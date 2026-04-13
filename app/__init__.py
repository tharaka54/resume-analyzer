"""
app/__init__.py — Flask Application Factory
Wires up all blueprints, extensions, and middleware
"""

import os
from flask import Flask
from flask_cors import CORS
from flask_sock import Sock
from flask_talisman import Talisman

from app.config import Config
from app.extensions import limiter


sock = Sock()


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ── Extensions ────────────────────────────────────────────────────────────
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
    sock.init_app(app)
    limiter.init_app(app)     # NFR #9 — rate limiting via Flask-Limiter

    # ── Security Headers (Flask-Talisman) ─────────────────────────────────────
    # Content Security Policy — restricts which resources the browser can load.
    # Tighten 'script-src' / 'style-src' further when you remove inline scripts.
    csp = {
        "default-src":    ["'self'"],
        "script-src":     ["'self'", "'unsafe-inline'"],   # adjust when inline JS removed
        "style-src":      ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
        "font-src":       ["'self'", "https://fonts.gstatic.com"],
        "img-src":        ["'self'", "data:", "https:"],   # allow profile pictures over HTTPS
        "connect-src":    ["'self'"],
        "frame-ancestors":["'none'"],                      # blocks all iframe embedding
        "object-src":     ["'none'"],
        "base-uri":       ["'self'"],
    }

    force_https = app.config.get("FORCE_HTTPS", False)

    Talisman(
        app,
        force_https=force_https,                        # Redirect HTTP→HTTPS (prod only)
        strict_transport_security=force_https,          # HSTS header
        strict_transport_security_max_age=31536000,     # 1 year
        content_security_policy=csp,
        x_content_type_options=True,                    # X-Content-Type-Options: nosniff
        x_xss_protection=True,                         # X-XSS-Protection: 1; mode=block
        frame_options="DENY",                           # X-Frame-Options: DENY
        referrer_policy="strict-origin-when-cross-origin",
        session_cookie_secure=force_https,
        session_cookie_http_only=True,
    )

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
