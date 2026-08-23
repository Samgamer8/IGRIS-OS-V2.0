from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ExperienceRecord:
    experience_id: str
    mission_type: str
    language: str
    strategy: str
    success: bool
    score: float
    attempts: int
    error_pattern: str = ""
    fix_pattern: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True, slots=True)
class TemplateRecord:
    template_id: str
    name: str
    language: str
    pattern: str
    success_rate: float
    usage_count: int = 0


class ExperienceMemory:
    # Crecimiento acotado: al superar MAX_BYTES se conservan las últimas
    # KEEP_RECORDS experiencias (las más recientes son las más útiles).
    MAX_BYTES = 2 * 1024 * 1024
    KEEP_RECORDS = 500

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.experiences_file = self.root / "experiences.jsonl"
        self.templates_file = self.root / "templates.json"

    def record_experience(self, mission_type: str, language: str, strategy: str,
                          success: bool, score: float, attempts: int,
                          error_pattern: str = "", fix_pattern: str = "") -> ExperienceRecord:
        experience_id = hashlib.sha256(
            f"{mission_type}:{language}:{strategy}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        record = ExperienceRecord(
            experience_id, mission_type, language, strategy, success, score,
            attempts, error_pattern, fix_pattern
        )
        with self.experiences_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(dataclasses.asdict(record), ensure_ascii=False) + "\n")
        self._trim_if_needed()
        if success and score >= 0.8:
            self._update_template(record)
        return record

    def find_similar_experiences(self, mission_type: str, language: str,
                                 limit: int = 10) -> tuple[ExperienceRecord, ...]:
        records = self._load_experiences()
        scored = []
        for record in records:
            score = 0.0
            if record.mission_type == mission_type:
                score += 0.5
            if record.language == language:
                score += 0.3
            if record.success:
                score += 0.2 * min(record.score, 1.0)
            scored.append((score, record))
        scored.sort(key=lambda x: x[0], reverse=True)
        return tuple(r for _, r in scored[:limit])

    def best_strategy(self, mission_type: str, language: str) -> str | None:
        records = self.find_similar_experiences(mission_type, language, limit=5)
        successful = [r for r in records if r.success and r.score >= 0.7]
        if not successful:
            return None
        strategy_counts: dict[str, int] = {}
        for record in successful:
            strategy_counts[record.strategy] = strategy_counts.get(record.strategy, 0) + 1
        if not strategy_counts:
            return None
        return max(strategy_counts.items(), key=lambda x: x[1])[0]

    def record_template(self, name: str, language: str, pattern: str,
                        success_rate: float) -> TemplateRecord:
        templates = self._load_templates()
        template_id = hashlib.sha256(f"{name}:{language}:{pattern}".encode()).hexdigest()[:16]
        record = TemplateRecord(template_id, name, language, pattern, success_rate)
        templates[template_id] = dataclasses.asdict(record)
        self.templates_file.write_text(
            json.dumps(templates, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return record

    def find_template(self, language: str, pattern: str) -> TemplateRecord | None:
        templates = self._load_templates()
        for record in templates.values():
            if record["language"] == language and record["pattern"] == pattern:
                return TemplateRecord(**record)
        return None

    def _update_template(self, experience: ExperienceRecord) -> None:
        templates = self._load_templates()
        pattern = f"{experience.mission_type}:{experience.language}"
        for record in templates.values():
            if record["language"] == experience.language and experience.mission_type in record["pattern"]:
                total = record["usage_count"] + 1
                new_rate = (record["success_rate"] * record["usage_count"] + experience.score) / total
                record["success_rate"] = new_rate
                record["usage_count"] = total
                self.templates_file.write_text(
                    json.dumps(templates, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                return
        self.record_template(
            f"template_{experience.mission_type}", experience.language,
            pattern, experience.score
        )

    def _load_experiences(self) -> list[ExperienceRecord]:
        if not self.experiences_file.exists():
            return []
        records = []
        for line in self.experiences_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Linea de experiencia corrupta, se omite")
                continue
            try:
                records.append(ExperienceRecord(**data))
            except TypeError:
                logger.warning("Registro de experiencia con campos invalidos, se omite")
        return records

    def _trim_if_needed(self) -> None:
        """Recorta el JSONL conservando las últimas KEEP_RECORDS entradas."""
        try:
            if (self.experiences_file.exists()
                    and self.experiences_file.stat().st_size > self.MAX_BYTES):
                records = self._load_experiences()
                keep = records[-self.KEEP_RECORDS:]
                tmp = self.experiences_file.with_suffix(".tmp")
                with tmp.open("w", encoding="utf-8") as f:
                    for record in keep:
                        f.write(
                            json.dumps(dataclasses.asdict(record),
                                       ensure_ascii=False) + "\n")
                tmp.replace(self.experiences_file)
        except OSError as exc:
            logger.warning("No se pudo recortar experiences: %s", exc)

    def _load_templates(self) -> dict[str, dict]:
        if not self.templates_file.exists():
            return {}
        return json.loads(self.templates_file.read_text(encoding="utf-8"))


import dataclasses
