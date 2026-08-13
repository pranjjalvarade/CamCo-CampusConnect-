import os
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from dotenv import load_dotenv
from models import db, User, UserInterest, AVAILABLE_INTERESTS

load_dotenv()

# ---------------------------------------------------------------------------
# App Factory
# ---------------------------------------------------------------------------

def create_app() -> Flask:
    app = Flask(__name__)

    # Configuration
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-fallback-secret")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///camco.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Extensions
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Please log in to access your dashboard."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    # Create database tables on first run
    with app.app_context():
        db.create_all()

    # -----------------------------------------------------------------------
    # Routes
    # -----------------------------------------------------------------------

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    # --- Registration -------------------------------------------------------

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            full_name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")
            selected_tags = request.form.getlist("interests")

            # --- Server-side Validation ---
            errors = []

            if not username or len(username) < 3:
                errors.append("Username must be at least 3 characters long.")
            if not email or "@" not in email:
                errors.append("Please enter a valid email address.")
            if len(password) < 6:
                errors.append("Password must be at least 6 characters long.")
            if password != confirm:
                errors.append("Passwords do not match.")
            if len(selected_tags) < 3:
                errors.append("Please select at least 3 interest tags.")

            # Validate tags against allowed list
            invalid_tags = [t for t in selected_tags if t not in AVAILABLE_INTERESTS]
            if invalid_tags:
                errors.append("One or more selected interests are invalid.")

            if User.query.filter_by(username=username).first():
                errors.append("Username is already taken.")
            if User.query.filter_by(email=email).first():
                errors.append("An account with this email already exists.")

            if errors:
                for error in errors:
                    flash(error, "danger")
                return render_template(
                    "register.html",
                    interests=AVAILABLE_INTERESTS,
                    selected_tags=selected_tags,
                    form_data=request.form,
                )

            # --- Create User ---
            user = User(username=username, email=email, full_name=full_name or None)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()  # Get user.id before committing

            for tag in selected_tags:
                db.session.add(UserInterest(user_id=user.id, tag=tag))

            db.session.commit()
            flash(
                f"Welcome to CamCo, {username}! Your account has been created. Please log in.",
                "success",
            )
            return redirect(url_for("login"))

        return render_template(
            "register.html",
            interests=AVAILABLE_INTERESTS,
            selected_tags=[],
            form_data={},
        )

    # --- Login --------------------------------------------------------------

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            remember = request.form.get("remember_me") == "on"

            user = User.query.filter_by(email=email).first()

            if user and user.check_password(password):
                login_user(user, remember=remember)
                next_page = request.args.get("next")
                flash(f"Welcome back, {user.username}!", "success")
                return redirect(next_page or url_for("dashboard"))
            else:
                flash("Invalid email or password. Please try again.", "danger")

        return render_template("login.html")

    # --- Logout -------------------------------------------------------------

    @app.route("/logout")
    @login_required
    def logout():
        username = current_user.username
        logout_user()
        flash(f"You have been logged out, {username}. See you soon!", "info")
        return redirect(url_for("login"))

    # --- Dashboard ----------------------------------------------------------

    @app.route("/dashboard")
    @login_required
    def dashboard():
        tags = current_user.get_interest_tags()
        return render_template("dashboard.html", user=current_user, tags=tags)

    return app


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
