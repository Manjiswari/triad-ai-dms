import re
from datetime import datetime
from bson import ObjectId

def serialize_doc(doc):
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize_doc(item) for item in doc]
    if isinstance(doc, dict):
        result = {}
        for k, v in doc.items():
            if k == "_id" and isinstance(v, ObjectId):
                result["id"] = str(v)
                result["_id"] = str(v)
            elif isinstance(v, ObjectId):
                result[k] = str(v)
            elif isinstance(v, datetime):
                result[k] = v.isoformat()
            elif isinstance(v, (dict, list)):
                result[k] = serialize_doc(v)
            else:
                result[k] = v
        return result
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, datetime):
        return doc.isoformat()
    return doc

def can_user_access_document(user: dict | None, document: dict) -> tuple[bool, str]:
    if not document:
        return False, "Document not found"
    if not user:
        return False, "Authentication required"
    if user.get("role") == "admin":
        return True, "admin"

    doc_division = document.get("division", "")
    user_division = user.get("division", "")
    if doc_division and user_division and doc_division == user_division:
        return True, "same_division"

    from .db import Database
    requests_col = Database.get_collection("access_requests")
    req = requests_col.find_one({
        "doc_id": document.get("_id"),
        "requester_id": user.get("_id"),
        "status": "approved"
    })
    if req:
        return True, "approved_request"

    return False, "cross_division_unauthorized"

def get_user_document_access_info(user: dict | None, document: dict) -> dict:
    if not document or not user:
        return {
            "can_download": False,
            "is_own_division": False,
            "request_status": None,
            "request_id": None
        }

    doc_division = document.get("division", "")
    is_own_division = (user.get("division") == doc_division)
    is_admin = (user.get("role") == "admin")

    if is_admin or is_own_division:
        return {
            "can_download": True,
            "is_own_division": is_own_division,
            "request_status": None,
            "request_id": None
        }

    from .db import Database
    requests_col = Database.get_collection("access_requests")
    req = requests_col.find_one({
        "doc_id": document.get("_id"),
        "requester_id": user.get("_id")
    }, sort=[("created_at", -1)])

    if req:
        status = req.get("status")
        return {
            "can_download": (status == "approved"),
            "is_own_division": False,
            "request_status": status,
            "request_id": str(req.get("_id"))
        }

    return {
        "can_download": False,
        "is_own_division": False,
        "request_status": None,
        "request_id": None
    }

def generate_search_snippet(text: str, query: str, context_len: int = 140) -> str:
    if not text or not query:
        return (text[:context_len] + "...") if text and len(text) > context_len else (text or "")

    pattern = re.compile(re.escape(query), re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return (text[:context_len] + "...") if len(text) > context_len else text

    start_idx = max(0, match.start() - context_len // 2)
    end_idx = min(len(text), match.end() + context_len // 2)

    prefix = "..." if start_idx > 0 else ""
    suffix = "..." if end_idx < len(text) else ""
    snippet = text[start_idx:end_idx]

    highlighted = pattern.sub(lambda m: f"<mark class='bg-yellow-200 text-yellow-900 font-semibold px-1 rounded'>{m.group(0)}</mark>", snippet)
    return f"{prefix}{highlighted}{suffix}"
