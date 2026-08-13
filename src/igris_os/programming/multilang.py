import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from igris_os.programming.languages import PROFILES, LanguageVerifier
from igris_os.tools import safe_output


@dataclass(frozen=True, slots=True)
class MultiLanguageResult:
    ok: bool
    message: str
    project: str = ""
    attempts: int = 0


class MultiLanguageDeveloper:
    def __init__(self, client, workspace: Path, model: str) -> None:
        self.client = client
        self.workspace = workspace.resolve()
        self.model = model

    def develop(self, objective: str, language: str, *, confirmed: bool = False,
                attempts: int = 3) -> MultiLanguageResult:
        key = language.casefold()
        profile = PROFILES.get(key)
        if not confirmed:
            return MultiLanguageResult(False, "Se necesita confirmacion")
        if not profile or key == "python":
            return MultiLanguageResult(False, "Lenguaje no compatible")
        feedback = ""
        for attempt in range(1, attempts + 1):
            prompt = (
                "Actua como ingeniero senior. Devuelve solo JSON UTF-8 con "
                '{"name":"nombre","source":"codigo completo","readme":"uso"}. '
                f"Lenguaje: {profile.name}. Sin markdown.\nOBJETIVO:\n{objective}")
            if feedback:
                prompt += "\nERROR DE VERIFICACION:\n" + feedback[-1500:]
            reply = self.client.generate(prompt, self.model)
            if not reply.ok:
                feedback = reply.error or "Modelo no disponible"
                continue
            try:
                raw = re.sub(r"^\s*```(?:json)?|```\s*$", "", reply.text,
                             flags=re.IGNORECASE).strip()
                package = json.loads(raw, strict=False)
                name = re.sub(r"[^a-zA-Z0-9_-]+", "_",
                              str(package["name"])).strip("_")
                source = str(package["source"])
                if not name or not source.strip():
                    raise ValueError("Paquete incompleto")
                staging = safe_output(self.workspace, ".staging/" + name)
                staging.mkdir(parents=True, exist_ok=True)
                filename = "main" + profile.extensions[0]
                candidate = staging / filename
                candidate.write_text(source, encoding="utf-8")
                check = LanguageVerifier().check(key, candidate)
                if not check.available:
                    return MultiLanguageResult(False, check.message, attempts=attempt)
                if not check.ok:
                    feedback = check.message
                    continue
                digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
                target = safe_output(self.workspace, "projects/" + name)
                if target.exists():
                    target = safe_output(self.workspace,
                                         "projects/" + name + "_" + digest[:8])
                target.mkdir(parents=True)
                (target / filename).write_text(source, encoding="utf-8")
                (target / "README.md").write_text(
                    str(package.get("readme", objective)), encoding="utf-8")
                (target / "VERIFICATION.json").write_text(json.dumps(
                    {"language": key, "sha256": digest, "syntax_valid": True},
                    indent=2), encoding="utf-8")
                return MultiLanguageResult(
                    True, "Proyecto generado y verificado", str(target), attempt)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                feedback = str(exc)
        return MultiLanguageResult(
            False, "No supero verificacion: " + feedback, attempts=attempts)
