"""Memoria persistente de IGRIS OS.

Dos piezas, ambas con codigo propio (solo stdlib) y pensadas para cerrar la
brecha con asistentes tipo ChatGPT/Cline/Continue, SIN copiar su
implementacion:

- ``ConversationJournal``: guarda el historial de la conversacion en disco
  (JSON por linea) para recuperarlo al reabrir IGRIS o al cambiar de modelo.
- ``LongTermMemory``: hechos breves sobre el usuario o sus preferencias
  ("uso una RTX 5060 Ti", "prefiero respuestas en espanol") que IGRIS puede
  recordar entre conversaciones.

Ambas son de solo texto, locales y bajo control del usuario (nada sale del
equipo). No depende de ningun proveedor de IA.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
import re
from typing import Iterable, Iterator

MAX_ENTRY_CHARS = 4000
MAX_FACT_CHARS = 280


def _safe_text(text: str, *, limit: int) -> str:
    """Normaliza y recorta un texto para almacenarlo sin saltos de linea."""
    flat = re.sub(r"\s+", " ", str(text)).strip()
    return flat[:limit]


@dataclass(frozen=True, slots=True)
class Fact:
    """Un hecho recordado a largo plazo, con su evidencia textual."""

    text: str
    created_at: str = ""


class ConversationJournal:
    """Historial de conversacion persistido en disco (JSON Lines).

    Cada linea es un turno ``{"role": ..., "text": ...}``. Se anexa para ser
    seguro entre hilos y se puede releer entero o solo las ultimas ``n``.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, role: str, text: str) -> None:
        record = {"role": role,
                  "text": _safe_text(text, limit=MAX_ENTRY_CHARS)}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def load(self, *, limit: int = 40) -> list[dict]:
        """Devuelve los ultimos ``limit`` turnos validos del journal."""
        if not self.path.is_file():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        entries: list[dict] = []
        for line in reversed(lines):
            if len(entries) >= limit:
                break
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict) and "role" in record and "text" in record:
                entries.append({"role": str(record["role"]),
                                "text": str(record["text"])})
        entries.reverse()
        return entries

    def clear(self) -> None:
        if self.path.is_file():
            self.path.unlink()

    def count(self) -> int:
        if not self.path.is_file():
            return 0
        return sum(1 for _ in self.path.open(encoding="utf-8"))


class LongTermMemory:
    """Hechos breves recordados entre conversaciones (JSON Lines).

    Evita duplicados exactos (case-insensitive) y recorta cada hecho. No usa
    ningun modelo: el hecho lo aporta el usuario o IGRIS de forma explicita.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _iter_records(self) -> Iterator[dict]:
        if not self.path.is_file():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict) and "text" in record:
                yield record

    def remember(self, text: str, *, created_at: str = "") -> bool:
        """Guarda un hecho. Devuelve False si ya existia (sin duplicar)."""
        flat = _safe_text(text, limit=MAX_FACT_CHARS)
        if not flat:
            return False
        existing = {str(r.get("text", "")).casefold() for r in self._iter_records()}
        if flat.casefold() in existing:
            return False
        fact = Fact(text=flat, created_at=created_at)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(fact), ensure_ascii=False) + "\n")
        return True

    def recall(self, *, limit: int = 50) -> list[Fact]:
        facts = [Fact(text=str(r.get("text", "")),
                      created_at=str(r.get("created_at", "")))
                 for r in self._iter_records()]
        facts.reverse()
        return facts[: max(0, limit)]

    def forget(self, text: str) -> int:
        """Elimina hechos que coincidan (case-insensitive). Devuelve cuantos."""
        target = _safe_text(text, limit=MAX_FACT_CHARS).casefold()
        kept, removed = [], 0
        for record in self._iter_records():
            if str(record.get("text", "")).casefold() == target:
                removed += 1
            else:
                kept.append(record)
        if removed:
            self._rewrite(kept)
        return removed

    def clear(self) -> None:
        if self.path.is_file():
            self.path.unlink()

    def _rewrite(self, records: Iterable[dict]) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def count(self) -> int:
        return sum(1 for _ in self._iter_records())


class PersistentMemory:
    """Fachada que une journal + memoria de hechos bajo un mismo directorio."""

    JOURNAL = "journal.jsonl"
    FACTS = "facts.jsonl"

    def __init__(self, root: Path) -> None:
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        self.journal = ConversationJournal(root / self.JOURNAL)
        self.long_term = LongTermMemory(root / self.FACTS)

    def log_turn(self, role: str, text: str) -> None:
        self.journal.append(role, text)

    def remember(self, text: str, *, created_at: str = "") -> bool:
        return self.long_term.remember(text, created_at=created_at)

    def recall(self, *, limit: int = 50) -> list[Fact]:
        return self.long_term.recall(limit=limit)

    def recent_history(self, *, limit: int = 40) -> list[dict]:
        return self.journal.load(limit=limit)

    def clear(self) -> None:
        self.journal.clear()
        self.long_term.clear()