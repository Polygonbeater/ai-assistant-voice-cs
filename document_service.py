from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json
import logging
import threading
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """Represents a text chunk extracted from a document with metadata."""
    doc_id: str
    doc_name: str
    chunk_index: int
    text: str
    file_path: str
    char_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "doc_name": self.doc_name,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "file_path": self.file_path,
            "char_count": self.char_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentChunk:
        return cls(
            doc_id=data.get("doc_id", ""),
            doc_name=data.get("doc_name", ""),
            chunk_index=int(data.get("chunk_index", 0)),
            text=data.get("text", ""),
            file_path=data.get("file_path", ""),
            char_count=int(data.get("char_count", len(data.get("text", "")))),
        )


def smart_chunk_text(text: str, chunk_size: int = 450, chunk_overlap: int = 50) -> list[str]:
    """
    Rozdělí text na menší logické bloky s definovaným překryvem (overlap).
    Preferuje přirozené hranice: odstavce, věty, řádky a mezery, aby nedocházelo
    k přerušení myšlenek na hranicích bloků.
    """
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    text_len = len(normalized)

    # Dělicí znaky v pořadí priority pro hledání konce bloku
    delimiters = ["\n\n", ".\n", ". ", "!\n", "! ", "?\n", "? ", "\n", "; ", ";\n"]

    while start < text_len:
        end = min(start + chunk_size, text_len)
        if end < text_len:
            # Hledáme přirozený zlom v druhé polovině zamýšleného okna
            search_start = start + max(1, chunk_size // 2)
            sub = normalized[search_start:end]

            split_pos = -1
            for delim in delimiters:
                pos = sub.rfind(delim)
                if pos != -1:
                    split_pos = pos + len(delim)
                    break

            if split_pos == -1:
                # Fallback na mezeru mezi slovy
                space_pos = sub.rfind(" ")
                if space_pos != -1:
                    split_pos = space_pos + 1

            if split_pos != -1:
                end = search_start + split_pos

        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_len:
            break

        # Výpočet začátku dalšího bloku se započtením překryvu
        target_next = max(start + 1, end - chunk_overlap)
        # Zarovnání začátku dalšího bloku na začátek slova
        while target_next < end and normalized[target_next] not in (" ", "\n", "\t"):
            target_next += 1
        while target_next < end and normalized[target_next] in (" ", "\n", "\t"):
            target_next += 1

        start = target_next if target_next > start else end

    return chunks


class DocumentService:
    """
    Robustní lokální RAG systém pro zpracování dokumentů a zdrojových kódů.
    Podporuje PDF, DOCX, Markdown, Python, JSON a další textové formáty.
    Poskytuje chytrý chunking s překryvem, lokální vektorové úložiště FAISS
    a CPU embedding model (all-MiniLM-L6-v2 přes sentence-transformers).
    """

    SUPPORTED_SUFFIXES = {
        ".pdf",
        ".docx",
        ".md",
        ".txt",
        ".py",
        ".json",
        ".csv",
        ".log",
        ".yaml",
        ".yml",
        ".toml",
        ".sh",
        ".bash",
        ".html",
        ".xml",
        ".css",
        ".js",
        ".ts",
    }

    def __init__(
        self,
        config: dict | None = None,
        storage_dir: str | Path | None = None,
        embedding_model: str = "all-MiniLM-L6-v2",
        chunk_size: int = 450,
        chunk_overlap: int = 50,
        top_k: int = 3,
        max_characters: int = 40_000,
    ):
        rag_cfg = (config or {}).get("rag", {})
        self.storage_dir = Path(storage_dir or rag_cfg.get("storage_dir", "rag_storage"))
        self.embedding_model_name = rag_cfg.get("embedding_model", embedding_model)
        self.chunk_size = int(rag_cfg.get("chunk_size", chunk_size))
        self.chunk_overlap = int(rag_cfg.get("chunk_overlap", chunk_overlap))
        self.top_k = int(rag_cfg.get("top_k", top_k))
        self.enabled = bool(rag_cfg.get("enabled", True))
        self.max_characters = max_characters

        self.embedding_dim = 384
        self._model = None
        self._index = None
        self.chunks: list[DocumentChunk] = []
        self.registry: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

        # Automatické načtení uloženého indexu, pokud existuje
        self._load_storage()

    def _ensure_model(self):
        """Lazy načtení modelu pro embeddings běžícího efektivně na CPU."""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        from sentence_transformers import SentenceTransformer
                        logger.info("Načítám CPU embedding model: %s", self.embedding_model_name)
                        self._model = SentenceTransformer(self.embedding_model_name, device="cpu")
                    except ImportError as exc:
                        raise RuntimeError(
                            "Pro vektorové embeddings nainstalujte: pip install sentence-transformers"
                        ) from exc
        return self._model

    def _ensure_index(self):
        """Zajistí existenci FAISS indexu."""
        if self._index is None:
            try:
                import faiss
                self._index = faiss.IndexFlatIP(self.embedding_dim)
            except ImportError as exc:
                raise RuntimeError("Pro vektorové vyhledávání nainstalujte: pip install faiss-cpu") from exc
        return self._index

    def _load_storage(self) -> None:
        """Načte index a metadata z disku."""
        try:
            import faiss
            index_path = self.storage_dir / "index.faiss"
            chunks_path = self.storage_dir / "chunks.json"
            registry_path = self.storage_dir / "registry.json"

            if index_path.is_file() and chunks_path.is_file():
                self._index = faiss.read_index(str(index_path))
                with chunks_path.open("r", encoding="utf-8") as f:
                    raw_chunks = json.load(f)
                    self.chunks = [DocumentChunk.from_dict(c) for c in raw_chunks]

                if registry_path.is_file():
                    with registry_path.open("r", encoding="utf-8") as f:
                        self.registry = json.load(f)
                else:
                    self._reconstruct_registry()

                logger.info(
                    "RAG úložiště načteno z %s: %d dokumentů, %d vektorových bloků",
                    self.storage_dir,
                    len(self.registry),
                    len(self.chunks),
                )
            else:
                self._index = faiss.IndexFlatIP(self.embedding_dim)
                self.chunks = []
                self.registry = {}
        except Exception as exc:
            logger.warning("Nepodařilo se načíst existující RAG úložiště (%s), vytvářím čisté.", exc)
            self.chunks = []
            self.registry = {}
            try:
                import faiss
                self._index = faiss.IndexFlatIP(self.embedding_dim)
            except ImportError:
                self._index = None

    def _save_storage(self) -> None:
        """Uloží FAISS index a metadata na disk."""
        try:
            import faiss
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            index_path = self.storage_dir / "index.faiss"
            chunks_path = self.storage_dir / "chunks.json"
            registry_path = self.storage_dir / "registry.json"

            if self._index is not None:
                faiss.write_index(self._index, str(index_path))

            with chunks_path.open("w", encoding="utf-8") as f:
                json.dump([c.to_dict() for c in self.chunks], f, ensure_ascii=False, indent=2)

            with registry_path.open("w", encoding="utf-8") as f:
                json.dump(self.registry, f, ensure_ascii=False, indent=2)

            logger.info("RAG úložiště uloženo do %s (%d bloků)", self.storage_dir, len(self.chunks))
        except Exception as exc:
            logger.error("Chyba při ukládání RAG úložiště: %s", exc)

    def _reconstruct_registry(self) -> None:
        """Zrekonstruuje registr dokumentů ze seznamu chunků."""
        self.registry = {}
        for chunk in self.chunks:
            path_str = chunk.file_path or chunk.doc_name
            if path_str not in self.registry:
                self.registry[path_str] = {
                    "file_path": chunk.file_path,
                    "filename": chunk.doc_name,
                    "chunk_count": 0,
                    "file_size": 0,
                    "file_mtime": 0,
                    "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            self.registry[path_str]["chunk_count"] += 1

    def read(self, path: str | Path) -> str:
        """
        Přečte plný text dokumentu (PDF, DOCX, MD, PY, JSON, TXT apod.).
        Udržuje zpětnou kompatibilitu se stávajícím rozhraním.
        """
        document_path = Path(path).resolve()
        if not document_path.is_file():
            raise FileNotFoundError(f"Dokument neexistuje: {document_path}")

        suffix = document_path.suffix.lower()
        if suffix == ".pdf":
            text = self._read_pdf(document_path)
        elif suffix == ".docx":
            text = self._read_docx(document_path)
        else:
            # MD, PY, JSON, TXT, CSV, LOG atd.
            text = self._read_text_file(document_path)

        truncated = self.truncate(text)
        logger.info(
            "Dokument načten; typ=%s, zdrojových znaků=%d, použitých znaků=%d",
            suffix,
            len(text),
            len(truncated),
        )
        return truncated

    def truncate(self, text: str) -> str:
        """Ořízne text na nastavený maximální počet znaků."""
        normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        return normalized[: self.max_characters]

    def chunk_text(
        self,
        text: str,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> list[str]:
        """Rozdělí text na menší bloky s překryvem."""
        c_size = chunk_size or self.chunk_size
        c_overlap = chunk_overlap or self.chunk_overlap
        return smart_chunk_text(text, chunk_size=c_size, chunk_overlap=c_overlap)

    def index_file(self, path: str | Path) -> int:
        """
        Načte soubor, provede chytrý chunking, spočítá embeddings a přidá bloky
        do lokální vektorové databáze FAISS.
        Vrací počet vytvořených a zindexovaných bloků.
        """
        doc_path = Path(path).resolve()
        if not doc_path.is_file():
            raise FileNotFoundError(f"Soubor neexistuje: {doc_path}")

        text = self.read(doc_path)
        if not text.strip():
            logger.warning("Soubor %s neobsahuje žádný text k indexaci.", doc_path.name)
            return 0

        # Pokud již byl soubor dříve zindexován, odstraníme staré bloky
        self.delete_document(str(doc_path), save=False)

        raw_chunks = self.chunk_text(text)
        if not raw_chunks:
            return 0

        file_chunks = [
            DocumentChunk(
                doc_id=doc_path.stem,
                doc_name=doc_path.name,
                chunk_index=i,
                text=chunk_text,
                file_path=str(doc_path),
                char_count=len(chunk_text),
            )
            for i, chunk_text in enumerate(raw_chunks)
        ]

        model = self._ensure_model()
        index = self._ensure_index()

        import numpy as np
        texts_to_embed = [c.text for c in file_chunks]
        embeddings = model.encode(
            texts_to_embed,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).astype(np.float32)

        with self._lock:
            index.add(embeddings)
            self.chunks.extend(file_chunks)

            # Aktualizace registru
            stat = doc_path.stat()
            self.registry[str(doc_path)] = {
                "file_path": str(doc_path),
                "filename": doc_path.name,
                "chunk_count": len(file_chunks),
                "file_size": stat.st_size,
                "file_mtime": stat.st_mtime,
                "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            self._save_storage()

        logger.info(
            "Soubor %s úspěšně zindexován: %d bloků (celkem v indexu: %d bloků)",
            doc_path.name,
            len(file_chunks),
            len(self.chunks),
        )
        return len(file_chunks)

    def search(
        self,
        query: str,
        top_k: int | None = None,
        score_threshold: float = 0.0,
    ) -> list[dict[str, Any]]:
        """
        Sémantické dohledávání (Retrieval): Vyhledá v lokální vektorové databázi
        nejrelevantnější úseky (nejbližší shoda podle kosinové podobnosti).
        Vrací seznam 2-3 nejrelevantnějších bloků.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        with self._lock:
            if not self.chunks or self._index is None or self._index.ntotal == 0:
                return []

            k = min(top_k or self.top_k, self._index.ntotal)
            if k <= 0:
                return []

            model = self._ensure_model()
            import numpy as np

            q_vec = model.encode(
                [clean_query],
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            ).astype(np.float32)

            distances, indices = self._index.search(q_vec, k)

            results: list[dict[str, Any]] = []
            for score, idx in zip(distances[0], indices[0]):
                if idx == -1 or idx >= len(self.chunks):
                    continue
                score_val = float(score)
                if score_val < score_threshold:
                    continue
                chunk = self.chunks[idx]
                results.append({
                    "doc_id": chunk.doc_id,
                    "doc_name": chunk.doc_name,
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                    "file_path": chunk.file_path,
                    "score": round(score_val, 4),
                    "char_count": chunk.char_count,
                })

            return results

    def delete_document(self, doc_identifier: str, save: bool = True) -> bool:
        """
        Odstraní dokument a všechny jeho bloky z FAISS indexu a registru.
        Ztotožňuje se podle cesty k souboru nebo názvu souboru.
        """
        with self._lock:
            target_key = None
            target_name = None

            # Hledání v registru
            for path_key, meta in list(self.registry.items()):
                if path_key == doc_identifier or meta.get("filename") == doc_identifier:
                    target_key = path_key
                    target_name = meta.get("filename")
                    break

            if not target_key:
                # Zkusit shodu v chuncích přímo
                for chunk in self.chunks:
                    if chunk.file_path == doc_identifier or chunk.doc_name == doc_identifier:
                        target_key = chunk.file_path
                        target_name = chunk.doc_name
                        break

            if not target_key and not target_name:
                return False

            # Filtrování chunků
            surviving_indices: list[int] = []
            surviving_chunks: list[DocumentChunk] = []

            for i, chunk in enumerate(self.chunks):
                if chunk.file_path == target_key or chunk.doc_name == target_name:
                    continue
                surviving_indices.append(i)
                surviving_chunks.append(chunk)

            # Přestavba FAISS indexu pro zbývající vektory
            import faiss
            import numpy as np

            if not surviving_chunks:
                self._index = faiss.IndexFlatIP(self.embedding_dim)
                self.chunks = []
            elif self._index is not None and self._index.ntotal > 0:
                old_count = self._index.ntotal
                all_vectors = np.empty((old_count, self.embedding_dim), dtype=np.float32)
                self._index.reconstruct_n(0, old_count, all_vectors)
                surviving_vectors = all_vectors[surviving_indices]

                new_index = faiss.IndexFlatIP(self.embedding_dim)
                new_index.add(surviving_vectors)
                self._index = new_index
                self.chunks = surviving_chunks

            if target_key in self.registry:
                del self.registry[target_key]

            if save:
                self._save_storage()

            logger.info("Dokument %s byl odstraněn z RAG indexu.", target_name or target_key)
            return True

    def clear_all(self) -> None:
        """Kompletně vymaže všechny indexované dokumenty a bloky."""
        with self._lock:
            import faiss
            self._index = faiss.IndexFlatIP(self.embedding_dim)
            self.chunks = []
            self.registry = {}
            self._save_storage()
            logger.info("Všechny dokumenty byly vymazány z RAG indexu.")

    def reindex_all(self) -> dict[str, int]:
        """
        Znovu projde a zindexuje všechny dříve registrované soubory z disku.
        Vrací slovník {soubor: počet_bloků}.
        """
        paths_to_reindex = list(self.registry.keys())
        results: dict[str, int] = {}
        for path_str in paths_to_reindex:
            path = Path(path_str)
            if path.is_file():
                try:
                    count = self.index_file(path)
                    results[path.name] = count
                except Exception as exc:
                    logger.error("Chyba při reindexaci souboru %s: %s", path, exc)
                    results[path.name] = -1
            else:
                logger.warning("Soubor pro reindexaci již na disku neexistuje: %s", path_str)
        return results

    def get_indexed_documents(self) -> list[dict[str, Any]]:
        """Vrátí přehledný seznam všech zindexovaných souborů a statistik."""
        with self._lock:
            docs = []
            for path_key, meta in self.registry.items():
                docs.append({
                    "file_path": meta.get("file_path", path_key),
                    "filename": meta.get("filename", Path(path_key).name),
                    "chunk_count": meta.get("chunk_count", 0),
                    "file_size": meta.get("file_size", 0),
                    "indexed_at": meta.get("indexed_at", ""),
                })
            return sorted(docs, key=lambda d: d["filename"].lower())

    def total_chunks(self) -> int:
        """Vrátí celkový počet uložených vektorových bloků."""
        with self._lock:
            return len(self.chunks)

    @staticmethod
    def format_chunks_for_prompt(chunks: list[dict[str, Any]]) -> str:
        """Formátuje dohledané RAG úseky do přehledného kontextu pro LLM prompt."""
        if not chunks:
            return ""
        formatted = []
        for i, c in enumerate(chunks, 1):
            doc_name = c.get("doc_name", "Dokument")
            score = c.get("score", 0.0)
            text = c.get("text", "").strip()
            formatted.append(f"[Úsek {i} | Zdroj: {doc_name} (relevance: {score:.2f})]\n{text}")
        return "\n\n".join(formatted)

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
        parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
        for table in document.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    parts.append(row_text)
        return "\n".join(parts)

    @staticmethod
    def _read_text_file(path: Path) -> str:
        for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1250"):
            try:
                with path.open("r", encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, LookupError):
                continue
        with path.open("r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def get_embedding_model(self):
        """Vrátí instanci CPU embedding modelu pro sdílení s ConversationMemoryService."""
        return self._ensure_model()


@dataclass
class MemoryChunk:
    """Reprezentuje sémantický blok z minulé konverzace."""
    session_id: str
    session_title: str
    chunk_index: int
    text: str
    timestamp: str
    char_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "session_title": self.session_title,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "timestamp": self.timestamp,
            "char_count": self.char_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryChunk:
        return cls(
            session_id=data.get("session_id", ""),
            session_title=data.get("session_title", ""),
            chunk_index=int(data.get("chunk_index", 0)),
            text=data.get("text", ""),
            timestamp=data.get("timestamp", ""),
            char_count=int(data.get("char_count", len(data.get("text", "")))),
        )


class ConversationMemoryService:
    """
    Sémantická paměť konverzací (Long-Term Vector Memory).
    Spravuje lokální FAISS vektorovou databázi pro minulá sezení v podadresáři `rag_storage/memory/`.
    Automaticky indexuje zprávy relací, provádí smart chunking s překryvem a poskytuje
    rychlé sémantické dohledávání relevantních informací ze starších konverzací.
    """

    def __init__(
        self,
        config: dict | None = None,
        storage_dir: str | Path | None = None,
        embedding_model: str = "all-MiniLM-L6-v2",
        chunk_size: int = 400,
        chunk_overlap: int = 50,
        top_k: int = 2,
        shared_model=None,
        shared_model_provider: Callable[[], Any] | None = None,
    ):
        rag_cfg = (config or {}).get("rag", {})
        default_dir = Path(rag_cfg.get("storage_dir", "rag_storage")) / "memory"
        self.storage_dir = Path(storage_dir or rag_cfg.get("memory_storage_dir", default_dir))
        self.embedding_model_name = rag_cfg.get("embedding_model", embedding_model)
        self.chunk_size = int(rag_cfg.get("chunk_size", chunk_size))
        self.chunk_overlap = int(rag_cfg.get("chunk_overlap", chunk_overlap))
        self.top_k = int(rag_cfg.get("memory_top_k", top_k))
        self.enabled = bool(rag_cfg.get("enabled", True))

        self.embedding_dim = 384
        self._model = shared_model
        self._shared_model_provider = shared_model_provider
        self._index = None
        self.chunks: list[MemoryChunk] = []
        self.registry: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

        self._load_storage()

    def _ensure_model(self):
        """Zajistí načtení CPU embedding modelu."""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    if self._shared_model_provider:
                        self._model = self._shared_model_provider()
                    else:
                        try:
                            from sentence_transformers import SentenceTransformer
                            logger.info("Načítám CPU embedding model pro paměť: %s", self.embedding_model_name)
                            self._model = SentenceTransformer(self.embedding_model_name, device="cpu")
                        except ImportError as exc:
                            raise RuntimeError(
                                "Pro vektorové embeddings nainstalujte: pip install sentence-transformers"
                            ) from exc
        return self._model

    def _ensure_index(self):
        """Zajistí existenci FAISS indexu."""
        if self._index is None:
            try:
                import faiss
                self._index = faiss.IndexFlatIP(self.embedding_dim)
            except ImportError as exc:
                raise RuntimeError("Pro vektorové vyhledávání nainstalujte: pip install faiss-cpu") from exc
        return self._index

    def _load_storage(self) -> None:
        """Načte paměťový FAISS index a metadata z disku."""
        try:
            import faiss
            index_path = self.storage_dir / "index.faiss"
            chunks_path = self.storage_dir / "chunks.json"
            registry_path = self.storage_dir / "registry.json"

            if index_path.is_file() and chunks_path.is_file():
                self._index = faiss.read_index(str(index_path))
                with chunks_path.open("r", encoding="utf-8") as f:
                    raw_chunks = json.load(f)
                    self.chunks = [MemoryChunk.from_dict(c) for c in raw_chunks]

                if registry_path.is_file():
                    with registry_path.open("r", encoding="utf-8") as f:
                        self.registry = json.load(f)
                else:
                    self._reconstruct_registry()

                logger.info(
                    "Sémantická paměť načtena z %s: %d relací, %d vektorových bloků",
                    self.storage_dir,
                    len(self.registry),
                    len(self.chunks),
                )
            else:
                self._index = faiss.IndexFlatIP(self.embedding_dim)
                self.chunks = []
                self.registry = {}
        except Exception as exc:
            logger.warning("Nepodařilo se načíst existující paměťové úložiště (%s), vytvářím čisté.", exc)
            self.chunks = []
            self.registry = {}
            try:
                import faiss
                self._index = faiss.IndexFlatIP(self.embedding_dim)
            except ImportError:
                self._index = None

    def _save_storage(self) -> None:
        """Uloží paměťový index a metadata na disk."""
        try:
            import faiss
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            index_path = self.storage_dir / "index.faiss"
            chunks_path = self.storage_dir / "chunks.json"
            registry_path = self.storage_dir / "registry.json"

            if self._index is not None:
                faiss.write_index(self._index, str(index_path))

            with chunks_path.open("w", encoding="utf-8") as f:
                json.dump([c.to_dict() for c in self.chunks], f, ensure_ascii=False, indent=2)

            with registry_path.open("w", encoding="utf-8") as f:
                json.dump(self.registry, f, ensure_ascii=False, indent=2)

            logger.info("Sémantická paměť uložena do %s (%d bloků)", self.storage_dir, len(self.chunks))
        except Exception as exc:
            logger.error("Chyba při ukládání sémantické paměti: %s", exc)

    def _reconstruct_registry(self) -> None:
        """Zrekonstruuje registr relací ze seznamu paměťových bloků."""
        self.registry = {}
        for chunk in self.chunks:
            sid = chunk.session_id
            if sid not in self.registry:
                self.registry[sid] = {
                    "session_id": sid,
                    "title": chunk.session_title,
                    "chunk_count": 0,
                    "updated_at": chunk.timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            self.registry[sid]["chunk_count"] += 1

    def format_session_messages(self, title: str, messages: list[dict[str, Any]]) -> str:
        """Převede zprávy relace do textového formátu pro chytrý chunking."""
        if not messages:
            return ""
        lines = [f"=== TÉMA KONVERZACE: {title} ==="]
        for msg in messages:
            role = msg.get("role", "")
            content = str(msg.get("content", "")).strip()
            if not content:
                continue
            lbl = "Uživatel" if role == "user" else "Asistent"
            lines.append(f"[{lbl}]: {content}")
        return "\n\n".join(lines)

    def index_session(
        self,
        session_id: str,
        title: str,
        messages: list[dict[str, Any]],
        updated_at: str = "",
    ) -> int:
        """
        Zindexuje zprávy zadané relace: rozdělí na smart chunky, spočítá embeddings
        a uloží do FAISS indexu paměti. Pokud relace již byla zindexována, staré bloky
        jsou nahrazeny novými (aktualizace).
        """
        if not messages:
            self.delete_session(session_id)
            return 0

        text = self.format_session_messages(title, messages)
        if not text.strip():
            return 0

        raw_chunks = smart_chunk_text(text, chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap)
        if not raw_chunks:
            return 0

        stamp = updated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_chunks = [
            MemoryChunk(
                session_id=session_id,
                session_title=title,
                chunk_index=i,
                text=ch,
                timestamp=stamp,
                char_count=len(ch),
            )
            for i, ch in enumerate(raw_chunks)
        ]

        model = self._ensure_model()
        import numpy as np

        texts = [c.text for c in new_chunks]
        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).astype(np.float32)

        with self._lock:
            # Odstraníme staré bloky dané relace, pokud existovaly
            has_old = any(c.session_id == session_id for c in self.chunks)
            if has_old:
                # Rekonstruujeme index bez starých bloků
                remaining = [c for c in self.chunks if c.session_id != session_id]
                import faiss
                self._index = faiss.IndexFlatIP(self.embedding_dim)
                self.chunks = remaining
                if remaining:
                    rem_texts = [c.text for c in remaining]
                    rem_emb = model.encode(
                        rem_texts,
                        normalize_embeddings=True,
                        convert_to_numpy=True,
                        show_progress_bar=False,
                    ).astype(np.float32)
                    self._index.add(rem_emb)

            # Přidáme nové bloky
            idx = self._ensure_index()
            idx.add(embeddings)
            self.chunks.extend(new_chunks)

            # Aktualizace registru
            self.registry[session_id] = {
                "session_id": session_id,
                "title": title,
                "chunk_count": len(new_chunks),
                "updated_at": stamp,
            }

            self._save_storage()

        logger.info(
            "Relace '%s' (%s) zindexována do paměti: %d bloků (celkem v paměti: %d bloků)",
            title,
            session_id,
            len(new_chunks),
            len(self.chunks),
        )
        return len(new_chunks)

    def search_memory(
        self,
        query: str,
        top_k: int | None = None,
        score_threshold: float = 0.30,
        exclude_session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Sémantické vyhledávání v dlouhodobé paměti.
        Vrací nejrelevantnější bloky z minulých konverzací.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        with self._lock:
            if not self.chunks or self._index is None or self._index.ntotal == 0:
                return []

            # Zjistíme počet kandidátů k prohledání (hledáme více, pokud vylučujeme session_id)
            k_target = top_k or self.top_k
            fetch_k = min(k_target * 3 if exclude_session_id else k_target, self._index.ntotal)
            if fetch_k <= 0:
                return []

            model = self._ensure_model()
            import numpy as np

            q_vec = model.encode(
                [clean_query],
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            ).astype(np.float32)

            distances, indices = self._index.search(q_vec, fetch_k)

            results: list[dict[str, Any]] = []
            for score, idx in zip(distances[0], indices[0]):
                if idx == -1 or idx >= len(self.chunks):
                    continue
                score_val = float(score)
                if score_val < score_threshold:
                    continue
                chunk = self.chunks[idx]
                if exclude_session_id and chunk.session_id == exclude_session_id:
                    continue
                results.append({
                    "session_id": chunk.session_id,
                    "session_title": chunk.session_title,
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                    "timestamp": chunk.timestamp,
                    "score": round(score_val, 4),
                    "char_count": chunk.char_count,
                })
                if len(results) >= k_target:
                    break

            return results

    def format_memory_for_prompt(self, memories: list[dict[str, Any]]) -> str:
        """Zformátuje dohledanou paměť do přehledného bloku pro prompt LLM."""
        if not memories:
            return ""
        formatted = ["RELEVANTNÍ HISTORICKÁ PAMĚŤ:"]
        for i, m in enumerate(memories, 1):
            title = m.get("session_title", "Předchozí konverzace")
            score = m.get("score", 0.0)
            text = m.get("text", "").strip()
            formatted.append(f"--- Záznam #{i} [Téma: „{title}“, relevance: {score:.2f}] ---\n{text}")
        return "\n\n".join(formatted)

    def delete_session(self, session_id: str) -> bool:
        """Odstraní relaci z FAISS paměti i registru."""
        with self._lock:
            if session_id not in self.registry and not any(c.session_id == session_id for c in self.chunks):
                return False

            remaining = [c for c in self.chunks if c.session_id != session_id]
            import faiss
            self._index = faiss.IndexFlatIP(self.embedding_dim)
            self.chunks = remaining
            self.registry.pop(session_id, None)

            if remaining:
                model = self._ensure_model()
                import numpy as np
                rem_texts = [c.text for c in remaining]
                rem_emb = model.encode(
                    rem_texts,
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                    show_progress_bar=False,
                ).astype(np.float32)
                self._index.add(rem_emb)

            self._save_storage()
            logger.info("Relace %s byla odstraněna ze sémantické paměti", session_id)
            return True

    def clear_memory(self) -> None:
        """Kompletně vyčistí vektorovou paměť."""
        with self._lock:
            try:
                import faiss
                self._index = faiss.IndexFlatIP(self.embedding_dim)
            except Exception:
                self._index = None
            self.chunks = []
            self.registry = {}
            self._save_storage()
            logger.info("Sémantická paměť byla kompletně vymazána")

    def get_memory_stats(self) -> dict[str, Any]:
        """Vrátí statistiky sémantické paměti."""
        with self._lock:
            return {
                "total_sessions": len(self.registry),
                "total_chunks": len(self.chunks),
                "storage_dir": str(self.storage_dir),
                "embedding_model": self.embedding_model_name,
            }

    def list_indexed_sessions(self) -> list[dict[str, Any]]:
        """Vrátí seznam všech zindexovaných relací."""
        with self._lock:
            return sorted(list(self.registry.values()), key=lambda x: x.get("updated_at", ""), reverse=True)

    def reindex_all_sessions(self, sessions_dir: str | Path) -> dict[str, int]:
        """Projde všechny .json soubory v sessions_dir a znovu je zindexuje do paměti."""
        s_dir = Path(sessions_dir)
        if not s_dir.is_dir():
            return {}
        results = {}
        for path in sorted(s_dir.glob("*.json")):
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                sid = data.get("session_id", path.stem)
                title = data.get("title", "Bez názvu")
                messages = data.get("messages", [])
                updated = data.get("updated_at", "")
                if messages:
                    count = self.index_session(sid, title, messages, updated_at=updated)
                    results[sid] = count
            except Exception as e:
                logger.error("Chyba při indexaci relace %s do paměti: %s", path.name, e)
        return results
