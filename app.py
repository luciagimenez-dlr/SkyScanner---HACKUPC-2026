"""
WanderLens — Unified Entry Point
=================================
Integrates: authentication, video+experience upload, AI planner (Gemini),
            flights/hotels/cars (Skyscanner), map, community, VR conversion.

INSTALL:
  pip install flask flask-sqlalchemy flask-login flask-cors \
              google-generativeai requests python-dotenv werkzeug opencv-python numpy

CONFIGURE .env:
  GEMINI_API_KEY=...
  SKYSCANNER_API_KEY=...   (optional — without key, uses mock data)
  SECRET_KEY=change-this
  DB_PATH=wanderlens.db

RUN:
  python app.py
  → http://localhost:5000
"""

import os
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_required, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

from models import db, User
from blueprints.auth_bp   import auth_bp
from blueprints.input_bp  import input_bp
from blueprints.search_bp import search_bp
from blueprints.api_bp    import api_bp

load_dotenv()

# ── App ───────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["SECRET_KEY"]                  = os.getenv("SECRET_KEY", "wanderlens-dev-secret-2025")
app.config["SQLALCHEMY_DATABASE_URI"]     = f"sqlite:///{os.getenv('DB_PATH', 'wanderlens.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"]          = 500 * 1024 * 1024   # 500 MB upload limit
app.config["UPLOAD_FOLDER"]               = os.path.join("static", "uploads", "videos")

# ── Extensions ────────────────────────────────────────────────────────────────
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view    = "auth.login"
login_manager.login_message = "Please sign in to access this page."

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ── Blueprints ────────────────────────────────────────────────────────────────
app.register_blueprint(auth_bp)
app.register_blueprint(input_bp)
app.register_blueprint(search_bp)
app.register_blueprint(api_bp)

# ── DB init ───────────────────────────────────────────────────────────────────
with app.app_context():
    db.create_all()

# ── Core routes ───────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil():
    if request.method == "POST":
        current_user.travel_style        = request.form.get("travel_style", "")
        current_user.accessibility_needs = request.form.get("accessibility_needs", "")
        current_user.budget_preference   = request.form.get("budget_preference", "mitjà")
        db.session.commit()
        flash("Preferences updated successfully.", "success")
        return redirect(url_for("perfil"))
    return render_template("perfil.html", user=current_user)


@app.route("/change-password", methods=["POST"])
@login_required
def change_password():
    current_pw  = request.form.get("current_password", "")
    new_pw      = request.form.get("new_password", "")
    confirm_pw  = request.form.get("confirm_password", "")

    if not check_password_hash(current_user.password_hash, current_pw):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("perfil"))

    if len(new_pw) < 6:
        flash("New password must be at least 6 characters.", "error")
        return redirect(url_for("perfil"))

    if new_pw != confirm_pw:
        flash("Passwords do not match.", "error")
        return redirect(url_for("perfil"))

    current_user.password_hash = generate_password_hash(new_pw, method="scrypt")
    db.session.commit()
    flash("Password updated successfully.", "success")
    return redirect(url_for("perfil"))


@app.route("/delete-account", methods=["POST"])
@login_required
def delete_account():
    confirm_username = request.form.get("confirm_username", "").strip()
    password         = request.form.get("password", "")

    if confirm_username != current_user.username:
        flash("Username confirmation does not match.", "error")
        return redirect(url_for("perfil"))

    if not check_password_hash(current_user.password_hash, password):
        flash("Password is incorrect.", "error")
        return redirect(url_for("perfil"))

    # Remove all related files on disk
    from models import Video
    for vid in current_user.videos.all():
        for url in [vid.original_url, vid.vr_url]:
            if url:
                path = url.lstrip("/")
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass

    user_to_delete = db.session.get(User, current_user.id)
    logout_user()
    db.session.delete(user_to_delete)
    db.session.commit()

    flash("Your account has been permanently deleted.", "info")
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)