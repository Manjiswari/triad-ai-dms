from datetime import datetime
from flask import Blueprint, request, jsonify, g
from ..db import Database
from ..auth import hash_password, verify_password, generate_token, token_required
from ..utils import serialize_doc

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or request.form.to_dict()
    if not data:
        return jsonify({"error": "Request body must be valid JSON", "status": 400}), 400

    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    division = (data.get("division") or "").strip()
    role = data.get("role", "user").strip().lower()

    if not username or not email:
        return jsonify({"error": "Username and Email are required", "status": 400}), 400
    if not password or len(password) < 4:
        return jsonify({"error": "Password must be at least 4 characters long", "status": 400}), 400
    if not division:
        return jsonify({"error": "Division is required", "status": 400}), 400

    if role not in ("user", "admin"):
        role = "user"

    users_col = Database.get_collection("users")
    if users_col.find_one({"username": username}):
        return jsonify({"error": f"Username '{username}' is already taken", "status": 409}), 409
    if users_col.find_one({"email": email}):
        return jsonify({"error": f"Email '{email}' is already registered", "status": 409}), 409

    divisions_col = Database.get_collection("divisions")
    if not divisions_col.find_one({"name": division}):
        divisions_col.insert_one({"name": division, "created_at": datetime.utcnow()})

    user_doc = {
        "username": username,
        "email": email,
        "password_hash": hash_password(password),
        "division": division,
        "role": role,
        "created_at": datetime.utcnow()
    }
    result = users_col.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    token = generate_token(user_doc)
    safe_user = {
        "id": str(user_doc["_id"]),
        "username": user_doc["username"],
        "email": user_doc["email"],
        "division": user_doc["division"],
        "role": user_doc["role"],
        "created_at": user_doc["created_at"].isoformat()
    }

    return jsonify({
        "message": "User registered successfully",
        "token": token,
        "user": safe_user
    }), 201

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or request.form.to_dict()
    if not data:
        return jsonify({"error": "Request body must be valid JSON", "status": 400}), 400

    identifier = (data.get("username") or data.get("email") or "").strip()
    password = data.get("password") or ""

    if not identifier or not password:
        return jsonify({"error": "Username/email and password are required", "status": 400}), 400

    users_col = Database.get_collection("users")
    user = users_col.find_one({
        "$or": [
            {"username": identifier},
            {"email": identifier.lower()}
        ]
    })

    if not user or not verify_password(password, user.get("password_hash", "")):
        return jsonify({"error": "Invalid username or password", "status": 401}), 401

    token = generate_token(user)
    safe_user = {
        "id": str(user["_id"]),
        "username": user["username"],
        "email": user["email"],
        "division": user["division"],
        "role": user.get("role", "user")
    }

    return jsonify({
        "message": "Login successful",
        "token": token,
        "user": safe_user
    }), 200

@auth_bp.route("/me", methods=["GET"])
@token_required
def get_current_user():
    user = g.current_user
    return jsonify({
        "user": {
            "id": str(user["_id"]),
            "username": user["username"],
            "email": user["email"],
            "division": user["division"],
            "role": user.get("role", "user"),
            "created_at": user.get("created_at", datetime.utcnow()).isoformat()
        }
    }), 200
