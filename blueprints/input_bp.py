"""
blueprints/input_bp.py
=======================
Gestió d'experiències de viatge i upload de vídeos amb conversió VR.

Rutes:
  GET  /input/                  → Pàgina principal (formulari)
  POST /input/experience        → Desa experiència (BD)
  POST /input/upload-video      → Puja vídeo + converteix a VR
  GET  /input/my-content        → Experiències i vídeos de l'usuari (JSON)
  DELETE /input/experience/<id> → Elimina experiència (perd punts)
  DELETE /input/video/<id>      → Elimina vídeo (perd punts)
  PUT  /input/experience/<id>   → Edita experiència
  GET  /input/leaderboard       → Ranking per punts
"""

import os
import subprocess
import time
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, User, Experience, Video, Photo

input_bp = Blueprint("input_bp", __name__, url_prefix="/input")

UPLOAD_FOLDER    = os.path.join("static", "uploads", "videos")
POINTS_EXPERIENCE = 20
POINTS_VIDEO      = 50
POINTS_PHOTO      = 30
POINTS_FOR_DISCOUNT = 100

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# Pàgina principal

@input_bp.route("/", strict_slashes=False)
def input_home():
    return render_template(
        "input.html",
        points=current_user.points if current_user.is_authenticated else 0,
        points_config={
            "review_submitted": POINTS_EXPERIENCE,
            "vr_video_uploaded": POINTS_VIDEO,
            "photo_uploaded": POINTS_PHOTO,
        },
    )


# Experiències

@input_bp.route("/experience", methods=["POST"])
@login_required
def save_experience():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No s'han rebut dades"}), 400

    city   = (data.get("city") or "").strip()
    text   = (data.get("text") or "").strip()
    title  = (data.get("title") or "").strip()
    rating = int(data.get("rating", 5))

    if not city or not text:
        return jsonify({"error": "Cal indicar la ciutat i el text"}), 400
    if len(text) < 20:
        return jsonify({"error": "L'experiència ha de tenir almenys 20 caràcters"}), 400

    exp = Experience(
        user_id=current_user.id,
        city=city,
        title=title,
        text=text,
        rating=max(1, min(5, rating)),
    )
    db.session.add(exp)
    current_user.points += POINTS_EXPERIENCE
    db.session.commit()

    return jsonify({
        "success": True,
        "points_earned": POINTS_EXPERIENCE,
        "total_points": current_user.points,
        "experience": exp.to_dict(),
        "message": f"Experiència desada! +{POINTS_EXPERIENCE} punts",
    })


@input_bp.route("/experience/<int:exp_id>", methods=["PUT"])
@login_required
def edit_experience(exp_id):
    exp = Experience.query.get_or_404(exp_id)
    if exp.user_id != current_user.id:
        return jsonify({"error": "No tens permís per editar aquesta experiència"}), 403

    data = request.get_json()
    exp.city   = (data.get("city") or exp.city).strip()
    exp.title  = (data.get("title") or exp.title).strip()
    exp.text   = (data.get("text") or exp.text).strip()
    exp.rating = int(data.get("rating", exp.rating))
    db.session.commit()
    return jsonify({"success": True, "experience": exp.to_dict()})


@input_bp.route("/experience/<int:exp_id>", methods=["DELETE"])
@login_required
def delete_experience(exp_id):
    exp = Experience.query.get_or_404(exp_id)
    if exp.user_id != current_user.id:
        return jsonify({"error": "No tens permís"}), 403

    # Perd els punts
    current_user.points = max(0, current_user.points - POINTS_EXPERIENCE)
    db.session.delete(exp)
    db.session.commit()
    return jsonify({
        "success": True,
        "points_lost": POINTS_EXPERIENCE,
        "total_points": current_user.points,
        "message": f"Experiència eliminada. -{POINTS_EXPERIENCE} punts.",
    })


# Vídeos

ALLOWED_EXTENSIONS = {"mp4", "mov", "avi", "mkv", "webm"}

def _allowed_video(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@input_bp.route("/upload-video", methods=["POST"])
@login_required
def upload_vr_video():
    if "video" not in request.files:
        return jsonify({"error": "No s'ha rebut cap vídeo"}), 400

    video_file  = request.files["video"]
    city        = (request.form.get("city") or "").strip()
    title       = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()

    if not video_file.filename or not _allowed_video(video_file.filename):
        return jsonify({"error": "Format de vídeo no vàlid (mp4, mov, avi, mkv, webm)"}), 400
    if not city or not title:
        return jsonify({"error": "Cal indicar la ciutat i el títol"}), 400

    ext      = video_file.filename.rsplit(".", 1)[1].lower()
    ts       = int(time.time())
    safe_fn  = f"orig_{current_user.id}_{ts}.{ext}"
    vr_fn    = f"vr_{current_user.id}_{ts}.mp4"
    orig_path = os.path.join(UPLOAD_FOLDER, safe_fn)
    vr_path   = os.path.join(UPLOAD_FOLDER, vr_fn)

    video_file.save(orig_path)


    vr_ok = False
    try:
        vf = (
            "split[L][R];"
            "[L]lenscorrection=k1=0.18:k2=0.0[Ld];"
            "[R]lenscorrection=k1=0.18:k2=0.0[Rd];"
            "[Ld][Rd]hstack"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", orig_path,
            "-vf", vf,
            "-c:v", "libx264",
            "-profile:v", "high",
            "-level", "4.1",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            vr_path,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        vr_ok = result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        vr_ok = False

    video = Video(
        user_id     = current_user.id,
        city        = city,
        title       = title,
        description = description,
        original_url = f"/static/uploads/videos/{safe_fn}",
        vr_url      = f"/static/uploads/videos/{vr_fn}" if vr_ok else "",
        vr_ready    = vr_ok,
    )
    db.session.add(video)
    current_user.points += POINTS_VIDEO
    db.session.commit()

    return jsonify({
        "success": True,
        "vr_ready": vr_ok,
        "original_url": video.original_url,
        "vr_url": video.vr_url,
        "points_earned": POINTS_VIDEO,
        "total_points": current_user.points,
        "video": video.to_dict(),
        "message": (
            f"Vídeo pujat i convertit a VR! +{POINTS_VIDEO} punts"
            if vr_ok
            else f"Vídeo pujat (conversió VR no disponible — ffmpeg no instal·lat). +{POINTS_VIDEO} punts"
        ),
    })


# Fotos

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}

def _allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


@input_bp.route("/upload-photo", methods=["POST"])
@login_required
def upload_photo():
    if "photo" not in request.files:
        return jsonify({"error": "No s'ha rebut cap foto"}), 400

    photo_file  = request.files["photo"]
    city        = (request.form.get("city") or "").strip()
    title       = (request.form.get("title") or "").strip()

    if not photo_file.filename or not _allowed_image(photo_file.filename):
        return jsonify({"error": "Format de foto no vàlid (jpg, jpeg, png, gif, webp)"}), 400
    if not city or not title:
        return jsonify({"error": "Cal indicar la ciutat i el títol"}), 400

    ext        = photo_file.filename.rsplit(".", 1)[1].lower()
    ts         = int(time.time())
    safe_fn    = f"photo_{current_user.id}_{ts}.{ext}"
    photo_path = os.path.join(UPLOAD_FOLDER, safe_fn)
    photo_file.save(photo_path)

    photo = Photo(
        user_id=current_user.id,
        city=city,
        title=title,
        photo_url=f"/static/uploads/videos/{safe_fn}",
    )
    db.session.add(photo)
    current_user.points += POINTS_PHOTO
    db.session.commit()

    return jsonify({
        "success": True,
        "photo_url": photo.photo_url,
        "points_earned": POINTS_PHOTO,
        "total_points": current_user.points,
        "message": f"Foto pujada! +{POINTS_PHOTO} punts",
    })


@input_bp.route("/photo/<int:photo_id>", methods=["DELETE"])
@login_required
def delete_photo(photo_id):
    ph = Photo.query.get_or_404(photo_id)
    if ph.user_id != current_user.id:
        return jsonify({"error": "No tens permís"}), 403

    if ph.photo_url:
        path = ph.photo_url.lstrip("/")
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    current_user.points = max(0, current_user.points - POINTS_PHOTO)
    db.session.delete(ph)
    db.session.commit()
    return jsonify({
        "success": True,
        "points_lost": POINTS_PHOTO,
        "total_points": current_user.points,
        "message": f"Foto eliminada. -{POINTS_PHOTO} punts.",
    })


@input_bp.route("/video/<int:video_id>", methods=["DELETE"])
@login_required
def delete_video(video_id):
    vid = Video.query.get_or_404(video_id)
    if vid.user_id != current_user.id:
        return jsonify({"error": "No tens permís"}), 403

    # Elimina fitxers del disc
    for url in [vid.original_url, vid.vr_url]:
        if url:
            path = url.lstrip("/")
            if os.path.exists(path):
                os.remove(path)

    current_user.points = max(0, current_user.points - POINTS_VIDEO)
    db.session.delete(vid)
    db.session.commit()
    return jsonify({
        "success": True,
        "points_lost": POINTS_VIDEO,
        "total_points": current_user.points,
        "message": f"Vídeo eliminat. -{POINTS_VIDEO} punts.",
    })


# ── El meu contingut ──────────────────────────────────────────────────────────

@input_bp.route("/my-content")
@login_required
def my_content():
    experiences = [e.to_dict() for e in
                   current_user.experiences.order_by(Experience.created_at.desc()).all()]
    videos      = [v.to_dict() for v in
                   current_user.videos.order_by(Video.created_at.desc()).all()]
    photos      = [p.to_dict() for p in
                   current_user.photos.order_by(Photo.created_at.desc()).all()]
    return jsonify({
        "experiences": experiences,
        "videos": videos,
        "photos": photos,
        "points": current_user.points,
        "points_for_discount": POINTS_FOR_DISCOUNT,
        "discount_available": current_user.points >= POINTS_FOR_DISCOUNT,
    })


@input_bp.route("/my-points")
@login_required
def my_points():
    return jsonify({
        "points": current_user.points,
        "points_for_discount": POINTS_FOR_DISCOUNT,
        "progress_percent": min(100, int(current_user.points / POINTS_FOR_DISCOUNT * 100)),
        "discount_available": current_user.points >= POINTS_FOR_DISCOUNT,
    })


#Leaderboard
@input_bp.route("/leaderboard")
def leaderboard():
    top = (User.query
           .filter(User.points > 0)
           .order_by(User.points.desc())
           .limit(10)
           .all())
    result = [
        {
            "rank": i + 1,
            "username": u.username,
            "points": u.points,
            "videos": u.video_count,
            "experiences": u.experience_count,
        }
        for i, u in enumerate(top)
    ]
    return jsonify(result)