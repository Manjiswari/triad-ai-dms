import re
from flask import Blueprint, request, jsonify, g
from ..db import Database
from ..auth import optional_token
from ..utils import serialize_doc, generate_search_snippet, get_user_document_access_info

search_bp = Blueprint("search", __name__, url_prefix="/api/search")

@search_bp.route("", methods=["GET"])
@optional_token
def search_documents():
    query_str = (request.args.get("q") or "").strip()
    division_filter = request.args.get("division", "").strip()
    report_type_filter = request.args.get("Report Type", "").strip()

    docs_col = Database.get_collection("documents")
    fields_col = Database.get_collection("custom_fields")
    user = getattr(g, "current_user", None)
    all_fields = list(fields_col.find())
    dynamic_field_names = [f["name"] for f in all_fields]

    if not query_str:
        filter_q = {}
        if division_filter:
            filter_q["division"] = division_filter
        if report_type_filter:
            filter_q["metadata.Report Type"] = report_type_filter

        docs = list(docs_col.find(filter_q).sort("created_at", -1))
        results = []
        for d in docs:
            item = serialize_doc(d)
            access_info = get_user_document_access_info(user, d)
            item.update(access_info)
            item["snippet"] = (d.get("extracted_text") or "")[:200]
            item["match_sources"] = ["All documents"]
            results.append(item)

        return jsonify({
            "query": "",
            "results": results,
            "total": len(results)
        }), 200

    escaped = re.escape(query_str)
    regex = {"$regex": escaped, "$options": "i"}

    or_conditions = [
        {"title": regex},
        {"filename": regex},
        {"extracted_text": regex},
        {"division": regex}
    ]

    for field_name in dynamic_field_names:
        or_conditions.append({f"metadata.{field_name}": regex})

    mongo_query = {"$or": or_conditions}
    if division_filter:
        mongo_query = {"$and": [{"division": division_filter}, {"$or": or_conditions}]}

    matched_docs = list(docs_col.find(mongo_query).sort("created_at", -1))

    results = []
    for doc in matched_docs:
        item = serialize_doc(doc)
        access_info = get_user_document_access_info(user, doc)
        item.update(access_info)

        sources = []
        pattern = re.compile(escaped, re.IGNORECASE)

        if pattern.search(doc.get("title", "")):
            sources.append("Document Title")
        if pattern.search(doc.get("filename", "")):
            sources.append("Filename")
        if pattern.search(doc.get("extracted_text", "")):
            sources.append("OCR Extracted Text")
        if pattern.search(doc.get("division", "")):
            sources.append("Division")

        for k, v in doc.get("metadata", {}).items():
            if pattern.search(str(v)):
                sources.append(f"Metadata: {k}")

        snippet = generate_search_snippet(doc.get("extracted_text", ""), query_str, context_len=180)
        item["snippet"] = snippet
        item["match_sources"] = sources
        results.append(item)

    return jsonify({
        "query": query_str,
        "results": results,
        "total": len(results)
    }), 200
