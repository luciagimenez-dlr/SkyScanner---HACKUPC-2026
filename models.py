"""
models.py — Models SQLAlchemy per a WanderLens
================================================
Taules:
  User        → usuaris registrats (auth + punts + perfil)
  Experience  → experiències de viatge compartides
  Video       → vídeos pujats (original + versió VR)
  Photo       → fotos pujades (panoràmiques / 360)
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id               = db.Column(db.Integer, primary_key=True)
    username         = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash    = db.Column(db.String(256), nullable=False)
    points           = db.Column(db.Integer, default=0)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    # Preferències de viatge
    travel_style        = db.Column(db.String(200), default="")
    accessibility_needs = db.Column(db.String(200), default="")
    budget_preference   = db.Column(db.String(50),  default="mitjà")

    # Relacions
    experiences = db.relationship("Experience", backref="author",  lazy="dynamic",
                                  cascade="all, delete-orphan")
    videos      = db.relationship("Video",      backref="uploader", lazy="dynamic",
                                  cascade="all, delete-orphan")
    photos      = db.relationship("Photo",      backref="uploader", lazy="dynamic",
                                  cascade="all, delete-orphan")

    @property
    def experience_count(self):
        return self.experiences.count()

    @property
    def video_count(self):
        return self.videos.count()

    @property
    def photo_count(self):
        return self.photos.count()

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "points": self.points,
            "travel_style": self.travel_style,
            "accessibility_needs": self.accessibility_needs,
            "budget_preference": self.budget_preference,
            "experience_count": self.experience_count,
            "video_count": self.video_count,
        }


class Experience(db.Model):
    __tablename__ = "experiences"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    city       = db.Column(db.String(150), nullable=False, index=True)
    title      = db.Column(db.String(200), default="")
    text       = db.Column(db.Text, nullable=False)
    rating     = db.Column(db.Integer, default=5)   # 1–5
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.author.username,
            "city": self.city,
            "title": self.title,
            "text": self.text,
            "rating": self.rating,
            "created_at": self.created_at.strftime("%Y-%m-%d"),
        }


class Video(db.Model):
    __tablename__ = "videos"

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    city         = db.Column(db.String(150), nullable=False, index=True)
    title        = db.Column(db.String(200), nullable=False)
    description  = db.Column(db.Text, default="")
    original_url = db.Column(db.String(500), default="")   # vídeo original
    vr_url       = db.Column(db.String(500), default="")   # versió VR side-by-side
    vr_ready     = db.Column(db.Boolean, default=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    POINTS_VALUE = 50  # punts per pujar un vídeo

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.uploader.username,
            "city": self.city,
            "title": self.title,
            "description": self.description,
            "original_url": self.original_url,
            "vr_url": self.vr_url,
            "vr_ready": self.vr_ready,
            "created_at": self.created_at.strftime("%Y-%m-%d"),
        }


class Photo(db.Model):
    __tablename__ = "photos"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    city       = db.Column(db.String(150), nullable=False, index=True)
    title      = db.Column(db.String(200), nullable=False)
    photo_url  = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    POINTS_VALUE = 30

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.uploader.username,
            "city": self.city,
            "title": self.title,
            "photo_url": self.photo_url,
            "created_at": self.created_at.strftime("%Y-%m-%d"),
        }