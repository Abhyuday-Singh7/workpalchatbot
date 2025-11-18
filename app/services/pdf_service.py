from pathlib import Path

import fitz  # PyMuPDF


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract plain text from a PDF using PyMuPDF.
    """
    doc = fitz.open(pdf_path)
    text_chunks = []
    for page in doc:
        text_chunks.append(page.get_text())
    doc.close()
    return "\n".join(text_chunks)

