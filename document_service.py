from __future__ import annotations

from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class DocumentService:
    """Extracts bounded text from supported local document formats."""

    SUPPORTED_SUFFIXES = {".pdf", ".docx"}

    def __init__(self, max_characters: int = 40_000):
        if max_characters <= 0:
            raise ValueError("max_characters musí být kladné číslo.")
        self.max_characters = max_characters

    def read(self, path: str | Path) -> str:
        document_path = Path(path)
        if document_path.suffix.lower() not in self.SUPPORTED_SUFFIXES:
            raise ValueError("Podporovány jsou pouze soubory PDF a DOCX.")
        if not document_path.is_file():
            raise FileNotFoundError(f"Dokument neexistuje: {document_path}")

        if document_path.suffix.lower() == ".pdf":
            text = self._read_pdf(document_path)
        else:
            text = self._read_docx(document_path)

        truncated = self.truncate(text)
        logger.info(
            "Dokument načten; typ=%s, zdrojových znaků=%d, použitých znaků=%d",
            document_path.suffix.lower(),
            len(text),
            len(truncated),
        )
        return truncated

    def truncate(self, text: str) -> str:
        normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        return normalized[: self.max_characters]

    @staticmethod
    def _read_pdf(path: Path) -> str:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("Pro čtení PDF nainstalujte balíček PyMuPDF.") from exc

        with fitz.open(path) as document:
            return "\n".join(page.get_text() for page in document)

    @staticmethod
    def _read_docx(path: Path) -> str:
        try:
            from docx import Document
        except ImportError as exc:
            raise RuntimeError("Pro čtení DOCX nainstalujte balíček python-docx.") from exc

        document = Document(path)
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
