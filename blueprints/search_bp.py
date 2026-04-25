"""
blueprints/search_bp.py
=======================
PART 2: Buscador AI + Planificador de viatge + Mapes + VR Preview
=================================================================
RESPONSABLE: [Nom de l'estudiant que s'encarrega d'aquesta part]

Rutes d'aquest Blueprint:
  GET  /search/              → Pàgina principal del planificador
  POST /search/plan          → Genera el pla de viatge complet via Gemini AI
  GET  /search/vr-videos     → Llista de vídeos VR disponibles per una ciutat
  POST /search/sustainability → Info sobre sostenibilitat i cultura (ODS 12)
"""

from flask import Blueprint, render_template, request, jsonify, session
import os
import json
import google.generativeai as genai

# ============================================================
# CREACIÓ DEL BLUEPRINT
# ============================================================
search_bp = Blueprint(
    "search_bp",
    __name__,
    template_folder="../templates",
    static_folder="../static"
)

# ============================================================
# CONFIGURACIÓ DE GEMINI AI
# La clau s'agafa automàticament del fitxer .env
# ============================================================
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini_model = genai.GenerativeModel("gemini-1.5-flash")  # Model ràpid i eficient


# ============================================================
# PROMPT BASE PER A GEMINI
# Modifica aquest prompt per ajustar el comportament de la IA
# ============================================================
TRAVEL_PLANNER_SYSTEM_PROMPT = """
Ets WanderLens AI, un planificador de viatges expert i empàtic.
El teu objectiu és crear itineraris personalitzats, pràctics i sostenibles.

SEMPRE has de:
1. Adaptar-te EXACTAMENT al pressupost indicat
2. Respectar les necessitats d'accessibilitat si n'hi ha
3. Incloure informació cultural i normes de respecte local (ODS 12 - Agenda 2030)
4. Organitzar rutes per PROXIMITAT GEOGRÀFICA (evita desplaçaments innecessaris)
5. Suggerir horaris aproximats realistes
6. Mencionar on fer fotos icòniques si l'usuari ho vol
7. Incloure opcions de restaurants locals (no cadenes internacionals)
8. Afegir llocs de descans/cafès intermedis

FORMAT DE RESPOSTA (sempre en JSON):
{
  "destination": "Nom de la destinació",
  "trip_summary": "Resum breu del viatge",
  "cultural_notes": ["nota cultural 1", "nota cultural 2"],
  "sustainability_tips": ["consell sostenibilitat 1"],
  "days": [
    {
      "day": 1,
      "theme": "Tema del dia",
      "stops": [
        {
          "time": "09:00",
          "name": "Nom del lloc",
          "type": "museu|restaurant|monument|parc|fotos|descans",
          "duration_minutes": 90,
          "description": "Descripció breu",
          "accessibility": "info sobre accessibilitat",
          "price_estimate": "€ / €€ / €€€ / gratis",
          "lat": 41.3851,
          "lng": 2.1734,
          "instagram_tip": "On fer la millor foto (si aplica)"
        }
      ]
    }
  ],
  "transport_tips": ["consell transport 1"],
  "budget_breakdown": {
    "accommodation": "XX€/nit",
    "food_per_day": "XX€",
    "activities": "XX€ total",
    "transport": "XX€"
  }
}
"""


# ============================================================
# RUTES
# ============================================================

@search_bp.route("/")
def search_home():
    """Pàgina principal del planificador de viatge."""
    return render_template("search.html")


@search_bp.route("/plan", methods=["POST"])
def generate_travel_plan():
    """
    Genera un pla de viatge complet usant Gemini AI.
    
    Espera JSON amb:
    {
        "message": "Vull anar a Tokyo 5 dies amb la meva parella...",
        "budget": "mitjà",
        "travel_style": ["cultura", "gastronomia", "fotos"],
        "transport_preferences": ["sense metro", "a peu", "bici"],
        "accommodation_priority": "centre",
        "accessibility_needs": [],
        "num_travelers": 2,
        "conversation_history": [...]   ← per mantenir el context del xat
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No s'han rebut dades"}), 400

    user_message = data.get("message", "")
    conversation_history = data.get("conversation_history", [])

    # Construeix el context de l'usuari per personalitzar la resposta
    user_context = _build_user_context(data)

    # Afegeix el missatge nou a l'historial
    full_prompt = f"{user_context}\n\nMissatge de l'usuari: {user_message}"

    try:
        # --- Crida a Gemini AI ---
        # Inclou tot l'historial de conversa per mantenir el context
        chat_messages = []
        for msg in conversation_history:
            chat_messages.append({
                "role": msg["role"],
                "parts": [msg["content"]]
            })
        chat_messages.append({
            "role": "user",
            "parts": [full_prompt]
        })

        response = gemini_model.generate_content(
            [TRAVEL_PLANNER_SYSTEM_PROMPT] + [m["parts"][0] for m in chat_messages],
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,        # Creativitat moderada
                max_output_tokens=4096  # Permet respostes llargues
            )
        )

        ai_response_text = response.text

        # Intenta parsejar com JSON (per als mapes i components visuals)
        try:
            # Neteja la resposta per si hi ha markdown
            clean_text = ai_response_text.strip()
            if clean_text.startswith("```"):
                clean_text = clean_text.split("```")[1]
                if clean_text.startswith("json"):
                    clean_text = clean_text[4:]
            travel_plan = json.loads(clean_text)
            return jsonify({
                "success": True,
                "type": "structured_plan",
                "plan": travel_plan,
                "raw_text": ai_response_text
            })
        except json.JSONDecodeError:
            # Si no és JSON, retorna com a text normal (primera interacció)
            return jsonify({
                "success": True,
                "type": "conversation",
                "message": ai_response_text
            })

    except Exception as e:
        return jsonify({"error": f"Error de Gemini AI: {str(e)}"}), 500


@search_bp.route("/vr-videos")
def get_vr_videos():
    """
    Retorna els vídeos VR disponibles per a una ciutat específica.
    Aquests vídeos els han pujat altres usuaris a la secció d'input.
    
    Paràmetres URL: ?city=Barcelona
    """
    city = request.args.get("city", "").lower()

    # TODO: Consultar a la BD els vídeos reals pujats pels usuaris
    # Per ara retorna dades de mostra
    mock_videos = [
        {
            "id": 1,
            "city": "barcelona",
            "title": "Passeig de Gràcia al matí",
            "uploader": "Maria G.",
            "vr_url": "/static/uploads/videos/sample_vr_barcelona.mp4",
            "thumbnail": "/static/assets/thumb_barcelona.jpg",
            "points_contributed": 50
        },
        {
            "id": 2,
            "city": "tokyo",
            "title": "Shibuya Crossing de nit",
            "uploader": "Jordi P.",
            "vr_url": "/static/uploads/videos/sample_vr_tokyo.mp4",
            "thumbnail": "/static/assets/thumb_tokyo.jpg",
            "points_contributed": 50
        }
    ]

    if city:
        filtered = [v for v in mock_videos if v["city"] == city]
    else:
        filtered = mock_videos

    return jsonify(filtered)


@search_bp.route("/sustainability", methods=["POST"])
def get_sustainability_info():
    """
    Genera informació de sostenibilitat i respecte cultural per a una destinació.
    Basat en els ODS 12 i 10 de l'Agenda 2030.
    
    Espera JSON: { "destination": "Japó" }
    """
    data = request.get_json()
    destination = data.get("destination", "")

    prompt = f"""
    Per al destí "{destination}", genera informació concisa sobre:
    1. Normes culturals i de respecte que cal conèixer
    2. Pràctiques de turisme sostenible (ODS 12 - Consum responsable)
    3. Respecte a les comunitats locals (ODS 10 - Reducció de desigualtats)
    4. Llocs on NO anar per massificació turística (overtourism)
    5. Alternatives sostenibles als llocs masticats
    
    Respon en JSON amb aquest format:
    {{
        "cultural_rules": ["regla1", "regla2"],
        "sustainable_tips": ["consell1"],
        "avoid_overtourism": ["lloc1 - per qué evitar"],
        "hidden_gems": ["lloc alternatiu 1"],
        "local_economy": "Com contribuir a l'economia local"
    }}
    """

    try:
        response = gemini_model.generate_content(prompt)
        clean_text = response.text.strip().replace("```json", "").replace("```", "")
        sustainability_data = json.loads(clean_text)
        return jsonify({"success": True, "data": sustainability_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# HELPERS PRIVATS
# ============================================================

def _build_user_context(data: dict) -> str:
    """
    Construeix el context personalitzat de l'usuari per enviar a Gemini.
    Com més context, millor serà el pla generat.
    """
    context_parts = []

    if data.get("budget"):
        context_parts.append(f"Pressupost: {data['budget']}")
    if data.get("travel_style"):
        context_parts.append(f"Estil de viatge: {', '.join(data['travel_style'])}")
    if data.get("transport_preferences"):
        context_parts.append(f"Transport preferit: {', '.join(data['transport_preferences'])}")
    if data.get("accessibility_needs"):
        context_parts.append(f"Necessitats d'accessibilitat: {', '.join(data['accessibility_needs'])}")
    if data.get("num_travelers"):
        context_parts.append(f"Número de viatgers: {data['num_travelers']}")
    if data.get("accommodation_priority"):
        context_parts.append(f"Prioritat allotjament: {data['accommodation_priority']}")

    # Afegeix el perfil desat (si n'hi ha un de la sessió d'input)
    # En una app real, aquest perfil vindria de la BD
    if context_parts:
        return "CONTEXT DE L'USUARI:\n" + "\n".join(f"- {p}" for p in context_parts)
    return ""
