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
# NOTE: gemini-2.5-flash has "thinking" enabled by default which adds 30-120s latency.
# We explicitly disable it via thinking_config, or fall back to 1.5-flash.
try:
    gemini_model = genai.GenerativeModel(
        "models/gemini-2.5-flash-preview-05-20",
        generation_config=genai.types.GenerationConfig(
            temperature=0.7,
        ),
    )
    _THINKING_BUDGET = 0   # 0 = disable thinking (set per-call below)
except Exception:
    _THINKING_BUDGET = None
    try:
        gemini_model = genai.GenerativeModel("models/gemini-1.5-flash")
    except Exception:
        gemini_model = None

# ── Prompts ───────────────────────────────────────────────────────────────────

PLAN_PROMPT = """\
You are WanderLens AI, an expert and responsible travel planner.
OUTPUT RULES: valid JSON only, no markdown fences, directly parseable by json.loads().
Use REAL lat/lng. Group stops by proximity. Choose destination yourself if unspecified.

User context: {user_context}
User message: {user_message}

Return EXACTLY this JSON (no text outside it):
{{
  "destination": "Full name",
  "destination_iata": "IATA code",
  "destination_city_en": "City in English",
  "trip_summary": "2-sentence summary",
  "cultural_notes": [
    "5–7 full sentences. Cover: etiquette/taboos, dress codes, tipping (exact %), photography, festivals/calendars, historical sensitivities, how locals perceive tourists."
  ],
  "days": [
    {{
      "day": 1,
      "theme": "Day theme",
      "stops": [
        {{
          "time": "09:00",
          "name": "Place",
          "type": "museum",
          "duration_minutes": 90,
          "description": "1–2 sentences",
          "accessibility": "Info",
          "price_estimate": "€€",
          "instagram_tip": "Best shot"
        }}
      ]
    }}
  ],
  "transport_tips": ["tip"],
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

    For gemini-2.5-flash we explicitly set thinking_budget=0 to disable
    the extended reasoning mode, which otherwise adds 30–120 s of latency.
    """
    try:
        gen_cfg = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        # Disable thinking on 2.5-flash to avoid huge latency
        extra_kwargs = {}
        if _THINKING_BUDGET is not None:
            extra_kwargs["generation_config"] = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                thinking_config={"thinking_budget": _THINKING_BUDGET},
            )
        else:
            extra_kwargs["generation_config"] = gen_cfg

        resp = gemini_model.generate_content(prompt, **extra_kwargs)
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