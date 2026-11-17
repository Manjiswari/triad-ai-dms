from datetime import datetime
from bson import ObjectId
from flask import Blueprint, request, jsonify, g
from ..db import Database
from ..auth import optional_token, token_required, admin_required
from ..utils import serialize_doc

field_bp = Blueprint("fields", __name__, url_prefix="/api")

@field_bp.route("/fields", methods=["GET"])
def get_fields():
    fields_col = Database.get_collection("custom_fields")
    fields = list(fields_col.find().sort("created_at", 1))
    return jsonify({"fields": serialize_doc(fields), "total": len(fields)}), 200

@field_bp.route("/fields", methods=["POST"])
@optional_token
def create_field():
    data = request.get_json(silent=True) or request.form.to_dict()
    if not data:
        return jsonify({"error": "Request body must be valid JSON", "status": 400}), 400

    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Field 'name' is required", "status": 400}), 400

    label = (data.get("label") or name).strip()
    field_type = (data.get("type") or "text").strip().lower()
    if field_type not in ("text", "select", "number", "date"):
        field_type = "text"

    raw_options = data.get("options") or []
    if isinstance(raw_options, str):
        options = [opt.strip() for opt in raw_options.split(",") if opt.strip()]
    elif isinstance(raw_options, list):
        options = [str(opt).strip() for opt in raw_options if str(opt).strip()]
    else:
        options = []

    required = bool(data.get("required", False))
    description = data.get("description", "")

    fields_col = Database.get_collection("custom_fields")
    if fields_col.find_one({"name": name}):
        return jsonify({"error": f"A dynamic field with name '{name}' already exists", "status": 409}), 409

    field_doc = {
        "name": name,
        "label": label,
        "type": field_type,
        "options": options,
        "required": required,
        "is_system": False,
        "description": description,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    result = fields_col.insert_one(field_doc)
    field_doc["_id"] = result.inserted_id

    return jsonify({
        "message": f"Dynamic field '{name}' created successfully",
        "field": serialize_doc(field_doc)
    }), 201

@field_bp.route("/fields/<field_id>", methods=["PUT"])
@optional_token
def update_field(field_id):
    try:
        oid = ObjectId(field_id)
    except Exception:
        return jsonify({"error": "Invalid field ID format", "status": 400}), 400

    fields_col = Database.get_collection("custom_fields")
    field = fields_col.find_one({"_id": oid})
    if not field:
        return jsonify({"error": "Dynamic field not found", "status": 404}), 404

    data = request.get_json(silent=True) or request.form.to_dict()
    update_data = {"updated_at": datetime.utcnow()}

    if "label" in data:
        update_data["label"] = str(data["label"]).strip()
    if "type" in data and data["type"] in ("text", "select", "number", "date"):
        update_data["type"] = data["type"]
    if "required" in data:
        update_data["required"] = bool(data["required"])
    if "description" in data:
        update_data["description"] = str(data["description"]).strip()

    if "options" in data:
        raw_options = data["options"]
        if isinstance(raw_options, str):
            update_data["options"] = [opt.strip() for opt in raw_options.split(",") if opt.strip()]
        elif isinstance(raw_options, list):
            update_data["options"] = [str(opt).strip() for opt in raw_options if str(opt).strip()]

    fields_col.update_one({"_id": oid}, {"$set": update_data})
    updated = fields_col.find_one({"_id": oid})

    return jsonify({
        "message": "Field updated successfully",
        "field": serialize_doc(updated)
    }), 200

@field_bp.route("/fields/<field_id>", methods=["DELETE"])
@optional_token
def delete_field(field_id):
    try:
        oid = ObjectId(field_id)
    except Exception:
        return jsonify({"error": "Invalid field ID format", "status": 400}), 400

    fields_col = Database.get_collection("custom_fields")
    field = fields_col.find_one({"_id": oid})
    if not field:
        return jsonify({"error": "Field not found", "status": 404}), 404

    if field.get("is_system"):
        return jsonify({"error": "System fields cannot be deleted", "status": 400}), 400

    fields_col.delete_one({"_id": oid})
    return jsonify({"message": f"Field '{field.get('name')}' deleted successfully"}), 200

@field_bp.route("/divisions", methods=["GET"])
def get_divisions():
    div_col = Database.get_collection("divisions")
    divs = list(div_col.find().sort("name", 1))
    names = [d["name"] for d in divs]
    return jsonify({"divisions": names, "total": len(names)}), 200

@field_bp.route("/divisions", methods=["POST"])
@optional_token
def create_division():
    data = request.get_json(silent=True) or request.form.to_dict()
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Division name is required", "status": 400}), 400

    div_col = Database.get_collection("divisions")
    if div_col.find_one({"name": name}):
        return jsonify({"error": f"Division '{name}' already exists", "status": 409}), 409

    div_col.insert_one({"name": name, "created_at": datetime.utcnow()})
    return jsonify({"message": f"Division '{name}' added successfully", "division": name}), 201
