"""Content reader — extracts text/metadata from files for AI classification."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 — used at runtime

from src.shared.logging import get_logger

logger = get_logger(__name__)

# Maximum text length to send to the AI model
MAX_CONTENT_LENGTH = 2000


def extract_text_from_pdf(file_path: Path) -> str | None:
    """Extract text content from a PDF file using PyMuPDF.

    Args:
        file_path: Path to the PDF file.

    Returns:
        Extracted text, or None if extraction fails.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.warning("pymupdf_not_installed", hint="pip install pymupdf")
        return None

    try:
        doc = fitz.open(str(file_path))
        text_parts: list[str] = []
        # Read first few pages (enough for classification)
        for page_num in range(min(3, len(doc))):
            page = doc[page_num]
            text_parts.append(page.get_text())
        doc.close()

        text = "\n".join(text_parts).strip()
        return text[:MAX_CONTENT_LENGTH] if text else None
    except Exception:
        logger.debug("pdf_extraction_failed", file=str(file_path))
        return None


def extract_file_metadata(file_path: Path) -> dict[str, str]:
    """Extract useful metadata from a file for classification.

    This always works regardless of file type — uses filename, extension,
    size, etc. as classification hints.

    Args:
        file_path: Path to the file.

    Returns:
        Dictionary of metadata fields.
    """
    try:
        stat = file_path.stat()
        size_mb = stat.st_size / (1024 * 1024)
    except OSError:
        size_mb = 0.0

    return {
        "filename": file_path.name,
        "extension": file_path.suffix.lstrip(".").lower(),
        "stem": file_path.stem,
        "size_mb": f"{size_mb:.2f}",
    }


def get_file_context(file_path: Path) -> str:
    """Build a context string for AI classification.

    Combines metadata + extracted content (if available) into a prompt-ready string.

    Args:
        file_path: Path to the file.

    Returns:
        A formatted context string for the AI model.
    """
    metadata = extract_file_metadata(file_path)
    parts = [
        f"Filename: {metadata['filename']}",
        f"Extension: {metadata['extension']}",
        f"Size: {metadata['size_mb']} MB",
    ]

    # Try to extract content for supported types
    ext = metadata["extension"]
    content = None

    if ext == "pdf":
        content = extract_text_from_pdf(file_path)
    elif ext in ("txt", "md", "csv", "log", "json", "xml", "html"):
        content = _read_text_file(file_path)

    if content:
        parts.append(f"Content preview:\n{content}")

    return "\n".join(parts)


def _read_text_file(file_path: Path) -> str | None:
    """Read the first portion of a text file."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        return text[:MAX_CONTENT_LENGTH].strip() if text else None
    except OSError:
        return None
