
# Triad AI - Document Management System (DMS)
### Take-Home Assignment Submission - Full Stack Developer Internship

A Document Management System (DMS) built with **Python & Flask**, **MongoDB & GridFS**, **Role-Based Access Control (RBAC)**, **Optical Character Recognition (OCR)**, and **Dynamic Custom Metadata**.

---

## 🚀 Key Features Implemented

1. **Dynamic Custom Metadata**:
   - Tag documents with custom extensible key-value pairs (`Division`, `Report Type`, etc.).
   - Metadata fields are dynamically registered, configurable, editable, and filterable at runtime without hardcoding.

2. **Role-Based Access Control (RBAC) & Division Isolation**:
   - Strict division isolation: Users belonging to `Division A` can only upload documents to `Division A`.
   - By default, users within the same division can view and download their division's documents.
   - Cross-division document downloads are strictly denied (HTTP 403) unless an access request has been approved.

3. **Cross-Division Access Request Workflow**:
   - Users from `Division B` can request access to documents in `Division A` with a justification reason.
   - Division members/admins from `Division A` receive the request in an **Access Requests Inbox** and can **Approve** or **Reject** it.
   - Upon approval, the requesting user is authorized to download the document.

4. **OCR & Search Engine Pipeline**:
   - Uploading a PDF or Image automatically triggers the OCR engine (`pytesseract`, `pypdf`, fallback extractors).
   - Extracted OCR text is stored, indexed, and searchable via full-text keyword search (`GET /api/search?q=<query>`).

5. **MongoDB & GridFS File Storage**:
   - Binary files are stored in MongoDB GridFS (`fs.files` and `fs.chunks`).
   - Seamless streaming download endpoint (`GET /api/documents/<doc_id>/download`) with access verification.
   - Automatic in-memory mock fallback allows running immediately without requiring a local MongoDB daemon.

6. **All 6 Required UI Views**:
   - **Authentication (`/login`)**: Login & Registration with division assignment and demo logins.
   - **Dashboard / Document Hub (`/`)**: Main hub with filters for `Division` and `Report Type`, document cards, OCR preview, and upload modal.
   - **Document Details (`/documents/<doc_id>`)**: Shows metadata and OCR text, dynamic action button (`Download` or `Request Access`).
   - **Access Requests Inbox (`/requests`)**: Division review inbox to approve/reject incoming requests.
   - **Advanced Search Page (`/search`)**: Full-text search across titles, dynamic metadata, and OCR-extracted text with highlighted excerpts.
   - **Admin / Settings Page (`/admin`)**: Interface to create, edit, and configure custom metadata fields.

---

## ⚡ Quick Setup & Execution Guide

1. **Navigate into the project directory:**
   ```bash
   cd C:\Users\VITAP\Downloads\triad
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the Flask Application Server:**
   ```bash
   python run.py
   ```
   *Open `http://localhost:5000` in your browser.*

4. **Run the Automated Tests:**
   ```bash
   python smoke_test.py
   ```
   Or with the server running:
   ```bash
   python test_api.py
   ```

5. **Run with Docker:**
   ```bash
   docker-compose up --build
   ```

---

## 👤 Pre-configured Demo Accounts

- **`alice`** / `Alice@123` (`Division A` user)
- **`bob`** / `Bob@123` (`Division B` user)
- **`admin`** / `Admin@123` (Admin user)


