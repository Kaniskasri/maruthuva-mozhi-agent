"""
Maruthuva Mozhi — document ingestion and clinical field extraction.
Built with the AWS User Group Madurai Strands Decider hackathon kit.

Two public functions:
    ingest_uploaded_file(file_bytes, filename) -> dict
    extract_clinical_fields(raw_text) -> dict

No LLM, no decider, no file storage. Pure Python + regex + optional libraries.
"""

from __future__ import annotations

import re
import io
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# ingest_uploaded_file
# ---------------------------------------------------------------------------

def ingest_uploaded_file(file_bytes: bytes, filename: str) -> dict:
    """
    Accept raw file bytes and a filename, return extracted text and metadata.

    Returns:
        {
            "raw_text": str,
            "method": str,          # 'text' | 'pdf_parse' | 'ocr' | 'ocr_unavailable' | 'unsupported'
            "filename": str,
            "page_count": int,
            "confidence": float | None,
        }

    Never stores the file. Always returns a dict with raw_text.
    """
    ext = Path(filename).suffix.lower()

    if ext == ".txt":
        return _ingest_text(file_bytes, filename)
    elif ext == ".pdf":
        return _ingest_pdf(file_bytes, filename)
    elif ext in (".png", ".jpg", ".jpeg"):
        return _ingest_image(file_bytes, filename)
    else:
        return {
            "raw_text": f"Unsupported file type '{ext}'. Please paste text or upload a .txt, .pdf, .png, .jpg, or .jpeg file.",
            "method": "unsupported",
            "filename": filename,
            "page_count": 0,
            "confidence": None,
        }


def _ingest_text(file_bytes: bytes, filename: str) -> dict:
    try:
        raw_text = file_bytes.decode("utf-8", errors="replace")
    except Exception as exc:
        raw_text = f"Could not decode text file: {exc}"
    return {
        "raw_text": raw_text,
        "method": "text",
        "filename": filename,
        "page_count": 1,
        "confidence": None,
    }


def _ingest_pdf(file_bytes: bytes, filename: str) -> dict:
    # --- attempt pdfminer parse first ---
    text = ""
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract  # type: ignore

        text = pdfminer_extract(io.BytesIO(file_bytes)) or ""
    except ImportError:
        text = ""
    except Exception:
        text = ""

    non_ws = len(re.sub(r"\s", "", text))
    if non_ws >= 20:
        return {
            "raw_text": text,
            "method": "pdf_parse",
            "filename": filename,
            "page_count": _count_pdf_pages(file_bytes),
            "confidence": None,
        }

    # --- fall back to OCR ---
    return _ocr_pdf(file_bytes, filename)


def _ocr_pdf(file_bytes: bytes, filename: str) -> dict:
    try:
        from pdf2image import convert_from_bytes  # type: ignore
        import pytesseract  # type: ignore
        from pytesseract import TesseractNotFoundError  # type: ignore

        try:
            images = convert_from_bytes(file_bytes)
        except Exception as exc:
            return {
                "raw_text": f"PDF-to-image conversion failed: {exc}",
                "method": "ocr",
                "filename": filename,
                "page_count": 0,
                "confidence": None,
            }

        pages_text = []
        confidences = []
        for img in images:
            page_text = pytesseract.image_to_string(img)
            pages_text.append(page_text)
            try:
                data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                confs = [c for c in data["conf"] if isinstance(c, (int, float)) and c >= 0]
                if confs:
                    confidences.append(sum(confs) / len(confs))
            except Exception:
                pass

        avg_conf = (sum(confidences) / len(confidences)) if confidences else None
        return {
            "raw_text": "\n\n".join(pages_text),
            "method": "ocr",
            "filename": filename,
            "page_count": len(images),
            "confidence": avg_conf,
        }

    except ImportError:
        return {
            "raw_text": "Tesseract not installed — OCR unavailable; please paste text instead",
            "method": "ocr_unavailable",
            "filename": filename,
            "page_count": 0,
            "confidence": None,
        }
    except Exception as exc:  # includes TesseractNotFoundError via pytesseract
        if "TesseractNotFoundError" in type(exc).__name__ or "tesseract" in str(exc).lower():
            return {
                "raw_text": "Tesseract not installed — OCR unavailable; please paste text instead",
                "method": "ocr_unavailable",
                "filename": filename,
                "page_count": 0,
                "confidence": None,
            }
        return {
            "raw_text": f"OCR failed: {exc}",
            "method": "ocr",
            "filename": filename,
            "page_count": 0,
            "confidence": None,
        }


def _ingest_image(file_bytes: bytes, filename: str) -> dict:
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore

        img = Image.open(io.BytesIO(file_bytes))
        text = pytesseract.image_to_string(img)

        avg_conf: Optional[float] = None
        try:
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            confs = [c for c in data["conf"] if isinstance(c, (int, float)) and c >= 0]
            if confs:
                avg_conf = sum(confs) / len(confs)
        except Exception:
            pass

        return {
            "raw_text": text,
            "method": "ocr",
            "filename": filename,
            "page_count": 1,
            "confidence": avg_conf,
        }

    except ImportError:
        return {
            "raw_text": "Tesseract not installed — OCR unavailable; please paste text instead",
            "method": "ocr_unavailable",
            "filename": filename,
            "page_count": 0,
            "confidence": None,
        }
    except Exception as exc:
        if "TesseractNotFoundError" in type(exc).__name__ or "tesseract" in str(exc).lower():
            return {
                "raw_text": "Tesseract not installed — OCR unavailable; please paste text instead",
                "method": "ocr_unavailable",
                "filename": filename,
                "page_count": 0,
                "confidence": None,
            }
        return {
            "raw_text": f"Image OCR failed: {exc}",
            "method": "ocr",
            "filename": filename,
            "page_count": 1,
            "confidence": None,
        }


def _count_pdf_pages(file_bytes: bytes) -> int:
    """Best-effort PDF page count without requiring extra libs."""
    try:
        from pdfminer.high_level import extract_pages  # type: ignore

        return sum(1 for _ in extract_pages(io.BytesIO(file_bytes)))
    except Exception:
        pass
    # fallback: count /Page objects in raw bytes
    try:
        count = len(re.findall(rb"/Type\s*/Page\b", file_bytes))
        return count if count > 0 else 1
    except Exception:
        return 1


# ---------------------------------------------------------------------------
# extract_clinical_fields
# ---------------------------------------------------------------------------

# Known drug names (representative subset for regex alternation)
_KNOWN_DRUGS = [
    "Amoxicillin", "Paracetamol", "Metformin", "Atorvastatin", "Cetirizine",
    "Omeprazole", "Ibuprofen", "Metronidazole", "Azithromycin", "Amlodipine",
    "Aspirin", "Lisinopril", "Losartan", "Clopidogrel", "Pantoprazole",
    "Ranitidine", "Ciprofloxacin", "Doxycycline", "Prednisolone", "Hydrocortisone",
    "Salbutamol", "Montelukast", "Levocetirizine", "Fexofenadine", "Domperidone",
    "Ondansetron", "Diclofenac", "Naproxen", "Tramadol", "Codeine",
    "Insulin", "Glibenclamide", "Glipizide", "Sitagliptin", "Empagliflozin",
    "Rosuvastatin", "Simvastatin", "Warfarin", "Rivaroxaban", "Apixaban",
    "Amitriptyline", "Sertraline", "Escitalopram", "Fluoxetine", "Quetiapine",
    "Clonazepam", "Alprazolam", "Lorazepam", "Diazepam", "Phenytoin",
    "Carbamazepine", "Valproate", "Levetiracetam", "Gabapentin", "Pregabalin",
]

_DRUG_PATTERN = re.compile(
    r"\b(?:"
    + "|".join(re.escape(d) for d in _KNOWN_DRUGS)
    + r"|[A-Z][a-z]{3,}(?:\s+[A-Z][a-z]{2,})?)\b"
    r"(?=\s+\d|\s+\(|\s*\d)",  # followed by dose or paren — helps reduce FP
    re.IGNORECASE,
)

# Also catch "word + mg/mcg/ml" patterns to find unlisted drug names
_DRUG_WITH_DOSE_PATTERN = re.compile(
    r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\s+\d+(?:\.\d+)?\s*(?:mg|mcg|ml|g|IU|units?)\b",
    re.IGNORECASE,
)

_DOSAGE_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|ml|g|IU|units?)\b",
    re.IGNORECASE,
)

_FREQUENCY_PATTERN = re.compile(
    r"\b(?:once\s+daily|twice\s+daily|three\s+times\s+daily|thrice\s+daily|"
    r"every\s+\d+\s+hours?|four\s+times\s+daily|"
    r"OD|BD|TDS|QID|BID|PRN|SOS)\b",
    re.IGNORECASE,
)

_DURATION_PATTERN = re.compile(
    r"\b(?:for\s+)?\d+\s*(?:days?|weeks?|months?|years?)\b",
    re.IGNORECASE,
)

# ISO, day/month/year slash, and written-out date formats
_DATE_PATTERN = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b"                               # 2025-01-15
    r"|\b\d{1,2}/\d{1,2}/\d{4}\b"                          # 15/01/2025
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b"
    r"|\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\b",
    re.IGNORECASE,
)

_WARNING_PATTERN = re.compile(
    r"(?i)(?:^|\b)(?:[^\n]*\b(?:warning|stop\s+if|do\s+not|avoid|CALL|EMERGENCY|immediately)\b[^\n]*)",
    re.MULTILINE,
)

_UNREADABLE_PATTERN = re.compile(
    r"\[illegible\]|\?\?\?|\[unclear\]|\billegible\b|\bnot\s+readable\b",
    re.IGNORECASE,
)


def extract_clinical_fields(raw_text: str) -> dict:
    """
    Regex-based extraction of clinical fields from raw text.

    Returns:
        {
            "drug_names":          list[str],
            "dosages":             list[str],
            "frequencies":         list[str],
            "durations":           list[str],
            "dates":               list[str],
            "warnings":            list[str],
            "unreadable_sections": list[str],
        }

    Missing fields are empty lists. No LLM or inference.
    """
    # --- drug names ---
    drug_set: set[str] = set()

    # Known drug names (case-insensitive match, preserve original casing)
    known_pat = re.compile(
        r"\b(?:" + "|".join(re.escape(d) for d in _KNOWN_DRUGS) + r")\b",
        re.IGNORECASE,
    )
    for m in known_pat.finditer(raw_text):
        drug_set.add(m.group(0))

    # Capitalised word(s) immediately before a dosage
    for m in _DRUG_WITH_DOSE_PATTERN.finditer(raw_text):
        drug_set.add(m.group(1).strip())

    drug_names = sorted(drug_set, key=lambda s: raw_text.index(s) if s in raw_text else 0)

    # --- dosages ---
    dosages = list(dict.fromkeys(m.group(0) for m in _DOSAGE_PATTERN.finditer(raw_text)))

    # --- frequencies ---
    frequencies = list(dict.fromkeys(m.group(0) for m in _FREQUENCY_PATTERN.finditer(raw_text)))

    # --- durations ---
    durations = list(dict.fromkeys(m.group(0) for m in _DURATION_PATTERN.finditer(raw_text)))

    # --- dates ---
    dates = list(dict.fromkeys(m.group(0) for m in _DATE_PATTERN.finditer(raw_text)))

    # --- warnings ---
    warnings: list[str] = []
    for m in _WARNING_PATTERN.finditer(raw_text):
        line = m.group(0).strip()
        if line and line not in warnings:
            warnings.append(line)

    # --- unreadable sections ---
    unreadable_sections = list(dict.fromkeys(m.group(0) for m in _UNREADABLE_PATTERN.finditer(raw_text)))

    return {
        "drug_names": drug_names,
        "dosages": dosages,
        "frequencies": frequencies,
        "durations": durations,
        "dates": dates,
        "warnings": warnings,
        "unreadable_sections": unreadable_sections,
    }
