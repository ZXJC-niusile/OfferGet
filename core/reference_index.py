"""Read-only Reference Document Chunker & Retrieval Index (core/reference_index.py).

Indexes local supporting materials (project design docs, postmortems, weekly notes)
into heading-aware chunks tagged ``reference-only`` so OfferGet workflows can surface
factual details without polluting the public candidate profile.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence, Union

from core.resume_parser import _read_resume_file

SUPPORTED_REF_SUFFIXES = {".md", ".markdown", ".txt", ".html", ".htm", ".docx", ".pdf", ".json"}
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_WORD_RE = re.compile(r"[a-z0-9_+#.-]{2,}|[\u4e00-\u9fff]+")


def _tokenize(text: str) -> List[str]:
    """Tokenize English identifiers and Chinese unigrams/bigrams."""
    tokens: List[str] = []
    for seg in _WORD_RE.findall((text or "").lower()):
        if re.fullmatch(r"[\u4e00-\u9fff]+", seg):
            tokens.extend(seg)
            if len(seg) >= 2:
                tokens.extend(seg[i : i + 2] for i in range(len(seg) - 1))
        else:
            tokens.append(seg)
    return tokens


@dataclass
class ReferenceChunk:
    chunk_id: str
    doc_path: str
    doc_title: str
    section_path: str
    title: str
    content: str
    visibility: str = "reference-only"


def chunk_markdown_document(text: str, doc_path: str, doc_title: str) -> List[ReferenceChunk]:
    """Split text into heading-scoped chunks capped for concise evidence recall."""
    lines = text.splitlines()
    chunks: List[ReferenceChunk] = []
    stack: List[tuple[int, str]] = []
    buf: List[str] = []
    current_title = doc_title

    def flush() -> None:
        body = "\n".join(buf).strip()
        buf.clear()
        if not body:
            return
        section_path = " > ".join(t for _, t in stack) or doc_title
        for idx in range(0, len(body), 1400):
            part = body[idx : idx + 1400].strip()
            if part:
                chunks.append(
                    ReferenceChunk(
                        chunk_id=f"{doc_title}#{len(chunks)}",
                        doc_path=doc_path,
                        doc_title=doc_title,
                        section_path=section_path,
                        title=current_title,
                        content=part,
                    )
                )

    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            flush()
            level, title = len(m.group(1)), m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            current_title = title
        else:
            buf.append(line)
    flush()
    return chunks


class ReferenceKnowledgeIndex:
    """In-memory inverted index over local ``reference-only`` supporting documents."""

    def __init__(self, paths: Sequence[Union[str, Path]] = ()) -> None:
        self.chunks: List[ReferenceChunk] = []
        self._inverted: Dict[str, List[tuple[int, int, bool]]] = {}
        self.skipped_files: List[Dict[str, str]] = []
        if paths:
            self.add_paths(paths)

    def add_paths(self, paths: Sequence[Union[str, Path]]) -> None:
        files: List[Path] = []
        for raw in paths:
            p = Path(raw)
            if p.is_dir():
                files.extend(
                    f for f in sorted(p.rglob("*"))
                    if f.is_file() and f.suffix.lower() in SUPPORTED_REF_SUFFIXES
                )
            elif p.is_file():
                files.append(p)
            else:
                self.skipped_files.append({"path": str(p), "error": "not found"})

        for fp in files:
            try:
                text = _read_resume_file(fp)
            except Exception as exc:
                self.skipped_files.append({"path": str(fp), "error": str(exc)})
                continue
            if text.strip():
                self.chunks.extend(chunk_markdown_document(text, str(fp), fp.stem))
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        self._inverted.clear()
        for idx, chunk in enumerate(self.chunks):
            title_tokens = set(_tokenize(f"{chunk.title} {chunk.section_path}"))
            tf_map: Dict[str, int] = {}
            for tok in _tokenize(f"{chunk.title} {chunk.section_path} {chunk.content}"):
                tf_map[tok] = tf_map.get(tok, 0) + 1
            for tok, tf in tf_map.items():
                self._inverted.setdefault(tok, []).append((idx, tf, tok in title_tokens))

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Return top matching reference-only snippets for the query."""
        q_tokens = list(dict.fromkeys(_tokenize(query)))
        if not q_tokens or not self.chunks:
            return []

        n_chunks = len(self.chunks)
        scores: Dict[int, float] = {}
        for tok in q_tokens:
            postings = self._inverted.get(tok)
            if not postings:
                continue
            idf = math.log((n_chunks + 1) / (len(postings) + 0.5)) + 1.0
            for idx, tf, in_title in postings:
                boost = 3.0 if in_title else 1.0
                scores[idx] = scores.get(idx, 0.0) + tf * idf * boost

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[: max(1, limit)]
        return [
            {
                "chunk_id": self.chunks[idx].chunk_id,
                "doc_path": self.chunks[idx].doc_path,
                "doc_title": self.chunks[idx].doc_title,
                "section_path": self.chunks[idx].section_path,
                "title": self.chunks[idx].title,
                "content": self.chunks[idx].content,
                "visibility": "reference-only",
                "score": round(score, 2),
            }
            for idx, score in ranked
        ]
