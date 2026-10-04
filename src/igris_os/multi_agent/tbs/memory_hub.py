"""Memory Hub: Central coordination point for Tiny but Serious Inc. agents."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    """Types of memories stored in the hub."""
    CHAT_MEMORY = "chat_memory"
    WIKI = "wiki"
    CODEGRAPH = "codegraph"
    SKILL = "skill"
    INCIDENT = "incident"


@dataclass(frozen=True, slots=True)
class MemoryEntry:
    """A single memory entry in the hub."""
    memory_type: MemoryType
    category: str
    content: dict[str, Any]
    source_agent: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    verified: bool = False


@dataclass(frozen=True, slots=True)
class Skill:
    """A verified skill/method that agents can use."""
    name: str
    description: str
    category: str
    parameters: dict[str, Any]
    success_rate: float
    usage_count: int = 0


@dataclass(frozen=True, slots=True)
class HandoffContext:
    """Context passed between agents during handoff."""
    from_agent: str
    to_agent: str
    objective: str
    current_state: dict[str, Any]
    relevant_memories: list[dict[str, Any]]  # Changed from MemoryEntry to dict for JSON serialization
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MemoryHub:
    """Central memory hub for Tiny but Serious Inc. multi-agent system."""

    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path.resolve()
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Storage files
        self.chat_memory_file = self.storage_path / "chat_memory.jsonl"
        self.wiki_file = self.storage_path / "wiki.json"
        self.codegraph_file = self.storage_path / "codegraph.json"
        self.skills_file = self.storage_path / "skills.json"
        self.incidents_file = self.storage_path / "incidents.jsonl"
        self.handoffs_file = self.storage_path / "handoffs.jsonl"
        
        # In-memory cache for skills
        self._skills_cache: dict[str, Skill] = {}
        self._load_skills()

    def store_memory(self, entry: MemoryEntry) -> None:
        """Store a memory entry in the appropriate storage."""
        if entry.memory_type == MemoryType.CHAT_MEMORY:
            self._store_chat_memory(entry)
        elif entry.memory_type == MemoryType.WIKI:
            self._store_wiki(entry)
        elif entry.memory_type == MemoryType.CODEGRAPH:
            self._store_codegraph(entry)
        elif entry.memory_type == MemoryType.SKILL:
            self._store_skill(entry)
        elif entry.memory_type == MemoryType.INCIDENT:
            self._store_incident(entry)
        else:
            raise ValueError(f"Unknown memory type: {entry.memory_type}")

    def retrieve_memories(
        self,
        memory_type: MemoryType,
        category: str | None = None,
        source_agent: str | None = None,
        limit: int = 50,
    ) -> list[MemoryEntry]:
        """Retrieve memories based on filters."""
        if memory_type == MemoryType.CHAT_MEMORY:
            return self._retrieve_chat_memory(category, source_agent, limit)
        elif memory_type == MemoryType.WIKI:
            return self._retrieve_wiki(category, limit)
        elif memory_type == MemoryType.CODEGRAPH:
            return self._retrieve_codegraph(limit)
        elif memory_type == MemoryType.SKILL:
            return self._retrieve_skills(category, limit)
        elif memory_type == MemoryType.INCIDENT:
            return self._retrieve_incidents(source_agent, limit)
        else:
            raise ValueError(f"Unknown memory type: {memory_type}")

    def get_skill(self, skill_name: str) -> Skill | None:
        """Get a specific skill by name."""
        return self._skills_cache.get(skill_name)

    def record_handoff(self, context: HandoffContext) -> None:
        """Record an agent handoff for continuity."""
        with self.handoffs_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "from_agent": context.from_agent,
                "to_agent": context.to_agent,
                "objective": context.objective,
                "current_state": context.current_state,
                "relevant_memories": context.relevant_memories,  # Already serializable dicts
                "timestamp": context.timestamp,
            }, ensure_ascii=False) + "\n")

    def get_recent_handoffs(self, agent: str | None = None, limit: int = 10) -> list[dict]:
        """Get recent handoffs, optionally filtered by agent."""
        if not self.handoffs_file.exists():
            return []
        
        handoffs = []
        for line in self.handoffs_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if agent is None or data["from_agent"] == agent or data["to_agent"] == agent:
                    handoffs.append(data)
            except json.JSONDecodeError:
                continue
        
        return handoffs[-limit:]

    def _store_chat_memory(self, entry: MemoryEntry) -> None:
        with self.chat_memory_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "category": entry.category,
                "content": entry.content,
                "source_agent": entry.source_agent,
                "created_at": entry.created_at,
                "verified": entry.verified,
            }, ensure_ascii=False) + "\n")

    def _retrieve_chat_memory(
        self, category: str | None, source_agent: str | None, limit: int
    ) -> list[MemoryEntry]:
        if not self.chat_memory_file.exists():
            return []
        
        entries = []
        for line in self.chat_memory_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if category and data.get("category") != category:
                    continue
                if source_agent and data.get("source_agent") != source_agent:
                    continue
                entries.append(MemoryEntry(
                    memory_type=MemoryType.CHAT_MEMORY,
                    category=data["category"],
                    content=data["content"],
                    source_agent=data["source_agent"],
                    created_at=data["created_at"],
                    verified=data.get("verified", False),
                ))
            except (json.JSONDecodeError, KeyError):
                continue
        
        return entries[-limit:]

    def _store_wiki(self, entry: MemoryEntry) -> None:
        wiki = self._load_wiki()
        key = f"{entry.category}:{entry.source_agent}"
        wiki[key] = {
            "category": entry.category,
            "content": entry.content,
            "source_agent": entry.source_agent,
            "created_at": entry.created_at,
            "verified": entry.verified,
        }
        self.wiki_file.write_text(json.dumps(wiki, ensure_ascii=False, indent=2), encoding="utf-8")

    def _retrieve_wiki(self, category: str | None, limit: int) -> list[MemoryEntry]:
        wiki = self._load_wiki()
        entries = []
        for key, data in wiki.items():
            if category and data.get("category") != category:
                continue
            entries.append(MemoryEntry(
                memory_type=MemoryType.WIKI,
                category=data["category"],
                content=data["content"],
                source_agent=data["source_agent"],
                created_at=data["created_at"],
                verified=data.get("verified", False),
            ))
        return entries[-limit:]

    def _load_wiki(self) -> dict:
        if not self.wiki_file.exists():
            return {}
        try:
            return json.loads(self.wiki_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _store_codegraph(self, entry: MemoryEntry) -> None:
        codegraph = self._load_codegraph()
        codegraph.update(entry.content)
        self.codegraph_file.write_text(json.dumps(codegraph, ensure_ascii=False, indent=2), encoding="utf-8")

    def _retrieve_codegraph(self, limit: int) -> list[MemoryEntry]:
        codegraph = self._load_codegraph()
        return [MemoryEntry(
            memory_type=MemoryType.CODEGRAPH,
            category="code_structure",
            content=codegraph,
            source_agent="system",
            created_at=datetime.now(timezone.utc).isoformat(),
            verified=True,
        )]

    def _load_codegraph(self) -> dict:
        if not self.codegraph_file.exists():
            return {}
        try:
            return json.loads(self.codegraph_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _store_skill(self, entry: MemoryEntry) -> None:
        skill = Skill(
            name=entry.content.get("name", ""),
            description=entry.content.get("description", ""),
            category=entry.category,
            parameters=entry.content.get("parameters", {}),
            success_rate=entry.content.get("success_rate", 0.0),
            usage_count=entry.content.get("usage_count", 0),
        )
        self._skills_cache[skill.name] = skill
        self._save_skills()

    def _retrieve_skills(self, category: str | None, limit: int) -> list[MemoryEntry]:
        skills = [
            MemoryEntry(
                memory_type=MemoryType.SKILL,
                category=skill.category,
                content={
                    "name": skill.name,
                    "description": skill.description,
                    "parameters": skill.parameters,
                    "success_rate": skill.success_rate,
                    "usage_count": skill.usage_count,
                },
                source_agent="system",
                created_at=datetime.now(timezone.utc).isoformat(),
                verified=True,
            )
            for skill in self._skills_cache.values()
            if category is None or skill.category == category
        ]
        return skills[-limit:]

    def _load_skills(self) -> None:
        if not self.skills_file.exists():
            return
        try:
            data = json.loads(self.skills_file.read_text(encoding="utf-8"))
            for name, skill_data in data.items():
                self._skills_cache[name] = Skill(
                    name=name,
                    description=skill_data.get("description", ""),
                    category=skill_data.get("category", ""),
                    parameters=skill_data.get("parameters", {}),
                    success_rate=skill_data.get("success_rate", 0.0),
                    usage_count=skill_data.get("usage_count", 0),
                )
        except json.JSONDecodeError:
            pass

    def _save_skills(self) -> None:
        data = {
            name: {
                "description": skill.description,
                "category": skill.category,
                "parameters": skill.parameters,
                "success_rate": skill.success_rate,
                "usage_count": skill.usage_count,
            }
            for name, skill in self._skills_cache.items()
        }
        self.skills_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _store_incident(self, entry: MemoryEntry) -> None:
        with self.incidents_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "category": entry.category,
                "content": entry.content,
                "source_agent": entry.source_agent,
                "created_at": entry.created_at,
                "verified": entry.verified,
            }, ensure_ascii=False) + "\n")

    def _retrieve_incidents(self, source_agent: str | None, limit: int) -> list[MemoryEntry]:
        if not self.incidents_file.exists():
            return []
        
        entries = []
        for line in self.incidents_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if source_agent and data.get("source_agent") != source_agent:
                    continue
                entries.append(MemoryEntry(
                    memory_type=MemoryType.INCIDENT,
                    category=data["category"],
                    content=data["content"],
                    source_agent=data["source_agent"],
                    created_at=data["created_at"],
                    verified=data.get("verified", False),
                ))
            except (json.JSONDecodeError, KeyError):
                continue
        
        return entries[-limit:]

    def update_skill_usage(self, skill_name: str, success: bool) -> None:
        """Update skill usage statistics."""
        if skill_name not in self._skills_cache:
            return
        
        skill = self._skills_cache[skill_name]
        total_usage = skill.usage_count + 1
        new_rate = (skill.success_rate * skill.usage_count + (1.0 if success else 0.0)) / total_usage
        
        self._skills_cache[skill_name] = Skill(
            name=skill.name,
            description=skill.description,
            category=skill.category,
            parameters=skill.parameters,
            success_rate=new_rate,
            usage_count=total_usage,
        )
        self._save_skills()
