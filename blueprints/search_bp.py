"""
blueprints/search_bp.py
========================
AI travel planner using Gemini + integrated community data.

Routes (prefix /search):
  GET  /search/       → Planner page
  POST /search/plan   → Generate itinerary via Gemini AI

GEMINI RELIABILITY NOTES:
  Gemini can occasionally be slow to respond or return incomplete JSON.
  We address this with:
    1. An automatic retry loop (up to 3 attempts) on failure or bad JSON
    2. A JSON extraction/repair fallback (_extract_json)
    3. Temperature slightly lowered on retries for more consistent output
    4. The PLAN_PROMPT instructs the model very explicitly to return only JSON
"""

import os
import json
import time
import google.generativeai as genai
from flask import Blueprint, render_template, request, jsonify

search_bp = Blueprint("search_bp", __name__, url_prefix="/search")

# Configure Gemini
_gemini_api_key = os.getenv("GEMINI_API_KEY", "")
genai.configure(api_key=_gemini_api_key)

# Initialise the model (flash = fast, sufficient for itinerary generation)
try:
    gemini_model = genai.GenerativeModel("models/gemini-2.5-flash")
except Exception:
    try:
        gemini_model = genai.GenerativeModel("models/gemini-1.5-flash")
    except Exception:
        gemini_model = None

# ── Prompts ───────────────────────────────────────────────────────────────────

PLAN_PROMPT = """\
You are WanderLens AI, an expert, empathetic, and responsible travel planner.
WanderLens is deeply committed to sustainable and respectful tourism.

CRITICAL INSTRUCTIONS — READ CAREFULLY:
- Respond with ONLY a valid JSON object. No other text whatsoever.
- Do NOT use markdown code blocks (no ```json or ```).
- The JSON must be parseable directly with json.loads().
- Include REAL, ACCURATE latitude/longitude coordinates for every place.
- Organise stops by geographic proximity to minimise travel time.
- If the destination is not specified, choose the best option yourself.
- Be enthusiastic but precise — this itinerary will be used to plan a real trip.

CULTURAL NOTES — very important for our mission:
  Generate 5–7 rich, specific cultural notes. Go beyond surface-level tips.
  Cover: local social etiquette and taboos, dress codes in different contexts,
  tipping customs with exact amounts/percentages, attitudes toward photography
  of people or sacred sites, religious or festive calendars that may affect
  the trip, historical sensitivities the traveller should be aware of, and
  one note on how locals perceive tourists (and how to be a welcome guest).
  Each note should be a full, informative sentence — not a vague bullet point.

SUSTAINABILITY TIPS — central to our responsible tourism mission:
  Generate 4–6 concrete sustainability tips, each actionable and specific to
  this destination. Cover: local vs tourist-trap restaurants (support local
  economy), how to use public transport / walk / cycle instead of taxis,
  plastic/waste reduction (e.g. refillable water bottle spots), wildlife or
  nature interaction ethics if relevant, how to respect local communities
  (e.g. avoid displacing residents in over-touristed neighbourhoods), and one
  tip about carbon offset or low-impact travel to/within the destination.

USEFUL PHRASES — essential for respectful and meaningful travel:
  Generate 8–10 useful everyday phrases in the LOCAL LANGUAGE of the destination.
  For each phrase include:
    - A practical English label (what situation it covers)
    - The phrase written in the local script (e.g. Japanese kanji/kana, Arabic, Cyrillic, Thai, etc.)
    - A simple phonetic pronunciation guide for English speakers (romanised, syllable-stressed)
    - A very short note on when/how to use it if not obvious
  Cover: greeting (hello/good morning), thank you, please, excuse me / sorry,
  do you speak English?, how much does this cost?, where is [place]?,
  I would like [this], the bill please, and one culturally important phrase
  (e.g. a local blessing, common farewell, or polite form of address).

User context:
{user_context}

User message: {user_message}

Respond with EXACTLY this JSON format (no text outside the JSON):
{{
  "destination": "Full destination name",
  "destination_iata": "Airport IATA code (e.g. BCN, CDG, NRT, JFK)",
  "destination_city_en": "City name in English (for Skyscanner)",
  "trip_summary": "Attractive 2-sentence summary of the trip",
  "cultural_notes": [
    "Rich, specific cultural note covering etiquette, history or social norms (full sentence)",
    "Dress code note for specific contexts (temples, beaches, restaurants...)",
    "Tipping customs with exact figures or percentages",
    "Photography etiquette — people, sacred sites, street scenes",
    "Religious/festive calendar note relevant to the travel dates or general awareness",
    "Historical sensitivity or local pride point the traveller should respect",
    "How locals perceive tourists and one way to be a genuinely welcome visitor"
  ],
  "sustainability_tips": [
    "Specific tip about eating local — name types of local eateries to look for",
    "Public transport or low-carbon mobility tip specific to this city",
    "Plastic/waste reduction tip (e.g. where to refill water, bring a bag)",
    "Community respect tip — how to avoid over-tourism harm in this destination",
    "Wildlife or nature ethics tip if relevant, otherwise a carbon offset suggestion"
  ],
  "useful_phrases": [
    {{
      "label": "Hello / Good morning",
      "local_script": "Phrase in local writing system",
      "phonetic": "foh-NEH-tik gide",
      "note": "Optional usage note"
    }},
    {{
      "label": "Thank you",
      "local_script": "...",
      "phonetic": "...",
      "note": ""
    }}
  ],
  "days": [
    {{
      "day": 1,
      "theme": "Thematic name for the day",
      "stops": [
        {{
          "time": "09:00",
          "name": "Place name",
          "type": "museum",
          "duration_minutes": 90,
          "description": "Brief 1–2 sentence description",
          "accessibility": "Accessibility information",
          "price_estimate": "€€",
          "lat": 41.3851,
          "lng": 2.1734,
          "instagram_tip": "Best photo spot if relevant"
        }}
      ]
    }}
  ],
  "transport_tips": ["Transport tip 1"],
  "budget_breakdown": {{
    "accommodation": "€80/night",
    "food_per_day": "€30",
    "activities": "€50 total",
    "transport": "€20"
  }}
}}
"""

CLARIFY_PROMPT = """\
You are WanderLens AI, a friendly and enthusiastic travel assistant.
Be brief and warm (maximum 2–3 sentences). Ask for the missing information
needed to generate the itinerary. Speak naturally — no bullet points or lists.

User message: {message}
Detected: destination={has_destination}, duration={has_duration}
"""

# ── Routes ────────────────────────────────────────────────────────────────────

@search_bp.route("/", strict_slashes=False)
def search_home():
    return render_template("search.html")


@search_bp.route("/plan", methods=["POST"])
def generate_plan():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data received"}), 400

    if not gemini_model:
        return jsonify({
            "error": "Gemini AI is not configured. Add GEMINI_API_KEY to your .env file."
        }), 503

    user_message = data.get("message", "")
    user_context = _build_context(data)

    try:
        intent = _detect_intent(user_message, data.get("conversation_history", []))

        if intent["ready"]:
            # Attempt to generate a structured itinerary plan
            # We retry up to 3 times because Gemini occasionally returns
            # incomplete JSON or times out on the first attempt.
            plan = _generate_plan_with_retry(user_message, user_context, max_attempts=3)

            if plan:
                return jsonify({"success": True, "type": "structured_plan", "plan": plan})

            # All retries failed — return a helpful conversation message
            return jsonify({
                "success": True,
                "type":    "conversation",
                "message": (
                    "I almost have your itinerary ready — the AI is taking a moment. "
                    "Could you try again? Sometimes rephrasing slightly helps too."
                ),
            })

        else:
            # Ask for clarification before generating a full plan
            prompt = CLARIFY_PROMPT.format(
                message=user_message,
                has_destination=intent["has_destination"],
                has_duration=intent["has_duration"],
            )
            resp = _call_gemini(prompt, temperature=0.9, max_tokens=300)
            return jsonify({"success": True, "type": "conversation", "message": resp or "Where would you like to go?"})

    except Exception as e:
        return jsonify({"error": f"Gemini AI error: {e}"}), 500


# ── Gemini call helpers ───────────────────────────────────────────────────────

def _call_gemini(prompt: str, temperature: float = 0.7, max_tokens: int = 8192) -> str | None:
    """
    Call Gemini and return the raw text response.
    Returns None on failure (so the caller can decide what to do).
    """
    try:
        resp = gemini_model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        return resp.text
    except Exception:
        return None


def _generate_plan_with_retry(user_message: str, user_context: str, max_attempts: int = 3) -> dict | None:
    """
    Try to generate a valid JSON itinerary plan up to max_attempts times.

    On each attempt:
      - Slightly lower the temperature to make the model more deterministic
      - Wait a short time between retries (helps with transient Gemini issues)
      - Try both _clean_json and _extract_json to parse the response

    Returns a parsed dict on success, or None if all attempts fail.
    """
    prompt = PLAN_PROMPT.format(
        user_context=user_context or "No specific preferences provided.",
        user_message=user_message,
    )

    for attempt in range(max_attempts):
        # Lower temperature slightly on retries for more consistent JSON output
        temperature = max(0.3, 0.7 - attempt * 0.15)

        if attempt > 0:
            # Brief pause before retry — helps with rate limits and transient errors
            time.sleep(1.5)

        raw = _call_gemini(prompt, temperature=temperature, max_tokens=8192)
        if not raw:
            continue

        # Try clean parse first
        cleaned = _clean_json(raw)
        try:
            plan = json.loads(cleaned)
            if _is_valid_plan(plan):
                return plan
        except json.JSONDecodeError:
            pass

        # Try extraction/repair fallback
        plan = _extract_json(raw)
        if plan and _is_valid_plan(plan):
            return plan

    return None


def _is_valid_plan(plan: dict) -> bool:
    """Check that the parsed plan has the minimum required fields."""
    if not isinstance(plan, dict):
        return False
    return bool(plan.get("destination") and plan.get("days"))


# ── Helpers ───────────────────────────────────────────────────────────────────

# Keywords used to detect intent — covers English, Catalan, and Spanish
# since users may write in any of these languages
DESTINATION_KW = [
    "barcelona","madrid","paris","london","rome","tokyo","amsterdam","berlin",
    "vienna","prague","lisbon","athens","istanbul","dubai","new york","nyc",
    "bangkok","singapore","seoul","beijing","shanghai","sydney","melbourne",
    "cairo","marrakech","nairobi","buenos aires","rio","cancun","miami",
    "los angeles","san francisco","chicago","toronto","montreal","brussels",
    "copenhagen","stockholm","oslo","helsinki","zurich","geneva","seville",
    "granada","toledo","valencia","bilbao","malaga","florence","venice",
    "milan","naples","porto","edinburgh","dublin","warsaw","budapest",
    "dubrovnik","spain","france","italy","germany","japan","china","india",
    "turkey","morocco","greece","portugal","netherlands","belgium","switzerland",
    "austria","czech","poland","hungary","thailand","vietnam","cambodia",
    "indonesia","bali","mexico","peru","argentina","colombia","brazil",
    "egypt","kenya","tanzania","south africa","australia","new zealand",
    "europe","asia","africa","america","asia",
    # Catalan/Spanish variants
    "espanya","itàlia","alemanya","japó","xina","grècia","marroc",
    "tailàndia","mèxic","perú","brasil","àfrica",
]

DURATION_KW = [
    "days","day","week","weekend","nights","night","hours",
    "dies","dia","setmana","cap de setmana","nits","nit",
]

TRAVEL_KW = [
    "want","would like","plan","travel","visit","go to","discover","explore",
    "trip","vacation","holiday","tour","journey","itinerary","recommend",
    "suggestion","where should","which city","what to do",
    "vull","volem","viatjar","viatge","visitar","conèixer","descobrir",
    "explorar","anar","on anar","recomanar",
]


def _detect_intent(message: str, history: list) -> dict:
    low          = message.lower()
    has_dest     = any(kw in low for kw in DESTINATION_KW)
    has_duration = any(kw in low for kw in DURATION_KW)
    has_travel   = any(kw in low for kw in TRAVEL_KW)
    # Ready if: destination mentioned, or travel intent + (duration or prior context)
    ready        = has_dest or (has_travel and (has_duration or len(history) > 0))
    return {"has_destination": has_dest, "has_duration": has_duration, "ready": ready}


def _build_context(data: dict) -> str:
    parts = []
    if data.get("budget"):                parts.append(f"Budget: {data['budget']}")
    if data.get("travel_style"):          parts.append(f"Style: {', '.join(data['travel_style'])}")
    if data.get("transport_preferences"): parts.append(f"Transport: {', '.join(data['transport_preferences'])}")
    if data.get("accessibility_needs"):   parts.append(f"Accessibility: {', '.join(data['accessibility_needs'])}")
    if data.get("num_travelers"):         parts.append(f"Travellers: {data['num_travelers']}")
    if data.get("accommodation_priority"):parts.append(f"Accommodation: {data['accommodation_priority']}")
    return "CONTEXT:\n" + "\n".join(f"- {p}" for p in parts) if parts else ""


def _clean_json(text: str) -> str:
    """Strip markdown fences and extract the outermost JSON object."""
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            candidate = parts[1].strip()
            text = candidate[4:].strip() if candidate.startswith("json") else candidate
    # Extract from first { to last }
    start = text.find("{")
    end   = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    return text


def _extract_json(text: str) -> dict | None:
    """
    Attempt to extract and repair a JSON object from messy model output.
    Tries: direct parse, trailing-comma removal.
    """
    import re
    start = text.find("{")
    end   = text.rfind("}")
    if start == -1 or end == -1:
        return None
    candidate = text[start:end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    # Remove trailing commas before ] or } (common Gemini mistake)
    try:
        fixed = re.sub(r",\s*([}\]])", r"\1", candidate)
        return json.loads(fixed)
    except json.JSONDecodeError:
        return None