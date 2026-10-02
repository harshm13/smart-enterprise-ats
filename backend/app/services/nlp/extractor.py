import io
import logging
import re
from pathlib import Path

import docx
from pdfminer.high_level import extract_text as pdf_extract
from pdfminer.layout import LAParams
from pdfminer.pdfparser import PDFSyntaxError

logger = logging.getLogger(__name__)


def clean_text(raw_text: str) -> str:
    """
    Cleans and normalizes extracted resume text:
    - Normalizes line breaks and whitespace
    - Standardizes bullet points to a common marker
    - Strips non-printable ASCII and control characters
    - Collapses 3+ consecutive newlines to 2
    """
    if not raw_text:
        return ""

    # Replace null bytes and non-printable control characters (except newline, tab, return)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", " ", raw_text)

    # Standardize bullet point symbols
    text = re.sub(r"[\u2022\u2023\u25E6\u2043\u2219\u25CB\u25CF\u25AA\u25AB]", "\n• ", text)

    # Replace Windows carriage returns and form feeds
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Normalize multiple horizontal whitespaces/tabs (preserve newlines)
    text = re.sub(r"[ \t]+", " ", text)

    # Collapse excessive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extracts text from PDF bytes using pdfminer.six with layout analysis.
    Preserves multi-column reading order.
    """
    laparams = LAParams(
        line_margin=0.5,
        word_margin=0.1,
        char_margin=2.0,
        boxes_flow=0.5,
        detect_vertical=False,
    )
    with io.BytesIO(file_bytes) as stream:
        try:
            text = pdf_extract(stream, laparams=laparams)
        except PDFSyntaxError as e:
            logger.error("Corrupted or invalid PDF syntax: %s", e)
            raise ValueError(f"Corrupted or invalid PDF document: {e}") from e
        except Exception as e:
            logger.error("Failed to parse PDF: %s", e)
            raise ValueError(f"Could not extract text from PDF: {e}") from e

    return clean_text(text)


def extract_text_from_docx(file_bytes: bytes) -> str:
    """
    Extracts text from DOCX (Word) documents including paragraphs and tables.
    """
    with io.BytesIO(file_bytes) as stream:
        try:
            doc = docx.Document(stream)
        except Exception as e:
            logger.error("Failed to parse DOCX: %s", e)
            raise ValueError(f"Invalid or corrupted Word (.docx) document: {e}") from e

    lines: list[str] = []

    # Extract paragraph text
    for para in doc.paragraphs:
        p_text = para.text.strip()
        if p_text:
            lines.append(p_text)

    # Extract table text (many resumes format experience or skills in tables)
    for table in doc.tables:
        for row in table.rows:
            row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_cells:
                lines.append(" | ".join(row_cells))

    full_text = "\n".join(lines)
    return clean_text(full_text)


def extract_text(file_bytes: bytes, file_name: str) -> str:
    """
    Routes extraction based on file extension and magic byte signatures.
    """
    suffix = Path(file_name).suffix.lower()

    # Check magic bytes
    if file_bytes.startswith(b"%PDF"):
        return extract_text_from_pdf(file_bytes)
    elif file_bytes.startswith(b"PK\x03\x04") or suffix == ".docx":
        return extract_text_from_docx(file_bytes)
    elif suffix == ".pdf":
        return extract_text_from_pdf(file_bytes)
    elif suffix == ".txt":
        return clean_text(file_bytes.decode("utf-8", errors="replace"))
    else:
        raise ValueError(f"Unsupported file format for '{file_name}'. Only PDF and DOCX are supported.")
