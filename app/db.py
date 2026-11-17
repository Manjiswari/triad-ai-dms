import io
import logging
from datetime import datetime
from bson import ObjectId
import pymongo
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure

logger = logging.getLogger(__name__)

class MockGridOut:
    def __init__(self, doc, chunks):
        self._doc = doc
        self._id = doc.get("_id")
        self.filename = doc.get("filename", "unknown")
        self.content_type = doc.get("contentType", "application/octet-stream")
        self.length = doc.get("length", 0)
        self.upload_date = doc.get("uploadDate", datetime.utcnow())
        self._data = b"".join([c.get("data", b"") for c in sorted(chunks, key=lambda x: x.get("n", 0))])
        self._pos = 0

    def read(self, size=-1):
        if size == -1:
            data = self._data[self._pos:]
            self._pos = len(self._data)
            return data
        data = self._data[self._pos:self._pos + size]
        self._pos += len(data)
        return data

    def seek(self, pos, whence=0):
        if whence == 0:
            self._pos = pos
        elif whence == 1:
            self._pos += pos
        elif whence == 2:
            self._pos = len(self._data) + pos
        self._pos = max(0, min(self._pos, len(self._data)))

    def tell(self):
        return self._pos


class MockGridFS:
    def __init__(self, database):
        self._db = database
        self._files = database["fs.files"]
        self._chunks = database["fs.chunks"]

    def put(self, data, filename=None, content_type=None, **kwargs):
        if isinstance(data, (io.BytesIO, io.BufferedReader)):
            raw_bytes = data.read()
        elif isinstance(data, bytes):
            raw_bytes = data
        elif isinstance(data, str):
            raw_bytes = data.encode("utf-8")
        else:
            raw_bytes = bytes(data)

        file_id = ObjectId()
        chunk_size = kwargs.get("chunk_size", 255 * 1024)
        chunks_count = (len(raw_bytes) + chunk_size - 1) // chunk_size if raw_bytes else 1

        for n in range(max(1, chunks_count)):
            chunk_data = raw_bytes[n * chunk_size:(n + 1) * chunk_size]
            self._chunks.insert_one({
                "files_id": file_id,
                "n": n,
                "data": chunk_data
            })

        file_doc = {
            "_id": file_id,
            "filename": filename or "unnamed",
            "contentType": content_type or "application/octet-stream",
            "length": len(raw_bytes),
            "chunkSize": chunk_size,
            "uploadDate": datetime.utcnow()
        }
        file_doc.update(kwargs)
        self._files.insert_one(file_doc)
        return file_id

    def get(self, file_id):
        if isinstance(file_id, str):
            try:
                file_id = ObjectId(file_id)
            except Exception:
                pass
        doc = self._files.find_one({"_id": file_id})
        if not doc:
            raise FileNotFoundError(f"File with id {file_id} not found in GridFS")
        chunks = list(self._chunks.find({"files_id": file_id}))
        return MockGridOut(doc, chunks)

    def delete(self, file_id):
        if isinstance(file_id, str):
            try:
                file_id = ObjectId(file_id)
            except Exception:
                pass
        self._files.delete_one({"_id": file_id})
        self._chunks.delete_many({"files_id": file_id})


class Database:
    client = None
    db = None
    fs = None
    is_mock = False

    @classmethod
    def initialize(cls, app):
        from .config import Config
        mongo_uri = app.config.get("MONGO_URI", Config.MONGO_URI)
        db_name = app.config.get("DB_NAME", Config.DB_NAME)
        use_mock = app.config.get("USE_MOCK_FALLBACK", Config.USE_MOCK_FALLBACK)

        try:
            logger.info(f"Connecting to MongoDB at {mongo_uri}...")
            client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
            client.admin.command("ping")
            cls.client = client
            cls.db = client[db_name]
            import gridfs
            cls.fs = gridfs.GridFS(cls.db)
            cls.is_mock = False
            logger.info("Connected to live MongoDB with native GridFS!")
        except Exception as e:
            if use_mock:
                logger.warning(f"Live MongoDB unavailable ({e}). Initializing in-memory Mock MongoDB...")
                import mongomock
                cls.client = mongomock.MongoClient()
                cls.db = cls.client[db_name]
                cls.fs = MockGridFS(cls.db)
                cls.is_mock = True
            else:
                raise e

        cls.ensure_indexes()
        cls.seed_defaults()

    @classmethod
    def ensure_indexes(cls):
        try:
            cls.db["users"].create_index("username", unique=True)
            cls.db["users"].create_index("email", unique=True)
            cls.db["documents"].create_index([("division", 1)])
            cls.db["access_requests"].create_index([("doc_id", 1), ("requester_id", 1)])
            cls.db["custom_fields"].create_index("name", unique=True)
        except Exception as e:
            logger.debug(f"Index creation notice: {e}")

    @classmethod
    def seed_defaults(cls):
        divisions_col = cls.db["divisions"]
        default_divisions = ["Division A", "Division B", "Division C", "Engineering", "Finance", "HR"]
        for div_name in default_divisions:
            if not divisions_col.find_one({"name": div_name}):
                divisions_col.insert_one({"name": div_name, "created_at": datetime.utcnow()})

        fields_col = cls.db["custom_fields"]
        default_fields = [
            {
                "name": "Report Type",
                "label": "Report Type",
                "type": "select",
                "options": ["Financial", "Technical", "Audit", "Operations", "Legal", "General"],
                "required": False,
                "is_system": False,
                "description": "Classification of the uploaded document",
                "created_at": datetime.utcnow()
            },
            {
                "name": "Confidentiality",
                "label": "Confidentiality Level",
                "type": "select",
                "options": ["Public", "Internal", "Confidential", "Strictly Confidential"],
                "required": False,
                "is_system": False,
                "description": "Sensitivity tier for the document",
                "created_at": datetime.utcnow()
            },
            {
                "name": "Project",
                "label": "Associated Project",
                "type": "text",
                "options": [],
                "required": False,
                "is_system": False,
                "description": "Project code or initiative name",
                "created_at": datetime.utcnow()
            },
            {
                "name": "Year",
                "label": "Fiscal Year",
                "type": "number",
                "options": [],
                "required": False,
                "is_system": False,
                "description": "Document year",
                "created_at": datetime.utcnow()
            }
        ]
        for field in default_fields:
            if not fields_col.find_one({"name": field["name"]}):
                fields_col.insert_one(field)

        from .auth import hash_password
        users_col = cls.db["users"]
        demo_users = [
            {
                "username": "admin",
                "email": "admin@triad-ai.com",
                "password_hash": hash_password("Admin@123"),
                "division": "Division A",
                "role": "admin",
                "created_at": datetime.utcnow()
            },
            {
                "username": "alice",
                "email": "alice@divisiona.com",
                "password_hash": hash_password("Alice@123"),
                "division": "Division A",
                "role": "user",
                "created_at": datetime.utcnow()
            },
            {
                "username": "bob",
                "email": "bob@divisionb.com",
                "password_hash": hash_password("Bob@123"),
                "division": "Division B",
                "role": "user",
                "created_at": datetime.utcnow()
            }
        ]
        for user in demo_users:
            if not users_col.find_one({"username": user["username"]}):
                users_col.insert_one(user)

    @classmethod
    def get_collection(cls, name):
        return cls.db[name]
