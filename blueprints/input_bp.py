"""
blueprints/input_bp.py
======================
PART 1: Perfil d'usuari + Upload de vídeos VR + Sistema de punts
================================================================
RESPONSABLE: [Nom de l'estudiant que s'encarrega d'aquesta part]

Rutas d'aquest Blueprint:
  GET  /input/              → Pàgina principal del formulari d'input
  POST /input/profile       → Desa el perfil de l'usuari (interessos, accessibilitat, etc.)
  POST /input/upload-video  → Processa i puja vídeo al format VR (side-by-side)
  GET  /input/leaderboard   → Classifica d'usuaris per punts
  GET  /input/my-points     → Punts actuals de l'usuari
"""

from flask import Blueprint, render_template, request, jsonify, session
import os
import json

# ============================================================
# CREACIÓ DEL BLUEPRINT
# ============================================================
input_bp = Blueprint(
    "input_bp",
    __name__,
    template_folder="../templates",   # carpeta templates compartida
    static_folder="../static"          # carpeta static compartida
)

# ============================================================
# SISTEMA DE PUNTS  (en producció això hauria d'estar a una BD)
# ============================================================
POINTS_CONFIG = {
    "profile_completed":  10,   # Punts per completar el perfil
    "review_submitted":   20,   # Punts per escriure una ressenya
    "photo_uploaded":     15,   # Punts per pujar una foto
    "vr_video_uploaded":  50,   # Punts per pujar vídeo VR (el més valuós!)
    "accessibility_info": 30,   # Punts extra per informació d'accessibilitat
}

POINTS_FOR_DISCOUNT = 100  # Punts necessaris per obtenir descompte


# ============================================================
# RUTES
# ============================================================

@input_bp.route("/")
def input_home():
    """Pàgina principal del formulari d'input."""
    # TODO: Carregar punts actuals de l'usuari des de la BD
    user_points = session.get("user_points", 0)
    return render_template("input.html", points=user_points, points_config=POINTS_CONFIG)


@input_bp.route("/profile", methods=["POST"])
def save_profile():
    """
    Desa el perfil de l'usuari.
    
    Espera JSON amb:
    {
        "name": "Anna",
        "travel_types": ["cultura", "museus", "gastronomia"],
        "accessibility_needs": ["cadira de rodes"],
        "past_experiences": [
            {
                "city": "Barcelona",
                "positive": "Molt accessible al centre",
                "negative": "El metro no té ascensors a totes les estacions"
            }
        ],
        "budget_range": "mitjà",  // baix | mitjà | alt
        "family_with_kids": false
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "No s'han rebut dades"}), 400

    # TODO: Validar i desar a la base de dades
    # Per ara ho desem a la sessió com a exemple
    session["user_profile"] = data

    # Calcula punts guanyats
    points_earned = POINTS_CONFIG["profile_completed"]
    if data.get("accessibility_needs"):
        points_earned += POINTS_CONFIG["accessibility_info"]

    # Actualitza punts totals
    current_points = session.get("user_points", 0)
    new_total = current_points + points_earned
    session["user_points"] = new_total

    # Comprova si ha aconseguit descompte
    discount_unlocked = (current_points < POINTS_FOR_DISCOUNT) and (new_total >= POINTS_FOR_DISCOUNT)

    return jsonify({
        "success": True,
        "points_earned": points_earned,
        "total_points": new_total,
        "discount_unlocked": discount_unlocked,
        "message": f"Perfil desat! Has guanyat {points_earned} punts."
    })


@input_bp.route("/upload-video", methods=["POST"])
def upload_vr_video():
    """
    Processa un vídeo normal i el converteix a format VR side-by-side.
    
    Format VR side-by-side:
    - El vídeo original es duplica horitzontalment
    - La meitat esquerra és per l'ull esquerre
    - La meitat dreta és per l'ull dret
    - Resultat: usuaris amb ulleres VR/AR veuen en 3D immersiu
    
    NOTA: Per la conversió real caldria instal·lar ffmpeg:
          sudo apt install ffmpeg  (Linux/Mac)
          o descarregar de https://ffmpeg.org (Windows)
    """
    if "video" not in request.files:
        return jsonify({"error": "No s'ha rebut cap vídeo"}), 400

    video_file = request.files["video"]
    city = request.form.get("city", "desconeguda")
    description = request.form.get("description", "")

    if video_file.filename == "":
        return jsonify({"error": "Nom de fitxer buit"}), 400

    # --- Desa el vídeo original temporalment ---
    upload_folder = os.path.join("static", "uploads", "videos")
    os.makedirs(upload_folder, exist_ok=True)

    original_path = os.path.join(upload_folder, f"original_{video_file.filename}")
    video_file.save(original_path)

    # --- Converteix a format VR side-by-side amb ffmpeg ---
    vr_filename = f"vr_{video_file.filename}"
    vr_path = os.path.join(upload_folder, vr_filename)

    # Comanda ffmpeg per duplicar el vídeo side-by-side (format cardboard VR)
    # [DEPENÈNCIA EXTERNA] Necessites ffmpeg instal·lat al sistema
    ffmpeg_command = (
        f'ffmpeg -i "{original_path}" '
        f'-vf "split[a][b];[a]pad=iw*2:ih[left];[left][b]overlay=w" '
        f'"{vr_path}" -y'
    )

    # TODO: Descomentar quan tinguis ffmpeg instal·lat:
    # import subprocess
    # result = subprocess.run(ffmpeg_command, shell=True, capture_output=True)
    # if result.returncode != 0:
    #     return jsonify({"error": "Error en la conversió VR"}), 500

    # Desa metadades del vídeo
    video_metadata = {
        "city": city,
        "description": description,
        "original_file": original_path,
        "vr_file": vr_path,
        "uploader": session.get("user_profile", {}).get("name", "Anònim")
    }

    # Actualitza punts
    current_points = session.get("user_points", 0)
    points_earned = POINTS_CONFIG["vr_video_uploaded"]
    new_total = current_points + points_earned
    session["user_points"] = new_total
    discount_unlocked = (current_points < POINTS_FOR_DISCOUNT) and (new_total >= POINTS_FOR_DISCOUNT)

    return jsonify({
        "success": True,
        "vr_video_url": f"/static/uploads/videos/{vr_filename}",
        "points_earned": points_earned,
        "total_points": new_total,
        "discount_unlocked": discount_unlocked,
        "message": f"Vídeo convertit a VR! Has guanyat {points_earned} punts."
    })


@input_bp.route("/my-points")
def my_points():
    """Retorna els punts actuals de l'usuari i el progrés cap al descompte."""
    points = session.get("user_points", 0)
    return jsonify({
        "points": points,
        "points_for_discount": POINTS_FOR_DISCOUNT,
        "progress_percent": min(100, int((points / POINTS_FOR_DISCOUNT) * 100)),
        "discount_available": points >= POINTS_FOR_DISCOUNT
    })


@input_bp.route("/leaderboard")
def leaderboard():
    """
    Classifica d'usuaris per punts.
    TODO: Implementar amb base de dades real (SQLite, PostgreSQL, etc.)
    """
    # Dades de mostra — substituir per consulta a BD
    mock_leaderboard = [
        {"rank": 1, "name": "Maria G.",     "points": 340, "videos": 5},
        {"rank": 2, "name": "Jordi P.",     "points": 280, "videos": 4},
        {"rank": 3, "name": "Sara M.",      "points": 210, "videos": 3},
        {"rank": 4, "name": "Tu",           "points": session.get("user_points", 0), "videos": 0},
    ]
    return jsonify(mock_leaderboard)
