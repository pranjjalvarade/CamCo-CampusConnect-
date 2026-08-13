from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

AVAILABLE_INTERESTS = [
    "#Python",
    "#WebDev",
    "#QuantumPhysics",
    "#Cricket",
    "#Hackathons",
    "#MachineLearning",
    "#OpenSource",
    "#Robotics",
]


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to interests
    interests = db.relationship(
        "UserInterest", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        """Hash and store the password using Werkzeug's pbkdf2."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify the provided password against the stored hash."""
        return check_password_hash(self.password_hash, password)

    def get_interest_tags(self) -> list[str]:
        """Return a list of tag strings for this user."""
        return [interest.tag for interest in self.interests]

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class UserInterest(db.Model):
    __tablename__ = "user_interests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    tag = db.Column(db.String(64), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<UserInterest user_id={self.user_id} tag={self.tag}>"
