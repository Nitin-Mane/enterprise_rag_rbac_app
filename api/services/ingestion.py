import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.utils.text import slugify
from pypdf import PdfReader

from api.models import DataSource, DocumentChunk


OCR_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def chunk_text(text, size=850, overlap=120):
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    chunks = []
    start = 0
    while start < len(cleaned):
        end = min(start + size, len(cleaned))
        chunks.append(cleaned[start:end])
        if end == len(cleaned):
            break
        start = max(0, end - overlap)
    return chunks


def ocr_status():
    try:
        import pytesseract

        version = pytesseract.get_tesseract_version()
        return {"available": True, "engine": "tesseract", "version": str(version)}
    except Exception as exc:
        return {"available": False, "engine": "tesseract", "detail": str(exc)}


def ocr_image(image):
    import pytesseract

    return pytesseract.image_to_string(image)


def read_image(path):
    from PIL import Image

    with Image.open(path) as image:
        text = ocr_image(image)
    return [("1", text, {"parser": "ocr_image", "ocr_used": True})]


def ocr_pdf_page(path, page_index):
    import fitz
    from PIL import Image

    document = fitz.open(str(path))
    try:
        page = document.load_page(page_index)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
        return ocr_image(image)
    finally:
        document.close()


def read_pdf(path):
    reader = PdfReader(str(path))
    rows = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        metadata = {"parser": "pypdf", "ocr_used": False}
        if len(text.strip()) < 30:
            try:
                ocr_text = ocr_pdf_page(path, index - 1)
                if ocr_text.strip():
                    text = ocr_text
                    metadata = {"parser": "pypdf+ocr", "ocr_used": True}
            except Exception as exc:
                metadata = {"parser": "pypdf", "ocr_used": False, "ocr_error": str(exc)}
        rows.append((str(index), text, metadata))
    return rows


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row_index, row in enumerate(reader, start=1):
            rendered = "; ".join(f"{key}: {value}" for key, value in row.items())
            rows.append((str(row_index), rendered, {"parser": "csv", "ocr_used": False}))
        return rows


def read_json(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [
            (str(i + 1), json.dumps(item, ensure_ascii=True), {"parser": "json", "ocr_used": False})
            for i, item in enumerate(data)
        ]
    return [("1", json.dumps(data, ensure_ascii=True), {"parser": "json", "ocr_used": False})]


def read_sqlite_dump(path):
    rows = []
    connection = sqlite3.connect(path)
    try:
        cursor = connection.cursor()
        tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        for (table_name,) in tables:
            for row_index, row in enumerate(cursor.execute(f"SELECT * FROM {table_name}"), start=1):
                rows.append(
                    (
                        f"{table_name}:{row_index}",
                        f"{table_name} row {row_index}: {row}",
                        {"parser": "sqlite", "ocr_used": False},
                    )
                )
    finally:
        connection.close()
    return rows


def read_text(path):
    return [("1", Path(path).read_text(encoding="utf-8"), {"parser": "text", "ocr_used": False})]


READERS = {
    ".pdf": read_pdf,
    ".csv": read_csv,
    ".json": read_json,
    ".sqlite": read_sqlite_dump,
    ".db": read_sqlite_dump,
    ".txt": read_text,
    ".md": read_text,
    ".png": read_image,
    ".jpg": read_image,
    ".jpeg": read_image,
    ".tif": read_image,
    ".tiff": read_image,
    ".bmp": read_image,
    ".webp": read_image,
}


def source_type_for_path(path):
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".csv":
        return "csv"
    if suffix == ".json":
        return "json"
    if suffix in {".sqlite", ".db"}:
        return "sql"
    if suffix in OCR_EXTENSIONS:
        return "image"
    return "txt"


def normalize_row(row):
    if len(row) == 2:
        page, text = row
        metadata = {}
    else:
        page, text, metadata = row
    return page, text, metadata


def ingest_source(source):
    path = settings.BASE_DIR / source.path
    reader = READERS.get(path.suffix.lower(), read_text)
    DocumentChunk.objects.filter(source=source).delete()
    chunk_index = 0
    parser_details = []
    for row in reader(path):
        page, text, row_metadata = normalize_row(row)
        parser_details.append(row_metadata)
        for chunk in chunk_text(text):
            DocumentChunk.objects.create(
                source=source,
                chunk_index=chunk_index,
                title=source.title,
                content=chunk,
                page=page,
                metadata={
                    "source_type": source.source_type,
                    "sensitivity": source.sensitivity,
                    **row_metadata,
                },
            )
            chunk_index += 1
    return {"chunks": chunk_index, "parser_details": parser_details}


def ingest_all_sources():
    DocumentChunk.objects.all().delete()
    created = 0
    for source in DataSource.objects.all():
        result = ingest_source(source)
        created += result["chunks"]
    return created


def save_uploaded_source(uploaded_file, title, departments, roles, clearance, sensitivity, description):
    upload_root = settings.RAG_DATA_PATH / "uploads"
    upload_root.mkdir(parents=True, exist_ok=True)

    original_name = Path(uploaded_file.name)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_stem = slugify(original_name.stem) or "uploaded-source"
    filename = f"{timestamp}-{safe_stem}{original_name.suffix.lower()}"
    target = upload_root / filename

    with open(target, "wb") as handle:
        for chunk in uploaded_file.chunks():
            handle.write(chunk)

    source_id = f"UPLOAD-{timestamp}-{safe_stem[:24].upper()}"
    source = DataSource.objects.create(
        source_id=source_id,
        title=title or original_name.stem,
        source_type=source_type_for_path(target),
        path=str(target.relative_to(settings.BASE_DIR)).replace("\\", "/"),
        departments=departments or ["all"],
        allowed_roles=roles or ["all"],
        min_clearance=clearance,
        sensitivity=sensitivity or "internal",
        description=description or f"Uploaded source parsed from {original_name.name}",
    )
    result = ingest_source(source)
    return source, result
