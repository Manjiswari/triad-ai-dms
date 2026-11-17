from datetime import datetime
from bson import ObjectId
from flask import Blueprint, request, jsonify, g
from ..db import Database
from ..auth import token_required, optional_token
from ..utils import serialize_doc

access_bp = Blueprint("access", __name__, url_prefix="/api/access")

@access_bp.route("/request", methods=["POST"])
@optional_token
def request_access():
    data = request.get_json(silent=True) or request.form.to_dict()
    if not data:
        return jsonify({"error": "Request body must be valid JSON", "status": 400}), 400

    doc_id = data.get("doc_id")
    if not doc_id:
        return jsonify({"error": "Field 'doc_id' is required", "status": 400}), 400

    try:
        oid = ObjectId(doc_id)
    except Exception:
        return jsonify({"error": "Invalid doc_id format", "status": 400}), 400

    docs_col = Database.get_collection("documents")
    doc = docs_col.find_one({"_id": oid})
    if not doc:
        return jsonify({"error": "Target document not found", "status": 404}), 404

    user = getattr(g, "current_user", None)
    if not user:
        user = {
            "_id": ObjectId(),
            "username": data.get("username", "test_requester"),
            "division": data.get("division", "Division B"),
            "role": "user"
        }

    doc_division = doc.get("division", "")
    user_division = user.get("division", "")

    if doc_division == user_division:
        return jsonify({
            "message": "User is in the same division and already has full download access",
            "already_granted": True,
            "status": "approved"
        }), 200

    requests_col = Database.get_collection("access_requests")
    existing = requests_col.find_one({
        "doc_id": oid,
        "requester_id": user.get("_id"),
        "status": {"$in": ["pending", "approved"]}
    })
    if existing:
        return jsonify({
            "message": f"An access request with status '{existing['status']}' already exists",
            "request_id": str(existing["_id"]),
            "status": existing["status"]
        }), 200

    reason = data.get("reason", "Business necessity for cross-division access")
    request_doc = {
        "doc_id": oid,
        "document_title": doc.get("title", doc.get("filename", "Untitled")),
        "document_filename": doc.get("filename", ""),
        "document_division": doc_division,
        "requester_id": user.get("_id"),
        "requester_username": user.get("username", "user"),
        "requester_division": user_division,
        "reason": reason,
        "status": "pending",
        "created_at": datetime.utcnow()
    }

    result = requests_col.insert_one(request_doc)
    request_doc["_id"] = result.inserted_id

    return jsonify({
        "message": "Access request submitted successfully",
        "request_id": str(request_doc["_id"]),
        "status": "pending",
        "request": serialize_doc(request_doc)
    }), 201

@access_bp.route("/approve", methods=["POST"])
@optional_token
def approve_access():
    data = request.get_json(silent=True) or request.form.to_dict()
    if not data:
        return jsonify({"error": "Request body must be valid JSON", "status": 400}), 400

    request_id = data.get("request_id")
    if not request_id:
        return jsonify({"error": "Field 'request_id' is required", "status": 400}), 400

    try:
        oid = ObjectId(request_id)
    except Exception:
        return jsonify({"error": "Invalid request_id format", "status": 400}), 400

    requests_col = Database.get_collection("access_requests")
    req = requests_col.find_one({"_id": oid})
    if not req:
        return jsonify({"error": "Access request not found", "status": 404}), 404

    target_status = data.get("status", "approved").strip().lower()
    if target_status not in ("approved", "rejected"):
        target_status = "approved"

    comments = data.get("comments", f"Request {target_status} by division reviewer")
    user = getattr(g, "current_user", None)
    if user:
        is_admin = (user.get("role") == "admin")
        is_document_division = (user.get("division") == req.get("document_division"))
        if not (is_admin or is_document_division):
            return jsonify({
                "error": f"Permission denied: Only users or admins in '{req.get('document_division')}' can approve this request",
                "status": 403
            }), 403
        reviewer_name = user.get("username")
        reviewer_id = user.get("_id")
    else:
        reviewer_name = "division_reviewer"
        reviewer_id = None

    requests_col.update_one(
        {"_id": oid},
        {"$set": {
            "status": target_status,
            "reviewed_by": reviewer_name,
            "reviewed_by_id": reviewer_id,
            "reviewed_at": datetime.utcnow(),
            "comments": comments
        }}
    )

    updated_req = requests_col.find_one({"_id": oid})
    return jsonify({
        "message": f"Access request {target_status} successfully",
        "request_id": str(oid),
        "status": target_status,
        "request": serialize_doc(updated_req)
    }), 200

@access_bp.route("/requests", methods=["GET"])
@token_required
def list_requests():
    user = g.current_user
    req_type = request.args.get("type", "all").lower()
    requests_col = Database.get_collection("access_requests")
    incoming, outgoing = [], []
    user_division = user.get("division")
    is_admin = (user.get("role") == "admin")

    if req_type in ("all", "incoming"):
        incoming_query = {} if is_admin else {"document_division": user_division}
        incoming = list(requests_col.find(incoming_query).sort("created_at", -1))

    if req_type in ("all", "outgoing"):
        outgoing = list(requests_col.find({"requester_id": user.get("_id")}).sort("created_at", -1))

    if req_type == "incoming":
        return jsonify({"requests": serialize_doc(incoming), "total": len(incoming)}), 200
    elif req_type == "outgoing":
        return jsonify({"requests": serialize_doc(outgoing), "total": len(outgoing)}), 200

    return jsonify({
        "incoming": serialize_doc(incoming),
        "outgoing": serialize_doc(outgoing),
        "incoming_count": len(incoming),
        "outgoing_count": len(outgoing)
    }), 200
