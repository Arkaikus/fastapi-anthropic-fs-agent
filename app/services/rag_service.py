from __future__ import annotations

import hashlib
import math
import re
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

try:
    import chromadb
except ImportError:  # pragma: no cover - Graceful fallback when dependency is unavailable.
    chromadb = None

_TOKEN_RE = re.compile(r"[A-Za-z0-9_./-]+")
_VECTOR_SIZE = 64
_MAX_TOKENS_FOR_EMBEDDING = 1200
_RAG_SNIPPET_CHARS = 240
_MAX_ROOT_ENTRIES = 12
_MAX_FOCUSED_TARGETS = 8
_STOPWORDS = {"the", "and", "with", "for", "that", "from"}
_MAX_WORKSPACE_CACHES = 32


@dataclass(frozen=True, slots=True)
class _Document:
    path: str
    text: str


@dataclass(frozen=True, slots=True)
class _CachedFile:
    signature: tuple[int, int]
    text: str


@dataclass(slots=True)
class _WorkspaceCache:
    collection_name: str
    files: dict[str, _CachedFile]


class RagService:
    _lock = Lock()
    _client = None
    _workspace_caches: OrderedDict[str, _WorkspaceCache] = OrderedDict()

    def __init__(self) -> None:
        # background indexing queue and workers
        self._task_queue: "asyncio.Queue[str | None]" = asyncio.Queue()
        self._worker_tasks: list[asyncio.Task[None]] = []
        self._pending: set[str] = set()
        self._stopping = False
        self._executor = ThreadPoolExecutor(max_workers=2)

    def build_context(self, *, prompt: str, base_dir: str) -> str | None:
        if not settings.rag_enabled:
            return None
        if chromadb is None:
            logger.warning("RAG skipped: chromadb dependency is unavailable.")
            return None

        base = Path(base_dir).resolve()
        documents = self._get_cached_documents(base)
        if not documents:
            return self._format_context(prompt=prompt, base=base, documents=[], matches=[])

        matches = self._retrieve(prompt=prompt, base=base, documents=documents)
        return self._format_context(prompt=prompt, base=base, documents=documents, matches=matches)

    def _get_cached_documents(self, base: Path) -> list[_Document]:
        with self._lock:
            cache = self._get_workspace_cache(base)
            if not cache.files:
                return []
            return [_Document(path=path, text=cache.files[path].text) for path in sorted(cache.files)]

    async def prewarm(self, base_dir: str) -> None:
        """Schedule a one-time prewarm of the given workspace path.

        This enqueues the path for background indexing and returns quickly.
        If the path is already pending or indexing, the call is a no-op.
        """
        if not settings.rag_enabled or chromadb is None:
            return
        base = str(Path(base_dir).resolve())
        if base in self._pending:
            return
        self._pending.add(base)
        await self._task_queue.put(base)
        # ensure workers are started
        if not self._worker_tasks:
            self._start_workers(settings.rag_background_workers or 1)

    def start_background_index(self, paths: list[str]) -> None:
        """Kick off background indexing for a list of paths (non-blocking)."""
        if not settings.rag_enabled or chromadb is None:
            return
        loop = asyncio.get_event_loop()

        # schedule enqueues on the running loop
        async def _enqueue_all():
            for p in paths:
                await self.prewarm(p)

        try:
            loop.create_task(_enqueue_all())
        except RuntimeError:
            # no running loop; best-effort synchronous enqueue
            for p in paths:
                base = str(Path(p).resolve())
                if base not in self._pending:
                    self._pending.add(base)
                    # push into queue synchronously not possible outside loop
                    # rely on workers starting when app loop runs
                    pass

    def _start_workers(self, count: int) -> None:
        for _ in range(max(1, count)):
            task = asyncio.create_task(self._worker_loop())
            self._worker_tasks.append(task)

    async def _worker_loop(self) -> None:
        while not self._stopping:
            try:
                base = await self._task_queue.get()
            except asyncio.CancelledError:
                break
            if base is None:
                break
            try:
                path = Path(base)
                loop = asyncio.get_running_loop()
                # run the blocking sync indexing in a thread
                await loop.run_in_executor(self._executor, self._sync_documents, path)
            except Exception as exc:
                logger.debug("RAG prewarm failed for %s: %s", base, exc)
            finally:
                self._pending.discard(base)
                try:
                    self._task_queue.task_done()
                except Exception:
                    pass

    async def shutdown(self) -> None:
        """Stop background workers and shutdown executor."""
        self._stopping = True
        # push sentinels to unblock workers
        for _ in self._worker_tasks:
            try:
                await self._task_queue.put(None)
            except Exception:
                pass
        for task in list(self._worker_tasks):
            try:
                task.cancel()
                await task
            except Exception:
                pass
        self._worker_tasks.clear()
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            pass

    def _sync_documents(self, base: Path) -> list[_Document]:
        with self._lock:
            cache = self._get_workspace_cache(base)
            collection = self._get_client().get_or_create_collection(name=cache.collection_name)
            if not base.exists() or not base.is_dir():
                self._delete_paths(collection=collection, paths=list(cache.files))
                cache.files.clear()
                return []

            current_paths: set[str] = set()
            indexed_count = 0
            for path in sorted(base.rglob("*")):
                if indexed_count >= settings.rag_max_files:
                    break
                if not path.is_file() or self._should_skip_path(path):
                    continue
                rel_path = str(path.relative_to(base))
                try:
                    stat = path.stat()
                    signature = (stat.st_mtime_ns, stat.st_size)
                except Exception:
                    continue

                cached_file = cache.files.get(rel_path)
                if cached_file and cached_file.signature == signature:
                    current_paths.add(rel_path)
                    indexed_count += 1
                    continue
                try:
                    text = path.read_text(encoding="utf-8")[: settings.rag_max_file_chars]
                except Exception:
                    self._delete_paths(collection=collection, paths=[rel_path])
                    cache.files.pop(rel_path, None)
                    continue
                if not text.strip():
                    self._delete_paths(collection=collection, paths=[rel_path])
                    cache.files.pop(rel_path, None)
                    continue
                collection.upsert(
                    ids=[self._doc_id(rel_path)],
                    documents=[text],
                    embeddings=[self._embed(rel_path, text)],
                    metadatas=[{"path": rel_path}],
                )
                cache.files[rel_path] = _CachedFile(signature=signature, text=text)
                current_paths.add(rel_path)
                indexed_count += 1

            stale_paths = [path for path in cache.files if path not in current_paths]
            if stale_paths:
                self._delete_paths(collection=collection, paths=stale_paths)
                for path in stale_paths:
                    cache.files.pop(path, None)

            return [_Document(path=path, text=cache.files[path].text) for path in sorted(cache.files)]

    def _retrieve(self, *, prompt: str, base: Path, documents: list[_Document]) -> list[_Document]:
        if not documents:
            return []
        with self._lock:
            cache = self._get_workspace_cache(base)
            collection = self._get_client().get_or_create_collection(name=cache.collection_name)
            result = collection.query(
                query_embeddings=[self._embed("", prompt)],
                n_results=min(settings.rag_query_results, len(documents)),
                include=["metadatas"],
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

    @classmethod
    def _get_client(cls):
        if cls._client is None:
            cls._client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
        return cls._client

    @classmethod
    def _get_workspace_cache(cls, base: Path) -> _WorkspaceCache:
        workspace_key = str(base)
        cache = cls._workspace_caches.get(workspace_key)
        if cache is not None:
            cls._workspace_caches.move_to_end(workspace_key)
            return cache
        collection_hash = hashlib.sha256(workspace_key.encode("utf-8")).hexdigest()
        cache = _WorkspaceCache(
            collection_name=f"rag-workspace-{collection_hash}",
            files={},
        )
        if len(cls._workspace_caches) >= _MAX_WORKSPACE_CACHES:
            _, evicted = cls._workspace_caches.popitem(last=False)
            try:
                cls._get_client().delete_collection(name=evicted.collection_name)
            except Exception as exc:
                logger.debug(
                    "Failed to delete evicted RAG collection %s: %s",
                    evicted.collection_name,
                    exc,
                )
        cls._workspace_caches[workspace_key] = cache
        return cache

    @staticmethod
    def _delete_paths(*, collection: Any, paths: Iterable[str]) -> None:
        ids = [RagService._doc_id(path) for path in paths]
        if ids:
            collection.delete(ids=ids)

    @staticmethod
    def _doc_id(path: str) -> str:
        return hashlib.sha256(path.encode("utf-8")).hexdigest()

    def _format_context(
        self,
        *,
        prompt: str,
        base: Path,
        documents: list[_Document],
        matches: list[_Document],
    ) -> str:
        sections: list[str] = [
            "Workspace context generated before tool use. Treat these as hints; if tools are available, verify before acting.",
            self._build_exploration_summary(prompt=prompt, base=base, documents=documents),
        ]
        if matches:
            lines = ["RAG matches (most relevant first):"]
            for doc in matches:
                snippet = " ".join(doc.text.split())[:_RAG_SNIPPET_CHARS]
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
                for entry in root_entries[:_MAX_ROOT_ENTRIES]:
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
        keywords = {token.lower() for token in _TOKEN_RE.findall(prompt) if len(token) >= 3 and token.lower() not in _STOPWORDS}
        if not keywords:
            return []

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
        return [doc for _, doc in scored[:_MAX_FOCUSED_TARGETS]]

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

        if all(value == 0.0 for value in vector):
            return vector
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector]
