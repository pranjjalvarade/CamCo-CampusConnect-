import json
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

AVAILABLE_INTERESTS = [
    "#Python", "#WebDev", "#QuantumPhysics", "#Cricket",
    "#Hackathons", "#MachineLearning", "#OpenSource", "#Robotics",
]


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name     = db.Column(db.String(120), nullable=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    interests     = db.relationship("UserInterest", backref="user", lazy=True, cascade="all, delete-orphan")
    posts         = db.relationship("Post", backref="author", lazy=True)
    comments      = db.relationship("Comment", backref="author", lazy=True)
    hackathon_posts = db.relationship("HackathonPost", backref="author", lazy=True)
    applications  = db.relationship("TeamApplication", foreign_keys="TeamApplication.applicant_id", backref="applicant", lazy=True)
    hack_applications = db.relationship("HackathonApplication", foreign_keys="HackathonApplication.applicant_id", backref="applicant", lazy=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_interest_tags(self) -> list[str]:
        return [i.tag for i in self.interests]

    @property
    def initials(self) -> str:
        display = self.full_name or self.username
        parts = display.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return display[:2].upper()

    def __repr__(self): return f"<User {self.username}>"


class UserInterest(db.Model):
    __tablename__ = "user_interests"
    id       = db.Column(db.Integer, primary_key=True)
    user_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    tag      = db.Column(db.String(64), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Regular Post (discussions / doubts only — team recruiting moved to Hackathon)
# ---------------------------------------------------------------------------

class Post(db.Model):
    __tablename__ = "posts"

    id         = db.Column(db.Integer, primary_key=True)
    title      = db.Column(db.String(200), nullable=False)
    body       = db.Column(db.Text, nullable=False)
    tag        = db.Column(db.String(64), nullable=False)
    author_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    timestamp  = db.Column(db.DateTime, default=datetime.utcnow)

    comments     = db.relationship("Comment", backref="post", lazy=True, cascade="all, delete-orphan")
    votes        = db.relationship("PostVote", backref="post", lazy=True, cascade="all, delete-orphan")

    def like_count(self)    -> int: return sum(1 for v in self.votes if v.value == 1)
    def dislike_count(self) -> int: return sum(1 for v in self.votes if v.value == -1)
    def comment_count(self) -> int: return len(self.comments)
    def __repr__(self): return f"<Post {self.id}>"


class PostVote(db.Model):
    __tablename__ = "post_votes"
    __table_args__ = (db.UniqueConstraint("user_id", "post_id", name="uq_post_vote"),)
    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=False)
    value   = db.Column(db.Integer, nullable=False)   # +1 or -1


# ---------------------------------------------------------------------------
# Comment
# ---------------------------------------------------------------------------

class Comment(db.Model):
    __tablename__ = "comments"
    id        = db.Column(db.Integer, primary_key=True)
    content   = db.Column(db.Text, nullable=False)
    post_id   = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    votes     = db.relationship("CommentVote", backref="comment", lazy=True, cascade="all, delete-orphan")

    def like_count(self)    -> int: return sum(1 for v in self.votes if v.value == 1)
    def dislike_count(self) -> int: return sum(1 for v in self.votes if v.value == -1)


class CommentVote(db.Model):
    __tablename__ = "comment_votes"
    __table_args__ = (db.UniqueConstraint("user_id", "comment_id", name="uq_comment_vote"),)
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey("comments.id"), nullable=False)
    value      = db.Column(db.Integer, nullable=False)   # +1 or -1


# ---------------------------------------------------------------------------
# TeamApplication (for regular posts — kept for compatibility)
# ---------------------------------------------------------------------------

class TeamApplication(db.Model):
    __tablename__ = "team_applications"
    id           = db.Column(db.Integer, primary_key=True)
    post_id      = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=True)
    applicant_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message      = db.Column(db.Text, nullable=False)
    status       = db.Column(db.String(20), default="pending", nullable=False)
    timestamp    = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# HackathonPost  — rich team-finding post
# ---------------------------------------------------------------------------

class HackathonPost(db.Model):
    __tablename__ = "hackathon_posts"

    id                     = db.Column(db.Integer, primary_key=True)
    hackathon_name         = db.Column(db.String(200), nullable=False)
    team_name              = db.Column(db.String(150), nullable=True)
    topic_decided          = db.Column(db.Boolean, default=False, nullable=False)
    theme                  = db.Column(db.String(300), nullable=True)
    problem_statement      = db.Column(db.Text, nullable=True)
    total_members          = db.Column(db.Integer, nullable=False)
    existing_members_count = db.Column(db.Integer, nullable=False, default=0)
    existing_members_json  = db.Column(db.Text, nullable=True)   # JSON list of {name, description, is_leader}
    required_skills        = db.Column(db.Text, nullable=True)
    author_id              = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    timestamp              = db.Column(db.DateTime, default=datetime.utcnow)

    hack_applications = db.relationship(
        "HackathonApplication", backref="hackathon_post", lazy=True, cascade="all, delete-orphan"
    )

    @property
    def members_needed(self) -> int:
        return max(0, self.total_members - self.existing_members_count)

    @property
    def display_title(self) -> str:
        return self.team_name or self.hackathon_name

    def get_existing_members(self) -> list:
        if self.existing_members_json:
            return json.loads(self.existing_members_json)
        return []

    def get_leader(self) -> str | None:
        for m in self.get_existing_members():
            if m.get("is_leader"):
                return m.get("name")
        return None

    def application_count(self) -> int:
        return len(self.hack_applications)

    def __repr__(self): return f"<HackathonPost {self.hackathon_name}>"


# ---------------------------------------------------------------------------
# HackathonApplication
# ---------------------------------------------------------------------------

class HackathonApplication(db.Model):
    __tablename__ = "hackathon_applications"
    __table_args__ = (db.UniqueConstraint("post_id", "applicant_id", name="uq_hack_application"),)

    id           = db.Column(db.Integer, primary_key=True)
    post_id      = db.Column(db.Integer, db.ForeignKey("hackathon_posts.id"), nullable=False)
    applicant_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message      = db.Column(db.Text, nullable=False)
    status       = db.Column(db.String(20), default="pending", nullable=False)
    timestamp    = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self): return f"<HackathonApplication {self.id} {self.status}>"
