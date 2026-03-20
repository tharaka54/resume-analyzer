"""
app/__init__.py — Flask Application Factory
Wires up all blueprints, extensions, and middleware
"""

import os
from flask import Flask
from flask_cors import CORS
from flask_sock import Sock

from app.config import Config


sock = Sock()


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ── Extensions ────────────────────────────────────────────────────────────
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
    sock.init_app(app)

    # ── Blueprints ────────────────────────────────────────────────────────────
    from app.routes.oauth import oauth_bp
    from app.routes.jobs import jobs_bp
    from app.routes.resumes import resumes_bp
    from app.routes.ranking import ranking_bp
    from app.routes.ws_ranking import ws_bp
    from app.routes.quiz import quiz_bp

    app.register_blueprint(oauth_bp,   url_prefix="/auth")
    app.register_blueprint(jobs_bp,    url_prefix="/jobs")
    app.register_blueprint(resumes_bp, url_prefix="/resumes")
    app.register_blueprint(ranking_bp, url_prefix="/ranking")
    app.register_blueprint(ws_bp)
    app.register_blueprint(quiz_bp, url_prefix="/quiz")

    # ── Frontend Routes ───────────────────────────────────────────────────────
    from flask import render_template
    
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def catch_all(path):
        return render_template("index.html")

    # ── Health check ──────────────────────────────────────────────────────────
    @app.route("/health")
    def health():
        return {"status": "ok", "service": "HireIQ API"}, 200

    return app
