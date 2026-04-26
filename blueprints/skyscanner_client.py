import os
import requests
from pydantic import BaseModel, Field

# ── Configuration & Constants ─────────────────────────────────────────────────

BASE_URL = "https://partners.api.skyscanner.net/apiservices"

# IATA → Skyscanner entityId mapping (needed for hotels and car hire v3 endpoints)
# If a destination is not listed, the fallback logic will gracefully return mock data.
ENTITY_MAP = {
    "BCN": "27544008", "MAD": "27544029", "CDG": "27539733",
    "LHR": "27539494", "NRT": "27542068", "JFK": "27537542",
    "DXB": "27537925", "AMS": "27539543", "FCO": "27539605",
    "BKK": "27543966", "SIN": "27543957", "SYD": "27543882",
    "ORD": "27537550", "LAX": "27537505", "MIA": "27537528",
    "ATL": "27537520", "IST": "27539798", "DEL": "27540791",
    "MUC": "27539688", "ZRH": "27539778", "VIE": "27539735",
    "CPH": "27539579", "OSL": "27539705", "ARN": "27539731",
    "HEL": "27539617", "BRU": "27539559", "LIS": "27539654",
    "TYO": "27542068", "ICN": "27542060", "PEK": "27541673",
    "PVG": "27541698", "HKG": "27541791", "KUL": "27543948",
    "CGK": "27543904", "BOM": "27540790", "GRU": "27563019",
    "EZE": "27563028", "SCL": "27563013", "YYZ": "27535700",
    "MEX": "27555464", "BOG": "27563036", "CAI": "27540476",
    "NBO": "27540356", "JNB": "27540321", "CPT": "27540293",
    "DUB": "27539596", "EDI": "27539590", "MAN": "27539492",
    "FRA": "27539654", "BER": "27539575", "PMI": "27544005",
    "AGP": "27543798", "VLC": "27543840", "BIO": "27543793",
    "GRX": "27543802", "SVQ": "27543838", "TFN": "27543907",
}

def _headers(api_key: str) -> dict:
    """Build the required Skyscanner API headers."""
    return {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }


# ── Models ────────────────────────────────────────────────────────────────────

from pydantic import BaseModel
from typing import Optional

class SearchFlightRequest(BaseModel):
    originIata: str
    destinationIata: str
    year: int
    month: int
    day: int = 1
    # Añadimos los opcionales
    return_year: Optional[int] = None
    return_month: Optional[int] = None
    return_day: Optional[int] = None
    market: str = "ES"
    locale: str = "en-US"
    currency: str = "EUR"

class SearchHotelRequest(BaseModel):
    """Parameters for hotel search"""
    destinationIata: str = Field(..., description="Destination airport IATA code (e.g., 'JFK')")
    checkinDate: str = Field(..., description="Check-in date (YYYY-MM-DD)")
    checkoutDate: str = Field(..., description="Check-out date (YYYY-MM-DD)")
    adults: int = Field(default=2, description="Number of adults")
    market: str = Field(default="ES", description="Market country code")
    locale: str = Field(default="en-GB", description="Locale for results")
    currency: str = Field(default="EUR", description="Currency for prices")

class SearchCarRequest(BaseModel):
    """Parameters for car hire search"""
    destinationIata: str = Field(..., description="Destination airport IATA code (e.g., 'JFK')")
    pickupDate: str = Field(..., description="Pick-up date (YYYY-MM-DD)")
    dropoffDate: str = Field(..., description="Drop-off date (YYYY-MM-DD)")
    market: str = Field(default="ES", description="Market country code")
    locale: str = Field(default="en-GB", description="Locale for results")
    currency: str = Field(default="EUR", description="Currency for prices")


# ── Core Functions ────────────────────────────────────────────────────────────

def search_flights(params: SearchFlightRequest) -> dict:
    """
    Search for indicative flights using the Skyscanner API. (Soporta Ida y Vuelta)
    """
    api_key = os.getenv("SKYSCANNER_API_KEY", "")

    if not api_key:
        return _mock_indicative_flights(params, "Sample data. Add SKYSCANNER_API_KEY to your .env for live prices.")

    url = f"{BASE_URL}/v3/flights/indicative/search"
    
    # Trayecto 1: IDA
    query_legs = [
        {
            "originPlace": {"queryPlace": {"iata": params.originIata}},
            "destinationPlace": {"queryPlace": {"iata": params.destinationIata}},
            "dateRange": {
                "startDate": {"year": params.year, "month": params.month},
                "endDate": {"year": params.year, "month": params.month}
            }
        }
    ]

    # Trayecto 2: VUELTA (Solo se añade si hay fecha de vuelta)
    if params.return_year and params.return_month:
        query_legs.append({
            "originPlace": {"queryPlace": {"iata": params.destinationIata}},
            "destinationPlace": {"queryPlace": {"iata": params.originIata}},
            "dateRange": {
                "startDate": {"year": params.return_year, "month": params.return_month},
                "endDate": {"year": params.return_year, "month": params.return_month}
            }
        })

    payload = {
        "query": {
            "market": params.market,
            "locale": params.locale,
            "currency": params.currency,
            "queryLegs": query_legs,
            "dateTimeGroupingType": "DATE_TIME_GROUPING_TYPE_BY_DATE"
        }
    }

    try:
        response = requests.post(url, headers=_headers(api_key), json=payload, timeout=20)
        response.raise_for_status()
        
        flights = _format_flight_results(response.json(), params)
        
        if not flights:
            return _mock_indicative_flights(params, "No se encontraron vuelos para esta fecha.")

        # Calculamos el return_date si lo hay, para enviárselo al frontend
        processed_return = f"{params.return_year}-{params.return_month:02d}" if params.return_year else None

        return {
            "success": True,
            "mock": False,
            "origin": params.originIata,
            "destination": params.destinationIata,
            "year": params.year,
            "month": params.month,
            "return_date": processed_return, # Frontend lo usa para pintar "Round Trip"
            "total": len(flights),
            "flights": flights,
        }

    except requests.exceptions.RequestException as e:
        return _mock_indicative_flights(params, "Error de API. Mostrando datos de prueba.")
    except Exception as e:
        return _mock_indicative_flights(params, "Error inesperado. Mostrando datos de prueba.")
    

def search_hotels(params: SearchHotelRequest) -> dict:
    """
    Search for hotels via Skyscanner.
    Falls back to mock data if no API key is set, the entityId is missing, or the API fails.
    """
    api_key = os.getenv("SKYSCANNER_API_KEY", "")
    if not api_key:
        return _mock_hotels(params, "Sample data. Add SKYSCANNER_API_KEY for live hotel prices.")

    entity_id = ENTITY_MAP.get(params.destinationIata.upper(), "")
    if not entity_id:
        return _mock_hotels(params, f"Entity ID not found for {params.destinationIata}. Showing sample hotels.")

    try:
        response = requests.get(
            f"{BASE_URL}/v3/hotels/search",
            headers=_headers(api_key),
            params={
                "market": params.market,
                "locale": params.locale,
                "currency": params.currency,
                "entityId": entity_id,
                "checkinDate": params.checkinDate,
                "checkoutDate": params.checkoutDate or params.checkinDate,
                "adults": max(1, params.adults),
            },
            timeout=15,
        )
        response.raise_for_status()
        
        parsed = _parse_hotels_response(response.json())
        if parsed.get("hotels"):
            return parsed
            
    except Exception as e:
        pass # Swallow all errors and fall back to mock data below

    return _mock_hotels(params, "Live hotel data unavailable (or 402 Payment Required). Showing sample prices.")


def search_cars(params: SearchCarRequest) -> dict:
    """
    Search for rental cars via Skyscanner.
    Falls back to mock data on any error or missing configuration.
    """
    api_key = os.getenv("SKYSCANNER_API_KEY", "")
    if not api_key:
        return _mock_cars(params, "Sample data. Add SKYSCANNER_API_KEY for live car prices.")

    entity_id = ENTITY_MAP.get(params.destinationIata.upper(), "")
    if not entity_id:
        return _mock_cars(params, f"Entity ID not found for {params.destinationIata}. Showing sample cars.")

    try:
        response = requests.get(
            f"{BASE_URL}/v3/carhire/search",
            headers=_headers(api_key),
            params={
                "market": params.market,
                "locale": params.locale,
                "currency": params.currency,
                "pickUpEntityId": entity_id,
                "pickUpDate": params.pickupDate,
                "dropOffDate": params.dropoffDate or params.pickupDate,
            },
            timeout=15,
        )
        response.raise_for_status()
        
        parsed = _parse_cars_response(response.json())
        if parsed.get("cars"):
            return parsed

    except Exception as e:
        pass # Swallow all errors and fall back to mock data below

    return _mock_cars(params, "Live car hire data unavailable. Showing sample prices.")


# ── Formatting & Parsing Helpers ──────────────────────────────────────────────

def _format_flight_results(data: dict, params: SearchFlightRequest) -> list:
    flights = []
    
    quotes = data.get("content", {}).get("results", {}).get("quotes", {})
    carriers = data.get("content", {}).get("results", {}).get("carriers", {})

    for quote_id, quote_data in quotes.items():
        try:
            # Precio
            price_amount = float(quote_data.get("minPrice", {}).get("amount", 0))
            
            # Aerolínea
            outbound_leg = quote_data.get("outboundLeg", {})
            carrier_id = outbound_leg.get("marketingCarrierId")
            airline_name = "Skyscanner"
            if carrier_id and carrier_id in carriers:
                airline_name = carriers[carrier_id].get("name", "Skyscanner")

            # Fechas y Escalas
            departure = outbound_leg.get("departureDateTime", {})
            q_year = departure.get("year", params.year)
            q_month = departure.get("month", params.month)
            q_day = departure.get("day", 1)
            formatted_date = f"{q_year}-{q_month:02d}-{q_day:02d}"

            is_direct = quote_data.get("isDirect", False)
            stops = 0 if is_direct else 1
            stops_label = "Direct" if is_direct else "1+ Stops"

            base_link = f"https://www.skyscanner.com/transport/flights/{params.originIata.lower()}/{params.destinationIata.lower()}/"

            flights.append({
                "airline": airline_name,
                "departure": formatted_date, # La API indicativa da la fecha, no la hora exacta
                "arrival": "--:--",         # Relleno visual
                "duration_label": "--",      # Relleno visual
                "duration_min": 0,           
                "stops_label": stops_label,
                "stops": stops,
                "price_label": f"€{int(price_amount)}",
                "price_eur": price_amount,
                "deep_link": base_link
            })
        except Exception:
            continue
            
    return sorted(flights, key=lambda f: f.get("price_eur", 0))

def _parse_hotels_response(data: dict) -> dict:
    hotels = []
    for h in data.get("hotels", [])[:6]:
        hotels.append({
            "name": h.get("name", "Hotel"),
            "price": h.get("pricePerNight", {}).get("amount", "?"),
            "stars": h.get("stars", 3),
            "rating": h.get("reviewScore", ""),
            "deep_link": h.get("url", "https://www.skyscanner.com/hotels"),
            "is_mock": False
        })
    return {"success": True, "mock": False, "hotels": hotels}

def _parse_cars_response(data: dict) -> dict:
    cars = []
    for c in data.get("cars", [])[:4]:
        cars.append({
            "name": c.get("vehicleInfo", {}).get("name", "Vehicle"),
            "category": c.get("vehicleInfo", {}).get("category", "Auto"),
            "price": c.get("price", {}).get("amount", "?"),
            "provider": c.get("provider", {}).get("name", "Skyscanner"),
            "deep_link": c.get("deepLink", "https://www.skyscanner.com/cars"),
            "is_mock": False
        })
    return {"success": True, "mock": False, "cars": cars}


# ── Mock Data Generators ──────────────────────────────────────────────────────

def _mock_indicative_flights(params: SearchFlightRequest, warning_msg: str) -> dict:
    base_link = f"https://www.skyscanner.com/transport/flights/{params.originIata.lower()}/{params.destinationIata.lower()}/"
    mock_flights = [
        {"date": f"{params.year}-{params.month:02d}-05", "price_eur": 45, "price_label": "€45", "is_direct": True, "deep_link": base_link, "is_mock": True},
        {"date": f"{params.year}-{params.month:02d}-12", "price_eur": 38, "price_label": "€38", "is_direct": True, "deep_link": base_link, "is_mock": True},
        {"date": f"{params.year}-{params.month:02d}-19", "price_eur": 89, "price_label": "€89", "is_direct": False, "deep_link": base_link, "is_mock": True},
    ]
    return {
        "success": True, "mock": True,
        "origin": params.originIata, "destination": params.destinationIata,
        "year": params.year, "month": params.month,
        "total": len(mock_flights),
        "flights": sorted(mock_flights, key=lambda f: f["price_eur"]),
        "warning": warning_msg,
    }

def _mock_hotels(params: SearchHotelRequest, warning_msg: str) -> dict:
    base = "https://www.skyscanner.com/hotels"
    dest = params.destinationIata.upper()
    mock_hotels = [
        {"name": f"Central Hotel {dest}", "price": "95", "stars": 4, "rating": "8.7", "deep_link": base, "is_mock": True},
        {"name": f"Boutique Stay {dest}", "price": "72", "stars": 3, "rating": "8.2", "deep_link": base, "is_mock": True},
        {"name": f"City Inn {dest}", "price": "58", "stars": 3, "rating": "7.9", "deep_link": base, "is_mock": True},
    ]
    return {
        "success": True, "mock": True,
        "destination": dest,
        "checkin": params.checkinDate,
        "hotels": mock_hotels,
        "warning": warning_msg,
    }

def _mock_cars(params: SearchCarRequest, warning_msg: str) -> dict:
    base = "https://www.skyscanner.com/cars"
    mock_cars = [
        {"name": "Toyota Yaris", "category": "Economy", "price": "€28/day", "provider": "Hertz", "deep_link": base, "is_mock": True},
        {"name": "Volkswagen Golf", "category": "Compact", "price": "€38/day", "provider": "Europcar", "deep_link": base, "is_mock": True},
        {"name": "BMW 3 Series", "category": "Premium", "price": "€79/day", "provider": "Sixt", "deep_link": base, "is_mock": True},
    ]
    return {
        "success": True, "mock": True,
        "destination": params.destinationIata.upper(),
        "cars": mock_cars,
        "warning": warning_msg,
    }