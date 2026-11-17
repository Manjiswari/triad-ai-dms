import io
import json
import logging
from datetime import datetime
from bson import ObjectId
from flask import Blueprint, request, jsonify, g, send_file
from werkzeug.utils import secure_filename
from ..db import Database
from ..auth import optional_token, token_required
from ..ocr import process_document_ocr
from ..utils import serialize_doc, can_user_access_document, get_user_document_access_info

logger = logging.getLogger(__name__)
doc_bp = Blueprint("documents", __name__, url_prefix="/api/documents")

@doc_bp.route("/upload", methods=["POST"])
@optional_token
def upload_document():
    if "file" not in request.files:
        return jsonify({"error": "No file part in the request", "status": 400}), 400

    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"error": "No file selected for upload", "status": 400}), 400

    filename = secure_filename(file.filename) or "uploaded_document.pdf"
    content_type = file.content_type or "application/octet-stream"
    file_bytes = file.read()
    file_size = len(file_bytes)

    metadata = {}
    raw_metadata = request.form.get("metadata")
    if raw_metadata:
        try:
            if isinstance(raw_metadata, str):
                metadata = json.loads(raw_metadata)
            elif isinstance(raw_metadata, dict):
                metadata = raw_metadata
        except Exception as e:
            return jsonify({"error": f"Invalid JSON in metadata field: {str(e)}", "status": 400}), 400

    for k, v in request.form.items():
        if k not in ("file", "metadata"):
            try:
                metadata[k] = json.loads(v)
            except Exception:
                metadata[k] = v

    user = getattr(g, "current_user", None)
    requested_division = metadata.get("Division") or metadata.get("division") or request.form.get("division")
    
    if user:
        user_division = user.get("division", "Division A")
        user_role = user.get("role", "user")
        if user_role != "admin" and requested_division and requested_division.strip() != user_division.strip():
            return jsonify({
                "error": f"Division isolation violation: Users in '{user_division}' can only upload to '{user_division}', not '{requested_division}'",
                "status": 403
            }), 403
            
        division = user_division
        uploaded_by_id = user.get("_id")
        uploader_name = user.get("username", "user")
    else:
        division = requested_division or "Division A"
        uploaded_by_id = None
        uploader_name = "automated_test"

    metadata["Division"] = division
    title = request.form.get("title") or metadata.get("Title") or metadata.get("title") or filename

    ocr_result = process_document_ocr(file_bytes, filename, content_type)

    try:
        gridfs_file_id = Database.fs.put(
            file_bytes,
            filename=filename,
            content_type=content_type,
            division=division,
            upload_date=datetime.utcnow()
        )
    except Exception as e:
        logger.error(f"Failed to store file in GridFS: {e}")
        return jsonify({"error": f"Failed to store file in GridFS: {str(e)}", "status": 500}), 500

    docs_col = Database.get_collection("documents")
    doc_record = {
        "title": title,
        "filename": filename,
        "file_id": gridfs_file_id,
        "file_size": file_size,
        "content_type": content_type,
        "division": division,
        "uploaded_by": uploaded_by_id,
        "uploader_name": uploader_name,
        "metadata": metadata,
        "extracted_text": ocr_result.get("text", ""),
        "ocr_status": ocr_result.get("status", "completed"),
        "ocr_method": ocr_result.get("method", "unknown"),
        "word_count": ocr_result.get("word_count", 0),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    result = docs_col.insert_one(doc_record)
    doc_record["_id"] = result.inserted_id

    fields_col = Database.get_collection("custom_fields")
    for key, val in metadata.items():
        if key not in ("Division", "division") and isinstance(key, str):
            existing = fields_col.find_one({"name": key})
            if not existing:
                fields_col.insert_one({
                    "name": key,
                    "label": key,
                    "type": "text",
                    "options": [str(val)] if val else [],
                    "required": False,
                    "is_system": False,
                    "created_at": datetime.utcnow()
                })

    return jsonify({
        "message": "Document uploaded and OCR processed successfully",
        "doc_id": str(doc_record["_id"]),
        "document": serialize_doc(doc_record)
    }), 201

@doc_bp.route("", methods=["GET"])
@optional_token
def list_documents():
    user = getattr(g, "current_user", None)
    docs_col = Database.get_collection("documents")
    query = {}
    user_division = user.get("division") if user else None
    user_role = user.get("role") if user else None

    if user and user_role != "admin":
        requests_col = Database.get_collection("access_requests")
        approved_requests = list(requests_col.find({
            "requester_id": user.get("_id"),
            "status": "approved"
        }))
        approved_doc_ids = [req.get("doc_id") for req in approved_requests if req.get("doc_id")]
        query["$or"] = [
            {"division": user_division},
            {"_id": {"$in": approved_doc_ids}}
        ]

    for param_key, param_value in request.args.items():
        if param_key in ("token", "limit", "skip", "page", "_"):
            continue
        if param_key.lower() == "division":
            query["division"] = param_value
        else:
            query[f"metadata.{param_key}"] = {"$regex": f"^{param_value}$", "$options": "i"}

    docs = list(docs_col.find(query).sort("created_at", -1))
    augmented = []
    for d in docs:
        item = serialize_doc(d)
        access_info = get_user_document_access_info(user, d)
        item.update(access_info)
        if "extracted_text" in item and len(item["extracted_text"] or "") > 300:
            item["extracted_text_preview"] = item["extracted_text"][:300] + "..."
        else:
            item["extracted_text_preview"] = item.get("extracted_text", "")
        augmented.append(item)

    return jsonify({
        "documents": augmented,
        "total": len(augmented),
        "user_division": user_division
    }), 200

@doc_bp.route("/<doc_id>", methods=["GET"])
@optional_token
def get_document(doc_id):
    try:
        oid = ObjectId(doc_id)
    except Exception:
        return jsonify({"error": "Invalid document ID format", "status": 400}), 400

    docs_col = Database.get_collection("documents")
    doc = docs_col.find_one({"_id": oid})
    if not doc:
        return jsonify({"error": "Document not found", "status": 404}), 404

    user = getattr(g, "current_user", None)
    serialized = serialize_doc(doc)
    access_info = get_user_document_access_info(user, doc)
    serialized.update(access_info)

    return jsonify({"document": serialized}), 200

@doc_bp.route("/<doc_id>/download", methods=["GET"])
@optional_token
def download_document(doc_id):
    try:
        oid = ObjectId(doc_id)
    except Exception:
        return jsonify({"error": "Invalid document ID format", "status": 400}), 400

    docs_col = Database.get_collection("documents")
    doc = docs_col.find_one({"_id": oid})
    if not doc:
        return jsonify({"error": "Document not found", "status": 404}), 404

    user = getattr(g, "current_user", None)
    has_access, reason = can_user_access_document(user, doc)

    if not has_access:
        if not user:
            return jsonify({"error": "Authentication required to download this document", "status": 401}), 401
        return jsonify({
            "error": "Access denied. Cross-division access request required.",
            "status": 403,
            "reason": reason,
            "document_division": doc.get("division"),
            "user_division": user.get("division")
        }), 403

    file_id = doc.get("file_id")
    try:
        grid_file = Database.fs.get(file_id)
        file_bytes = grid_file.read()
    except Exception as e:
        logger.error(f"Error reading file from GridFS: {e}")
        return jsonify({"error": f"Failed to retrieve file from storage: {str(e)}", "status": 500}), 500

    filename = doc.get("filename", "downloaded_file.pdf")
    content_type = doc.get("content_type", "application/octet-stream")

    return send_file(
        io.BytesIO(file_bytes),
        mimetype=content_type,
        as_attachment=True,
        download_name=filename
    )

@doc_bp.route("/<doc_id>", methods=["DELETE"])
@token_required
def delete_document(doc_id):
    try:
        oid = ObjectId(doc_id)
    except Exception:
        return jsonify({"error": "Invalid document ID format", "status": 400}), 400

    docs_col = Database.get_collection("documents")
    doc = docs_col.find_one({"_id": oid})
    if not doc:
        return jsonify({"error": "Document not found", "status": 404}), 404

    user = g.current_user
    is_admin = (user.get("role") == "admin")
    is_owner = (str(doc.get("uploaded_by")) == str(user.get("_id")))
    is_same_division = (doc.get("division") == user.get("division"))

    if not (is_admin or (is_same_division and is_owner)):
        return jsonify({"error": "Permission denied to delete this document", "status": 403}), 403

    file_id = doc.get("file_id")
    if file_id:
        try:
            Database.fs.delete(file_id)
        except Exception as e:
            logger.warning(f"Failed to delete GridFS file: {e}")

    docs_col.delete_one({"_id": oid})
    Database.get_collection("access_requests").delete_many({"doc_id": oid})
    return jsonify({"message": "Document deleted successfully"}), 200
