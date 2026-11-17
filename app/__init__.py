import os
from flask import Flask, jsonify, render_template
from flask_cors import CORS
from .config import Config
from .db import Database
from .routes.auth_routes import auth_bp
from .routes.doc_routes import doc_bp
from .routes.access_routes import access_bp
from .routes.search_routes import search_bp
from .routes.field_routes import field_bp

def create_app(config_class=Config):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_class)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    with app.app_context():
        Database.initialize(app)
        
    app.register_blueprint(auth_bp)
    app.register_blueprint(doc_bp)
    app.register_blueprint(access_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(field_bp)

    @app.route("/api/health", methods=["GET"])
    def health_check():
        return jsonify({
            "status": "healthy",
            "service": "Triad AI Document Management System (DMS)",
            "database": "mock_in_memory" if Database.is_mock else "mongodb_live",
            "version": "1.0.0"
        }), 200

    @app.route("/")
    def index_page():
        return render_template("dashboard.html")

    @app.route("/login")
    def login_page():
        return render_template("login.html")

    @app.route("/documents/<doc_id>")
    def doc_details_page(doc_id):
        return render_template("document_detail.html", doc_id=doc_id)

    @app.route("/requests")
    def requests_page():
        return render_template("requests.html")

    @app.route("/search")
    def search_page():
        return render_template("search.html")

    @app.route("/admin")
    def admin_page():
        return render_template("admin.html")

    return app
