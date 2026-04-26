"""
blueprints/api_bp.py
====================
Proxy per a APIs externes: Skyscanner, OpenStreetMap.

Rutes (prefix /api):
  GET /api/flights        → Vols (Skyscanner Live Prices v3)
  GET /api/hotels         → Hotels (Skyscanner / mock)
  GET /api/cars           → Cotxes de lloguer (Skyscanner / mock)
  GET /api/map-points     → POI via OpenStreetMap/Overpass
  GET /api/community      → Experiències + vídeos de la comunitat
  GET /api/health         → Salut de totes les APIs
"""

import os
import sys
import requests
from flask import Blueprint, request, jsonify
from models import db, Experience, Video, Photo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# IMPORTANTE: Ahora importamos también los modelos Pydantic
from blueprints.skyscanner_client import (
    search_flights, search_hotels, search_cars,
    SearchFlightRequest, SearchHotelRequest, SearchCarRequest
)

api_bp = Blueprint("api_bp", __name__, url_prefix="/api")

NOMINATIM_URL = "https://nominatim.openstreetmap.org"
OVERPASS_URL  = "https://overpass-api.de/api/interpreter"


# Vols
@api_bp.route('/flights', methods=['GET'])
def get_flights():
    origin = request.args.get("origin")
    destination = request.args.get("destination")
    date = request.args.get("date")
    return_date = request.args.get("return_date")
    
    if not origin or not destination or not date:
        return jsonify({"success": False, "error": "Faltan parámetros obligatorios"}), 400

    try:
        year, month, day = map(int, date.split("-"))
    except ValueError:
        return jsonify({"success": False, "error": "Formato de fecha inválido. Usa YYYY-MM-DD"}), 400

    # Procesar fecha de vuelta opcional
    return_year = return_month = return_day = None
    if return_date:
        try:
            return_year, return_month, return_day = map(int, return_date.split("-"))
        except ValueError:
            pass # Si viene mal formateada o vacía, la ignoramos

    params = SearchFlightRequest(
        originIata=origin,
        destinationIata=destination,
        year=year,
        month=month,
        day=day,
        return_year=return_year,
        return_month=return_month,
        return_day=return_day
    )

    result = search_flights(params)
    return jsonify(result)


# Hotels
@api_bp.route("/hotels")
def api_hotels():
    """GET /api/hotels?destination=BCN&checkin=2025-08-01&checkout=2025-08-07&adults=2"""
    destination = request.args.get("destination", "").upper().strip()
    checkin     = request.args.get("checkin", "").strip()
    checkout    = request.args.get("checkout", "").strip()
    try:
        adults = int(request.args.get("adults", 2))
    except ValueError:
        adults = 2

    if not destination:
        return jsonify({"error": "Cal indicar 'destination' (IATA)"}), 400

    # 1. Crear el objeto de petición
    hotel_request = SearchHotelRequest(
        destinationIata=destination,
        checkinDate=checkin,
        checkoutDate=checkout,
        adults=adults
    )

    # 2. Llamar a la función
    return jsonify(search_hotels(hotel_request))


# Cotxes
@api_bp.route("/cars")
def api_cars():
    """GET /api/cars?destination=BCN&pickup_date=2025-08-01&dropoff_date=2025-08-07"""
    destination  = request.args.get("destination", "").upper().strip()
    pickup_date  = request.args.get("pickup_date", "").strip()
    dropoff_date = request.args.get("dropoff_date", "").strip()

    if not destination:
        return jsonify({"error": "Cal indicar 'destination' (IATA)"}), 400

    # 1. Crear el objeto de petición
    car_request = SearchCarRequest(
        destinationIata=destination,
        pickupDate=pickup_date,
        dropoffDate=dropoff_date
    )

    # 2. Llamar a la función
    return jsonify(search_cars(car_request))


# Mapa / POI (Se mantiene exactamente igual)
@api_bp.route("/map-points")
def get_map_points():
    """
    GET /api/map-points?city=Barcelona&type=museum
    Tipus: museum | restaurant | hotel | park | monument | viewpoint | cafe | bar
    """
    city     = request.args.get("city", "Barcelona").strip()
    poi_type = request.args.get("type", "tourism").strip()

    try:
        geo_resp = requests.get(
            f"{NOMINATIM_URL}/search",
            params={"q": city, "format": "json", "limit": 1},
            headers={"User-Agent": "WanderLens/2.0 hackathon@example.com"},
            timeout=8,
        )
        geo_data = geo_resp.json()
        if not geo_data:
            return jsonify({"error": f"Ciutat '{city}' no trobada"}), 404

        lat       = float(geo_data[0]["lat"])
        lng       = float(geo_data[0]["lon"])
        city_name = geo_data[0]["display_name"].split(",")[0]

        osm_tag        = _poi_to_osm(poi_type)
        overpass_query = (
            f"[out:json][timeout:25];\n"
            f"(node[{osm_tag}](around:5000,{lat},{lng}););\n"
            f"out body 20;"
        )
        poi_resp = requests.post(OVERPASS_URL, data={"data": overpass_query}, timeout=15)
        poi_data = poi_resp.json()

        points = []
        for el in poi_data.get("elements", []):
            tags = el.get("tags", {})
            name = tags.get("name") or tags.get("name:ca") or tags.get("name:es") or ""
            if name:
                points.append({
                    "id":            el["id"],
                    "name":          name,
                    "lat":           el.get("lat", lat),
                    "lng":           el.get("lon", lng),
                    "type":          poi_type,
                    "website":       tags.get("website", ""),
                    "opening_hours": tags.get("opening_hours", "No disponible"),
                    "description":   tags.get("description", ""),
                })

        return jsonify({
            "city":   city_name,
            "center": {"lat": lat, "lng": lng},
            "points": points[:20],
        })

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error de mapa: {e}"}), 500


# Comunitat (Se mantiene exactamente igual)
@api_bp.route("/community")
def get_community():
    """GET /api/community?city=Tokyo"""
    city = request.args.get("city", "").strip()
    if not city:
        return jsonify({"experiences": [], "videos": []})

    exps = (Experience.query
            .filter(Experience.city.ilike(f"%{city}%"))
            .order_by(Experience.created_at.desc())
            .limit(8).all())

    vids = (Video.query
            .filter(Video.city.ilike(f"%{city}%"))
            .order_by(Video.created_at.desc())
            .limit(6).all())

    photos = (Photo.query
              .filter(Photo.city.ilike(f"%{city}%"))
              .order_by(Photo.created_at.desc())
              .limit(6).all())

    return jsonify({
        "city":        city,
        "experiences": [e.to_dict() for e in exps],
        "videos":      [v.to_dict() for v in vids],
        "photos":      [p.to_dict() for p in photos],
    })


# Discount check
@api_bp.route("/user-discount")
def user_discount():
    """GET /api/user-discount — returns current user's discount info"""
    from flask_login import current_user
    DISCOUNT_THRESHOLD = 300
    if not current_user.is_authenticated:
        return jsonify({"authenticated": False, "discount_pct": 0, "points": 0})
    pts = current_user.points
    # 500 pts → 10%, each extra 500 pts → +5%, max 25%
    if pts >= DISCOUNT_THRESHOLD:
        tiers = (pts - DISCOUNT_THRESHOLD) // 500
        discount_pct = min(10 + tiers * 5, 25)
    else:
        discount_pct = 0
    return jsonify({
        "authenticated": True,
        "points": pts,
        "discount_pct": discount_pct,
        "threshold": DISCOUNT_THRESHOLD,
        "has_discount": discount_pct > 0,
    })


# Health (Se mantiene exactamente igual)
@api_bp.route("/health")
def health():
    sky_key = bool(os.getenv("SKYSCANNER_API_KEY"))
    gem_key = bool(os.getenv("GEMINI_API_KEY"))
    db_url  = os.getenv("DATABASE_URL", "SQLite local")

    nom_ok = False
    try:
        r = requests.get(f"{NOMINATIM_URL}/status", timeout=4)
        nom_ok = r.status_code == 200
    except Exception:
        pass

    return jsonify({
        "status": "ok",
        "services": {
            "wanderlens":          "ok",
            "database":            "PostgreSQL" if os.getenv("DATABASE_URL") else "SQLite local",
            "gemini_api_key":      "ok" if gem_key else "⚠️  Falta GEMINI_API_KEY al .env",
            "skyscanner_api_key":  "ok" if sky_key else "⚠️  Falta SKYSCANNER_API_KEY (usant mock data)",
            "nominatim_osm":       "ok" if nom_ok else "⚠️  sense connexió",
            "overpass_api":        "gratuïta",
        },
    })


# Helpers
def _poi_to_osm(poi_type):
    return {
        "museum":     '"tourism"="museum"',
        "restaurant": '"amenity"="restaurant"',
        "hotel":      '"tourism"="hotel"',
        "park":       '"leisure"="park"',
        "monument":   '"historic"="monument"',
        "viewpoint":  '"tourism"="viewpoint"',
        "cafe":       '"amenity"="cafe"',
        "bar":        '"amenity"="bar"',
    }.get(poi_type, '"tourism"="attraction"')