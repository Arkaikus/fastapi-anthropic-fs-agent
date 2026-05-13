from __future__ import annotations

import hashlib
import math
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

try:
    import chromadb
except ImportError:  # pragma: no cover - graceful fallback when dependency is unavailable.
    chromadb = None

_TOKEN_RE = re.compile(r"[A-Za-z0-9_./-]+")
_VECTOR_SIZE = 64
_MAX_TOKENS_FOR_EMBEDDING = 1200
_STOPWORDS = {"the", "and", "with", "for", "that", "from"}


@dataclass(frozen=True, slots=True)
class _Document:
    path: str
    text: str


class RagService:
    def build_context(self, *, prompt: str, base_dir: str) -> str | None:
        if not settings.rag_enabled:
            return None
        if chromadb is None:
            logger.warning("RAG skipped: chromadb dependency is unavailable.")
            return None

        base = Path(base_dir).resolve()
        documents = self._collect_documents(base)
        if not documents:
            return self._format_context(prompt=prompt, base=base, documents=documents, matches=[])

        matches = self._retrieve(prompt=prompt, documents=documents)
        return self._format_context(prompt=prompt, base=base, documents=documents, matches=matches)

    def _collect_documents(self, base: Path) -> list[_Document]:
        documents: list[_Document] = []
        for path in sorted(base.rglob("*")):
            if len(documents) >= settings.rag_max_files:
                break
            if not path.is_file() or self._should_skip_path(path):
                continue
            try:
                text = path.read_text(encoding="utf-8")[: settings.rag_max_file_chars]
            except Exception:
                continue
            if not text.strip():
                continue
            rel_path = str(path.relative_to(base))
            documents.append(_Document(path=rel_path, text=text))
        return documents

    def _retrieve(self, *, prompt: str, documents: list[_Document]) -> list[_Document]:
        if not documents:
            return []
        client = chromadb.EphemeralClient()
        collection = client.get_or_create_collection(name=f"rag-session-{uuid.uuid4().hex}")
        collection.add(
            ids=[f"doc-{idx}" for idx, _ in enumerate(documents)],
            documents=[doc.text for doc in documents],
            embeddings=[self._embed(doc.path, doc.text) for doc in documents],
            metadatas=[{"path": doc.path} for doc in documents],
        )
        result = collection.query(
            query_embeddings=[self._embed("", prompt)],
            n_results=min(settings.rag_query_results, len(documents)),
            include=["metadatas", "documents"],
        )
        by_path = {doc.path: doc for doc in documents}
        ordered: list[_Document] = []
        for metadata in result.get("metadatas", [[]])[0]:
            if not metadata:
                continue
            path = str(metadata.get("path", ""))
            doc = by_path.get(path)
            if doc:
                ordered.append(doc)
        return ordered

    def _format_context(
        self,
        *,
        prompt: str,
        base: Path,
        documents: list[_Document],
        matches: list[_Document],
    ) -> str:
        sections: list[str] = [
            "Workspace context generated before tool use. Treat these as hints and verify with tools.",
            self._build_exploration_summary(prompt=prompt, base=base, documents=documents),
        ]
        if matches:
            lines = ["RAG matches (most relevant first):"]
            for doc in matches:
                snippet = " ".join(doc.text.split())[:240]
                lines.append(f"- {doc.path}: {snippet}")
            sections.append("\n".join(lines))
        return "\n\n".join(section for section in sections if section.strip())

    def _build_exploration_summary(
        self,
        *,
        prompt: str,
        base: Path,
        documents: list[_Document],
    ) -> str:
        root_lines = ["Top-level workspace entries:"]
        try:
            root_entries = sorted(base.iterdir(), key=lambda entry: (entry.is_file(), entry.name))
        except Exception:
            root_lines.append("- Workspace directory not accessible.")
        else:
            if root_entries:
                for entry in root_entries[:12]:
                    prefix = "FILE" if entry.is_file() else "DIR "
                    root_lines.append(f"- {prefix} {entry.name}")
            else:
                root_lines.append("- (empty)")

        focused = self._rank_for_prompt(prompt=prompt, documents=documents)
        focused_lines = ["Prompt-focused exploration targets:"]
        if focused:
            focused_lines.extend(f"- {doc.path}" for doc in focused)
        else:
            focused_lines.append("- No obvious matches yet; start from top-level entries.")
        return "\n".join(root_lines + [""] + focused_lines)

    def _rank_for_prompt(self, *, prompt: str, documents: list[_Document]) -> list[_Document]:
        keywords = {
            token.lower()
            for token in _TOKEN_RE.findall(prompt)
            if len(token) >= 3 and token.lower() not in _STOPWORDS
        }
        if not keywords:
            return documents[:5]

        scored: list[tuple[int, _Document]] = []
        for doc in documents:
            path_l = doc.path.lower()
            text_l = doc.text.lower()
            path_hits = sum(1 for keyword in keywords if keyword in path_l)
            text_hits = sum(1 for keyword in keywords if keyword in text_l)
            score = path_hits * 3 + text_hits
            if score > 0:
                scored.append((score, doc))
        scored.sort(key=lambda item: (-item[0], item[1].path))
        return [doc for _, doc in scored[:8]]

    @staticmethod
    def _should_skip_path(path: Path) -> bool:
        ignored_parts = {".git", "__pycache__", ".venv", "node_modules"}
        return any(part in ignored_parts for part in path.parts)

    @staticmethod
    def _embed(path: str, text: str) -> list[float]:
        vector = [0.0] * _VECTOR_SIZE
        for token in _TOKEN_RE.findall(f"{path} {text.lower()}")[:_MAX_TOKENS_FOR_EMBEDDING]:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], byteorder="big") % _VECTOR_SIZE
            vector[index] += 1.0

        if not any(vector):
            return vector
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector]
