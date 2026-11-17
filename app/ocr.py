import io
import re
import string
import logging
from PIL import Image

logger = logging.getLogger(__name__)

try:
    import pytesseract
    HAS_PYTESSERACT = True
except ImportError:
    HAS_PYTESSERACT = False

try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

def extract_printable_text(raw_bytes: bytes) -> str:
    try:
        decoded = raw_bytes.decode("utf-8", errors="ignore")
        printable = set(string.printable)
        filtered = "".join([c if c in printable else " " for c in decoded])
        words = [w for w in filtered.split() if len(w) > 2 and not w.startswith("%")]
        return " ".join(words[:200])
    except Exception:
        return ""

def extract_text_from_pdf(file_bytes: bytes) -> tuple[str, str]:
    extracted = []
    if HAS_PYPDF:
        try:
            stream = io.BytesIO(file_bytes)
            reader = pypdf.PdfReader(stream)
            for idx, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    extracted.append(page_text.strip())
            combined = "\n\n".join(extracted).strip()
            if combined:
                return combined, "pypdf"
        except Exception as e:
            logger.debug(f"pypdf extraction notice: {e}")

    fallback = extract_printable_text(file_bytes)
    if fallback:
        return fallback, "binary_string_extractor"
    return "", "none"

def extract_text_from_image(file_bytes: bytes) -> tuple[str, str]:
    if not HAS_PYTESSERACT:
        return "", "tesseract_not_installed"
    try:
        image = Image.open(io.BytesIO(file_bytes))
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        text = pytesseract.image_to_string(image)
        return text.strip(), "tesseract_ocr"
    except pytesseract.TesseractNotFoundError:
        logger.warning("Tesseract binary not found on system PATH. OCR skipped.")
        return "", "tesseract_binary_missing"
    except Exception as e:
        logger.warning(f"Error during image OCR: {e}")
        return "", "ocr_error"

def process_document_ocr(file_bytes: bytes, filename: str, content_type: str = "") -> dict:
    filename_lower = filename.lower()
    text = ""
    method = "unknown"
    status = "completed"

    try:
        if filename_lower.endswith(".pdf") or "pdf" in content_type:
            text, method = extract_text_from_pdf(file_bytes)
        elif any(filename_lower.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"]) or "image" in content_type:
            text, method = extract_text_from_image(file_bytes)
        elif filename_lower.endswith(".txt") or "text/plain" in content_type:
            try:
                text = file_bytes.decode("utf-8", errors="ignore").strip()
                method = "plaintext"
            except Exception:
                text = ""
                method = "plaintext_failed"
        else:
            text = extract_printable_text(file_bytes)
            method = "fallback"

        if not text:
            status = "empty" if method in ("pypdf", "plaintext", "tesseract_ocr") else "skipped"

        words = re.findall(r"\b\w+\b", text)
        word_count = len(words)

        return {
            "text": text,
            "status": status,
            "method": method,
            "word_count": word_count
        }
    except Exception as e:
        logger.error(f"Unexpected error in process_document_ocr: {e}", exc_info=True)
        return {
            "text": "",
            "status": "failed",
            "method": "exception",
            "word_count": 0,
            "error": str(e)
        }
