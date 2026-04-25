"""
blueprints/api_bp.py
====================
PART 3: API intermediària → Skyscanner + dades externes
=======================================================
RESPONSABLE: [Nom de l'estudiant que s'encarrega d'aquesta part]

Aquest Blueprint actua com a "proxy" entre el frontend i les APIs externes.
D'aquesta manera, la clau de Skyscanner mai no s'exposa al navegador.

Rutes d'aquest Blueprint:
  GET  /api/flights          → Cerca de vols via Skyscanner
  GET  /api/hotels           → Cerca d'hotels (Skyscanner o altra API)
  GET  /api/map-points       → Punts d'interès via OpenStreetMap/Nominatim
  GET  /api/health           → Comprova que totes les APIs funcionen
"""

from flask import Blueprint, request, jsonify
import os
import requests

# ============================================================
# CREACIÓ DEL BLUEPRINT
# ============================================================
api_bp = Blueprint("api_bp", __name__)

# ============================================================
# CONFIGURACIÓ D'APIs EXTERNES
# Totes les claus venen del fitxer .env
# ============================================================
SKYSCANNER_API_KEY = os.getenv("SKYSCANNER_API_KEY", "")
SKYSCANNER_BASE_URL = "https://partners.api.skyscanner.net/apiservices"

# OpenStreetMap Nominatim (gratuïta, sense clau necessària)
NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"

# Overpass API per punts d'interès (gratuïta)
OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"


# ============================================================
# RUTES
# ============================================================

@api_bp.route("/flights")
def search_flights():
    """
    Cerca vols via Skyscanner API.
    
    Paràmetres URL:
      ?origin=BCN&destination=TYO&date=2024-06-15&adults=2
    
    Documentació Skyscanner: https://developers.skyscanner.net/docs/intro
    
    IMPORTANT: Comprova la documentació oficial per als endpoints exactes,
    ja que Skyscanner pot actualitzar la seva API.
    """
    origin = request.args.get("origin", "BCN")
    destination = request.args.get("destination", "")
    date = request.args.get("date", "")
    adults = request.args.get("adults", "1")

    if not destination or not date:
        return jsonify({"error": "Cal indicar destinació i data"}), 400

    if not SKYSCANNER_API_KEY:
        # Retorna dades de mostra si no hi ha clau API
        return jsonify(_mock_flights(origin, destination, date, adults))

    # --- Crida real a Skyscanner API ---
    # NOTA: Consulta la documentació per l'endpoint correcte:
    # https://developers.skyscanner.net/docs/getting-started/authentication
    headers = {
        "x-api-key": SKYSCANNER_API_KEY,
        "Content-Type": "application/json"
    }

    # Exemple de crida (ajusta segons la documentació actual de Skyscanner)
    try:
        response = requests.post(
            f"{SKYSCANNER_BASE_URL}/v3/flights/live/search/create",
            headers=headers,
            json={
                "query": {
                    "market": "ES",
                    "locale": "ca-ES",
                    "currency": "EUR",
                    "queryLegs": [{
                        "originPlaceId": {"iata": origin},
                        "destinationPlaceId": {"iata": destination},
                        "date": {"year": int(date[:4]), "month": int(date[5:7]), "day": int(date[8:10])}
                    }],
                    "adults": int(adults),
                    "cabinClass": "CABIN_CLASS_ECONOMY"
                }
            }
        )
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error de Skyscanner API: {str(e)}"}), 500


@api_bp.route("/map-points")
def get_map_points():
    """
    Obté punts d'interès d'una ciutat via OpenStreetMap.
    Completament gratuït, no cal clau API!
    
    Paràmetres URL:
      ?city=Barcelona&type=museum    (tipus: museum, restaurant, hotel, park, etc.)
    """
    city = request.args.get("city", "Barcelona")
    poi_type = request.args.get("type", "tourism")

    # Primer obtenim les coordenades de la ciutat amb Nominatim
    try:
        geo_response = requests.get(
            f"{NOMINATIM_BASE_URL}/search",
            params={"q": city, "format": "json", "limit": 1},
            headers={"User-Agent": "WanderLens/1.0 hackathon@skyscanner.com"}
        )
        geo_data = geo_response.json()

        if not geo_data:
            return jsonify({"error": f"Ciutat '{city}' no trobada"}), 404

        lat = float(geo_data[0]["lat"])
        lng = float(geo_data[0]["lon"])
        city_name = geo_data[0]["display_name"].split(",")[0]

        # Ara fem una query Overpass per obtenir POIs
        # Radi de cerca: 5km del centre de la ciutat
        overpass_query = f"""
        [out:json][timeout:25];
        (
          node["{_poi_type_to_osm(poi_type)}"](around:5000,{lat},{lng});
        );
        out body 20;
        """

        poi_response = requests.post(
            OVERPASS_API_URL,
            data={"data": overpass_query}
        )
        poi_data = poi_response.json()

        # Formata els resultats
        points = []
        for element in poi_data.get("elements", []):
            tags = element.get("tags", {})
            name = tags.get("name", tags.get("name:ca", tags.get("name:es", "Sense nom")))
            if name and "Sense nom" not in name:
                points.append({
                    "id": element["id"],
                    "name": name,
                    "lat": element.get("lat", lat),
                    "lng": element.get("lon", lng),
                    "type": poi_type,
                    "website": tags.get("website", ""),
                    "opening_hours": tags.get("opening_hours", "No disponible"),
                    "description": tags.get("description", "")
                })

        return jsonify({
            "city": city_name,
            "center": {"lat": lat, "lng": lng},
            "points": points[:20]  # Limitem a 20 punts per rendiment
        })

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error de mapa: {str(e)}"}), 500


@api_bp.route("/health")
def health_check():
    """Comprova que totes les APIs externes funcionen correctament."""
    status = {
        "wanderlens": "ok",
        "gemini_api_key": "configurada" if os.getenv("GEMINI_API_KEY") else "FALTA CONFIGURAR",
        "skyscanner_api_key": "configurada" if SKYSCANNER_API_KEY else "FALTA CONFIGURAR",
        "openstreetmap": "gratuïta, sempre disponible"
    }

    # Comprova la connexió a Nominatim
    try:
        requests.get(f"{NOMINATIM_BASE_URL}/status", timeout=3)
        status["nominatim"] = "ok"
    except Exception:
        status["nominatim"] = "error de connexió"

    all_ok = all(v not in ["error de connexió"] for v in status.values())
    return jsonify({"status": "ok" if all_ok else "parcial", "services": status})


# ============================================================
# HELPERS PRIVATS
# ============================================================

def _poi_type_to_osm(poi_type: str) -> str:
    """Converteix un tipus genèric al tag d'OpenStreetMap."""
    mapping = {
        "museum":     "tourism=museum",
        "restaurant": "amenity=restaurant",
        "hotel":      "tourism=hotel",
        "park":       "leisure=park",
        "monument":   "historic=monument",
        "viewpoint":  "tourism=viewpoint",
        "cafe":       "amenity=cafe",
        "bar":        "amenity=bar",
        "tourism":    "tourism=attraction"
    }
    return mapping.get(poi_type, "tourism=attraction")


def _mock_flights(origin, destination, date, adults):
    """Dades de mostra per quan no hi ha clau Skyscanner configurada."""
    return {
        "mock": True,
        "message": "Configura SKYSCANNER_API_KEY al .env per vols reals",
        "results": [
            {
                "airline": "Vueling",
                "price": "189€",
                "departure": "08:30",
                "arrival": "11:45",
                "duration": "2h 15m",
                "stops": 0
            },
            {
                "airline": "Iberia",
                "price": "234€",
                "departure": "14:00",
                "arrival": "17:20",
                "duration": "2h 20m",
                "stops": 0
            }
        ]
    }
