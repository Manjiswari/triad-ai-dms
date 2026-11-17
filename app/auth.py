import os
import hashlib
import hmac
from datetime import datetime, timedelta
from functools import wraps
import jwt
from flask import request, jsonify, g, current_app
from bson import ObjectId

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"{salt.hex()}:{key.hex()}"

def verify_password(password: str, password_hash: str) -> bool:
    try:
        parts = password_hash.split(":")
        if len(parts) != 2:
            return False
        salt = bytes.fromhex(parts[0])
        expected_key = bytes.fromhex(parts[1])
        new_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return hmac.compare_digest(new_key, expected_key)
    except Exception:
        return False

def generate_token(user: dict) -> str:
    from .config import Config
    secret = current_app.config.get("JWT_SECRET", Config.JWT_SECRET) if current_app else Config.JWT_SECRET
    expiry = datetime.utcnow() + (current_app.config.get("JWT_EXPIRY", Config.JWT_EXPIRY) if current_app else Config.JWT_EXPIRY)
    
    payload = {
        "sub": str(user["_id"]),
        "username": user.get("username", ""),
        "email": user.get("email", ""),
        "division": user.get("division", ""),
        "role": user.get("role", "user"),
        "exp": expiry,
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, secret, algorithm="HS256")

def decode_token(token: str) -> dict:
    from .config import Config
    secret = current_app.config.get("JWT_SECRET", Config.JWT_SECRET) if current_app else Config.JWT_SECRET
    return jwt.decode(token, secret, algorithms=["HS256"])

def get_token_from_request():
    auth_header = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        elif len(parts) == 1:
            return parts[0]
            
    token = request.args.get("token")
    if token:
        return token
        
    return request.cookies.get("dms_token")

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_from_request()
        if not token:
            return jsonify({"error": "Authorization token is missing", "status": 401}), 401

        try:
            payload = decode_token(token)
            from .db import Database
            user_id = payload.get("sub")
            try:
                oid = ObjectId(user_id)
            except Exception:
                oid = user_id
            user = Database.get_collection("users").find_one({"_id": oid})
            if not user:
                return jsonify({"error": "User belonging to token no longer exists", "status": 401}), 401
            g.current_user = user
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired. Please log in again.", "status": 401}), 401
        except jwt.InvalidTokenError as e:
            return jsonify({"error": f"Invalid authentication token: {str(e)}", "status": 401}), 401
        except Exception as e:
            return jsonify({"error": f"Authentication failed: {str(e)}", "status": 401}), 401

        return f(*args, **kwargs)
    return decorated

def optional_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        g.current_user = None
        token = get_token_from_request()
        if token:
            try:
                payload = decode_token(token)
                from .db import Database
                user_id = payload.get("sub")
                try:
                    oid = ObjectId(user_id)
                except Exception:
                    oid = user_id
                user = Database.get_collection("users").find_one({"_id": oid})
                if user:
                    g.current_user = user
            except Exception:
                g.current_user = None
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    @token_required
    def decorated(*args, **kwargs):
        if g.current_user.get("role") != "admin":
            return jsonify({"error": "Admin privileges required for this action", "status": 403}), 403
        return f(*args, **kwargs)
    return decorated
