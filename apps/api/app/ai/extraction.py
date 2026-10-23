"""Bounded plain-text extraction. Never execute macros, scripts or external links."""

from io import BytesIO
import re, unicodedata, zipfile
from defusedxml import ElementTree
from pypdf import PdfReader
from .safety import redact

MAX_BYTES = 10 * 1024 * 1024
MAX_TEXT = 120_000
MAX_CHUNKS = 100


class ExtractionError(Exception):
    pass


def sanitise(text):
    text = unicodedata.normalize("NFKC", text)
    text = "".join(
        c for c in text if c in "\n\t" or not unicodedata.category(c).startswith("C")
    )
    return redact(re.sub(r"[ \t]+", " ", text)).strip()


def extract(data, kind):
    if not data or len(data) > MAX_BYTES:
        raise ExtractionError("file_size")
    sections = []
    try:
        if kind == "txt":
            sections = [("Text", data.decode("utf-8-sig", errors="strict"))]
        elif kind == "pdf":
            if not data.startswith(b"%PDF-"):
                raise ExtractionError("file_type")
            reader = PdfReader(BytesIO(data), strict=True)
            if reader.is_encrypted or len(reader.pages) > 100:
                raise ExtractionError("pdf_limit")
            # Bound decompressed content streams before text extraction.
            for number, page in enumerate(reader.pages, 1):
                contents = page.get_contents()
                if contents is not None and len(contents.get_data()) > 2_000_000:
                    raise ExtractionError("pdf_limit")
                sections.append((f"Page {number}", page.extract_text() or ""))
                if sum(len(s[1]) for s in sections) > MAX_TEXT:
                    raise ExtractionError("text_limit")
        elif kind == "docx":
            with zipfile.ZipFile(BytesIO(data)) as archive:
                entries = archive.infolist()
                if (
                    len(entries) > 200
                    or sum(e.file_size for e in entries) > 20 * 1024 * 1024
                    or any(
                        e.flag_bits & 1 or e.file_size > 5 * 1024 * 1024
                        for e in entries
                    )
                ):
                    raise ExtractionError("docx_limit")
                if (
                    "[Content_Types].xml" not in archive.namelist()
                    or "word/document.xml" not in archive.namelist()
                ):
                    raise ExtractionError("file_type")
                if any(
                    "vbaProject" in e.filename
                    or e.filename.startswith(("word/embeddings/", "word/activeX/"))
                    for e in entries
                ):
                    raise ExtractionError("active_content")
                root = ElementTree.fromstring(archive.read("word/document.xml"))
                paragraphs = [
                    "".join(p.itertext())
                    for p in root.iter(
                        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
                    )
                ]
                sections = [("Document", "\n".join(paragraphs))]
        else:
            raise ExtractionError("file_type")
    except ExtractionError:
        raise
    except Exception:
        raise ExtractionError("extraction_failed") from None
    if sum(len(s[1]) for s in sections) > MAX_TEXT:
        raise ExtractionError("text_limit")
    chunks = []
    for locator, text in sections:
        text = sanitise(text)
        for start in range(0, len(text), 1200):
            part = text[start : start + 1400].strip()
            if part:
                chunks.append((locator, part))
    if not chunks:
        raise ExtractionError("no_text")
    if len(chunks) > MAX_CHUNKS:
        raise ExtractionError("chunk_limit")
    return chunks


def extract_isolated(data, kind):
    """Bound parser CPU/address space in a separate Linux worker process."""
    import json, subprocess, sys

    try:
        result = subprocess.run(
            [sys.executable, "-m", "app.ai.extract_worker", kind],
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=20,
            check=False,
        )
        if result.returncode or len(result.stdout) > 250_000:
            raise ExtractionError("extraction_failed")
        return [tuple(row) for row in json.loads(result.stdout)]
    except (subprocess.TimeoutExpired, ValueError):
        raise ExtractionError("extraction_failed") from None
