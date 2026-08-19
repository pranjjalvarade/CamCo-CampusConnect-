import os
import json
from collections import defaultdict
from flask import Flask, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
from models import (
    db, User, UserInterest, Post, PostVote, Comment, CommentVote,
    TeamApplication, HackathonPost, HackathonApplication, AVAILABLE_INTERESTS,
)

load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"]                = os.getenv("SECRET_KEY", "dev-secret")
    app.config["SQLALCHEMY_DATABASE_URI"]   = os.getenv("DATABASE_URL", "sqlite:///camco.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(uid): return db.session.get(User, int(uid))

    with app.app_context():
        db.create_all()

    # =========================================================================
    # Auth
    # =========================================================================

    @app.route("/")
    def index():
        return redirect(url_for("feed") if current_user.is_authenticated else url_for("login"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("feed"))
        if request.method == "POST":
            username      = request.form.get("username", "").strip()
            full_name     = request.form.get("full_name", "").strip()
            email         = request.form.get("email", "").strip().lower()
            password      = request.form.get("password", "")
            confirm       = request.form.get("confirm_password", "")
            selected_tags = request.form.getlist("interests")

            errors = []
            if len(username) < 3:           errors.append("Username must be ≥ 3 characters.")
            if "@" not in email:            errors.append("Invalid email address.")
            if len(password) < 6:           errors.append("Password must be ≥ 6 characters.")
            if password != confirm:         errors.append("Passwords do not match.")
            if len(selected_tags) < 3:      errors.append("Select at least 3 interests.")
            if any(t not in AVAILABLE_INTERESTS for t in selected_tags):
                errors.append("Invalid interest tag selected.")
            if User.query.filter_by(username=username).first(): errors.append("Username taken.")
            if User.query.filter_by(email=email).first():       errors.append("Email already registered.")

            if errors:
                for e in errors: flash(e, "danger")
                return render_template("register.html", interests=AVAILABLE_INTERESTS,
                                       selected_tags=selected_tags, form_data=request.form)

            user = User(username=username, email=email, full_name=full_name or None)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            for tag in selected_tags:
                db.session.add(UserInterest(user_id=user.id, tag=tag))
            db.session.commit()
            flash(f"Welcome to CamCo, {username}! Please log in.", "success")
            return redirect(url_for("login"))

        return render_template("register.html", interests=AVAILABLE_INTERESTS,
                               selected_tags=[], form_data={})

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("feed"))
        if request.method == "POST":
            email    = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            remember = request.form.get("remember_me") == "on"
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                login_user(user, remember=remember)
                flash(f"Welcome back, {user.username}!", "success")
                return redirect(request.args.get("next") or url_for("feed"))
            flash("Invalid email or password.", "danger")
        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        name = current_user.username
        logout_user()
        flash(f"Logged out, {name}. See you soon!", "info")
        return redirect(url_for("login"))

    # =========================================================================
    # Dashboard
    # =========================================================================

    @app.route("/dashboard")
    @login_required
    def dashboard():
        tags     = current_user.get_interest_tags()
        my_posts = Post.query.filter_by(author_id=current_user.id).order_by(Post.timestamp.desc()).limit(5).all()
        my_hack  = HackathonPost.query.filter_by(author_id=current_user.id).order_by(HackathonPost.timestamp.desc()).limit(5).all()
        return render_template("dashboard.html", user=current_user, tags=tags,
                               my_posts=my_posts, my_hack=my_hack)

    # =========================================================================
    # Feed  (discussions / doubts)
    # =========================================================================

    @app.route("/feed")
    @login_required
    def feed():
        view       = request.args.get("view", "my")
        tag_filter = request.args.get("tag", "")

        query = Post.query
        if view != "all":
            user_tags = current_user.get_interest_tags()
            query = query.filter(Post.tag.in_(user_tags))
        if tag_filter and tag_filter in AVAILABLE_INTERESTS:
            query = query.filter(Post.tag == tag_filter)

        posts = query.order_by(Post.timestamp.desc()).all()

        user_post_votes = {v.post_id: v.value for v in
                           PostVote.query.filter_by(user_id=current_user.id).all()}
        all_cids = [c.id for p in posts for c in p.comments]
        user_comment_votes = {}
        if all_cids:
            user_comment_votes = {v.comment_id: v.value for v in
                                  CommentVote.query.filter(CommentVote.user_id == current_user.id,
                                                           CommentVote.comment_id.in_(all_cids)).all()}
        return render_template("feed.html", posts=posts, view=view, tag_filter=tag_filter,
                               interests=AVAILABLE_INTERESTS,
                               user_tags=current_user.get_interest_tags(),
                               user_post_votes=user_post_votes,
                               user_comment_votes=user_comment_votes)

    # --- Create regular post ------------------------------------------------

    @app.route("/post/create", methods=["POST"])
    @login_required
    def create_post():
        title = request.form.get("title", "").strip()
        body  = request.form.get("body", "").strip()
        tag   = request.form.get("tag", "").strip()
        errors = []
        if len(title) < 5:           errors.append("Title must be ≥ 5 characters.")
        if len(body) < 10:           errors.append("Body must be ≥ 10 characters.")
        if tag not in AVAILABLE_INTERESTS: errors.append("Select a valid tag.")
        if errors:
            for e in errors: flash(e, "danger")
            return redirect(url_for("feed"))
        db.session.add(Post(title=title, body=body, tag=tag, author_id=current_user.id))
        db.session.commit()
        flash("Post published!", "success")
        return redirect(url_for("feed"))

    # --- Delete regular post (author only) ----------------------------------

    @app.route("/post/<int:post_id>/delete", methods=["POST"])
    @login_required
    def delete_post(post_id):
        post = db.session.get(Post, post_id)
        if not post: abort(404)
        if post.author_id != current_user.id: abort(403)
        db.session.delete(post)
        db.session.commit()
        flash("Post deleted.", "info")
        return redirect(url_for("feed"))

    # --- Vote on post (AJAX + redirect fallback) ----------------------------

    @app.route("/post/<int:post_id>/vote", methods=["POST"])
    @login_required
    def vote_post(post_id):
        post = db.session.get(Post, post_id)
        if not post: abort(404)
        try:
            value = int(request.form.get("value", 0))
        except (ValueError, TypeError):
            abort(400)
        if value not in (1, -1): abort(400)

        existing = PostVote.query.filter_by(user_id=current_user.id, post_id=post_id).first()
        if existing:
            if existing.value == value:
                db.session.delete(existing)
            else:
                existing.value = value
        else:
            db.session.add(PostVote(user_id=current_user.id, post_id=post_id, value=value))
        db.session.commit()

        # Refresh post and get current state
        db.session.refresh(post)
        current_vote = PostVote.query.filter_by(user_id=current_user.id, post_id=post_id).first()
        my_vote = current_vote.value if current_vote else 0

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(ok=True, likes=post.like_count(), dislikes=post.dislike_count(), my_vote=my_vote)
        return redirect(request.referrer or url_for("feed"))

    # --- Comment ------------------------------------------------------------

    @app.route("/post/<int:post_id>/comment", methods=["POST"])
    @login_required
    def add_comment(post_id):
        post = db.session.get(Post, post_id)
        if not post: abort(404)
        content = request.form.get("content", "").strip()
        if not content:
            flash("Comment cannot be empty.", "warning")
            return redirect(url_for("feed"))
        db.session.add(Comment(content=content, post_id=post_id, author_id=current_user.id))
        db.session.commit()
        flash("Comment added!", "success")
        return redirect(request.referrer or url_for("feed"))

    # --- Vote on comment (AJAX + redirect fallback) -------------------------

    @app.route("/comment/<int:comment_id>/vote", methods=["POST"])
    @login_required
    def vote_comment(comment_id):
        comment = db.session.get(Comment, comment_id)
        if not comment: abort(404)
        try:
            value = int(request.form.get("value", 0))
        except (ValueError, TypeError):
            abort(400)
        if value not in (1, -1): abort(400)

        existing = CommentVote.query.filter_by(user_id=current_user.id, comment_id=comment_id).first()
        if existing:
            if existing.value == value:
                db.session.delete(existing)
            else:
                existing.value = value
        else:
            db.session.add(CommentVote(user_id=current_user.id, comment_id=comment_id, value=value))
        db.session.commit()

        db.session.refresh(comment)
        cur = CommentVote.query.filter_by(user_id=current_user.id, comment_id=comment_id).first()
        my_vote = cur.value if cur else 0

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(ok=True, likes=comment.like_count(), dislikes=comment.dislike_count(), my_vote=my_vote)
        return redirect(request.referrer or url_for("feed"))

    # =========================================================================
    # Hackathon Team Finder
    # =========================================================================

    @app.route("/hackathon")
    @login_required
    def hackathon():
        posts = HackathonPost.query.order_by(HackathonPost.timestamp.desc()).all()
        # Map: has the current user already applied?
        applied_ids = {a.post_id for a in HackathonApplication.query.filter_by(applicant_id=current_user.id).all()}
        return render_template("hackathon.html", posts=posts, applied_ids=applied_ids)

    @app.route("/hackathon/create", methods=["POST"])
    @login_required
    def create_hackathon_post():
        f = request.form

        hackathon_name  = f.get("hackathon_name", "").strip()
        team_name       = f.get("team_name", "").strip() or None
        topic_decided   = f.get("topic_decided") == "yes"
        theme           = f.get("theme", "").strip() or None
        prob_stmt       = f.get("problem_statement", "").strip() or None

        try:
            total_members  = int(f.get("total_members", 0))
            exist_count    = int(f.get("existing_members_count", 0))
        except (ValueError, TypeError):
            flash("Invalid member counts.", "danger")
            return redirect(url_for("hackathon"))

        errors = []
        if not hackathon_name:                         errors.append("Hackathon name is required.")
        if total_members < 2:                          errors.append("Total members must be ≥ 2.")
        if exist_count < 0:                            errors.append("Existing members cannot be negative.")
        if exist_count >= total_members:               errors.append("Existing members must be less than total members (you need to be looking for someone!).")
        if topic_decided and not theme:                errors.append("Enter a theme if topic is decided.")
        if topic_decided and not prob_stmt:            errors.append("Enter a problem statement if topic is decided.")

        if errors:
            for e in errors: flash(e, "danger")
            return redirect(url_for("hackathon"))

        # Build existing members JSON
        members = []
        leader_index = f.get("leader_index", "0")
        try: leader_index = int(leader_index)
        except: leader_index = 0

        for i in range(exist_count):
            name = f.get(f"member_name_{i}", "").strip()
            desc = f.get(f"member_desc_{i}", "").strip()
            members.append({
                "name": name or f"Member {i+1}",
                "description": desc,
                "is_leader": (i == leader_index),
            })

        required_skills = f.get("required_skills", "").strip() or None

        post = HackathonPost(
            hackathon_name         = hackathon_name,
            team_name              = team_name,
            topic_decided          = topic_decided,
            theme                  = theme if topic_decided else None,
            problem_statement      = prob_stmt if topic_decided else None,
            total_members          = total_members,
            existing_members_count = exist_count,
            existing_members_json  = json.dumps(members) if members else None,
            required_skills        = required_skills,
            author_id              = current_user.id,
        )
        db.session.add(post)
        db.session.commit()
        flash("Your hackathon post is live! 🚀", "success")
        return redirect(url_for("hackathon"))

    @app.route("/hackathon/<int:post_id>/delete", methods=["POST"])
    @login_required
    def delete_hackathon_post(post_id):
        post = db.session.get(HackathonPost, post_id)
        if not post: abort(404)
        if post.author_id != current_user.id: abort(403)
        db.session.delete(post)
        db.session.commit()
        flash("Post deleted.", "info")
        return redirect(url_for("hackathon"))

    @app.route("/hackathon/<int:post_id>/apply", methods=["POST"])
    @login_required
    def apply_hackathon(post_id):
        post = db.session.get(HackathonPost, post_id)
        if not post: abort(404)
        if post.author_id == current_user.id:
            flash("You cannot apply to your own post.", "warning")
            return redirect(url_for("hackathon"))
        if HackathonApplication.query.filter_by(post_id=post_id, applicant_id=current_user.id).first():
            flash("You have already applied to this post.", "info")
            return redirect(url_for("hackathon"))
        message = request.form.get("message", "").strip()
        if not message:
            flash("Write a short message with your application.", "warning")
            return redirect(url_for("hackathon"))
        db.session.add(HackathonApplication(post_id=post_id, applicant_id=current_user.id, message=message))
        db.session.commit()
        flash("Application submitted! Good luck 🎉", "success")
        return redirect(url_for("hackathon"))

    # =========================================================================
    # Applications manager (hackathon posts)
    # =========================================================================

    @app.route("/applications")
    @login_required
    def applications():
        my_posts = HackathonPost.query.filter_by(author_id=current_user.id).all()
        my_post_ids = [p.id for p in my_posts]
        apps = (HackathonApplication.query
                .filter(HackathonApplication.post_id.in_(my_post_ids))
                .order_by(HackathonApplication.timestamp.desc()).all()) if my_post_ids else []
        grouped  = defaultdict(list)
        post_map = {p.id: p for p in my_posts}
        for a in apps:
            grouped[a.post_id].append(a)
        return render_template("applications.html", grouped=grouped, post_map=post_map, total=len(apps))

    @app.route("/application/<int:app_id>/<action>", methods=["POST"])
    @login_required
    def manage_application(app_id, action):
        application = db.session.get(HackathonApplication, app_id)
        if not application: abort(404)
        if application.hackathon_post.author_id != current_user.id: abort(403)
        if action == "accept":
            application.status = "accepted"
            flash(f"Accepted @{application.applicant.username}'s application 🎉", "success")
        elif action == "reject":
            application.status = "rejected"
            flash(f"Rejected @{application.applicant.username}'s application.", "info")
        else:
            abort(400)
        db.session.commit()
        return redirect(url_for("applications"))

    # =========================================================================
    # Messages (WIP)
    # =========================================================================

    @app.route("/messages")
    @login_required
    def messages():
        return render_template("messages.html")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
