"""blueprints/auth_bp.py — Registre, Login, Logout"""

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("home"))
        flash("Usuari o contrasenya incorrectes.", "error")
    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if len(username) < 3:
            flash("El nom d'usuari ha de tenir almenys 3 caràcters.", "error")
        elif len(password) < 6:
            flash("La contrasenya ha de tenir almenys 6 caràcters.", "error")
        elif User.query.filter_by(username=username).first():
            flash("Aquest nom d'usuari ja existeix.", "error")
        else:
            user = User(
                username=username,
                password_hash=generate_password_hash(password, method="scrypt"),
            )
            db.session.add(user)
            db.session.commit()
            flash("Compte creat! Ja pots iniciar sessió.", "success")
            return redirect(url_for("auth.login"))
    return render_template("register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Fins aviat!", "success")
    return redirect(url_for("home"))