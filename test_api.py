import os
import json
import time
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000/api")
REPORT_FILE = "test_report.txt"

results = {"total": 0, "passed": 0, "failed": 0, "errors": []}

def log_result(test_name, success, error_msg=""):
    results["total"] += 1
    if success:
        results["passed"] += 1
        print(f"  [PASS] {test_name}")
    else:
        results["failed"] += 1
        print(f"  [FAIL] {test_name}: {error_msg}")
        results["errors"].append(f"[{test_name}] FAILED: {error_msg}")

def run_tests():
    sample_pdf_path = "test_sample.pdf"
    if not os.path.exists(sample_pdf_path):
        with open(sample_pdf_path, "wb") as f:
            f.write(b"%PDF-1.4\nCONFIDENTIAL FINANCIAL AUDIT REPORT 2024\n%%EOF")

    tokens = {}
    doc_ids = {}

    user_a = f"alice_{int(time.time())}"
    reg_a = requests.post(f"{BASE_URL}/auth/register", json={
        "username": user_a, "email": f"{user_a}@diva.com", "password": "Password@123", "division": "Division A"
    })
    if reg_a.status_code in [200, 201]:
        tokens["user_a"] = reg_a.json()["token"]
        log_result("POST /api/auth/register (Division A)", True)
    else:
        log_result("POST /api/auth/register (Division A)", False, reg_a.text)

    user_b = f"bob_{int(time.time())}"
    reg_b = requests.post(f"{BASE_URL}/auth/register", json={
        "username": user_b, "email": f"{user_b}@divb.com", "password": "Password@123", "division": "Division B"
    })
    if reg_b.status_code in [200, 201]:
        tokens["user_b"] = reg_b.json()["token"]
        log_result("POST /api/auth/register (Division B)", True)
    else:
        log_result("POST /api/auth/register (Division B)", False, reg_b.text)

    headers_a = {"Authorization": f"Bearer {tokens.get('user_a')}"}
    with open(sample_pdf_path, "rb") as f:
        files = {"file": ("test_sample.pdf", f, "application/pdf")}
        data = {"metadata": json.dumps({"Division": "Division A", "Report Type": "Financial"})}
        upload_res = requests.post(f"{BASE_URL}/documents/upload", files=files, data=data, headers=headers_a)
        if upload_res.status_code in [200, 201]:
            doc_ids["doc_a"] = upload_res.json()["doc_id"]
            log_result("POST /api/documents/upload", True)
        else:
            log_result("POST /api/documents/upload", False, upload_res.text)

    # Starter compatibility test without auth
    with open(sample_pdf_path, "rb") as f:
        files = {"file": ("test_sample.pdf", f, "application/pdf")}
        data = {"metadata": json.dumps({"Division": "Division A", "Report Type": "Financial"})}
        starter_res = requests.post(f"{BASE_URL}/documents/upload", files=files, data=data)
        log_result("POST /api/documents/upload (Starter unauth contract)", starter_res.status_code in [200, 201])

    # RBAC upload test: Division A user cannot upload to Division B
    with open(sample_pdf_path, "rb") as f:
        files = {"file": ("illegal.pdf", f, "application/pdf")}
        data = {"metadata": json.dumps({"Division": "Division B", "Report Type": "Financial"})}
        illegal_res = requests.post(f"{BASE_URL}/documents/upload", files=files, data=data, headers=headers_a)
        log_result("RBAC: Prevent cross-division upload (403)", illegal_res.status_code == 403)

    # Cross division download test
    headers_b = {"Authorization": f"Bearer {tokens.get('user_b')}"}
    unauth_dl = requests.get(f"{BASE_URL}/documents/{doc_ids.get('doc_a')}/download", headers=headers_b)
    log_result("RBAC: Prevent cross-division download without approval (403)", unauth_dl.status_code == 403)

    # Access request & approval
    req_res = requests.post(f"{BASE_URL}/access/request", json={"doc_id": doc_ids.get("doc_a"), "reason": "Review"}, headers=headers_b)
    if req_res.status_code in [200, 201]:
        req_id = req_res.json().get("request_id")
        log_result("POST /api/access/request", True)
        app_res = requests.post(f"{BASE_URL}/access/approve", json={"request_id": req_id, "status": "approved"}, headers=headers_a)
        log_result("POST /api/access/approve", app_res.status_code == 200)
        auth_dl = requests.get(f"{BASE_URL}/documents/{doc_ids.get('doc_a')}/download", headers=headers_b)
        log_result("GET /api/documents/<id>/download (Post-approval)", auth_dl.status_code == 200)
    else:
        log_result("POST /api/access/request", False, req_res.text)

    # Filtering & Search
    f_res = requests.get(f"{BASE_URL}/documents?Report Type=Financial", headers=headers_a)
    log_result("GET /api/documents?Report Type=Financial", f_res.status_code == 200)

    s_res = requests.get(f"{BASE_URL}/search?q=CONFIDENTIAL")
    log_result("GET /api/search?q=CONFIDENTIAL", s_res.status_code == 200)

    with open(REPORT_FILE, "w") as f:
        f.write(f"=== BACKEND API TEST REPORT ===\nTotal: {results['total']}\nPassed: {results['passed']}\nFailed: {results['failed']}\n")

if __name__ == "__main__":
    run_tests()
