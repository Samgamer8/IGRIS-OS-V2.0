from __future__ import annotations

import os
from pathlib import Path

from igris_os.application.node_staging import StrictNodeStagingDeveloper


def _typescript_cli() -> str:
    appdata = os.environ.get("APPDATA", "")
    candidates = (
        Path(appdata) / "npm" / "node_modules" / "typescript" / "bin" / "tsc",
        Path(appdata) / "npm" / "node_modules" / "typescript" / "lib" / "tsc.js",
    )
    for path in candidates:
        if path.is_file():
            return str(path)
    return ""


class ProductionNodeStagingDeveloper(StrictNodeStagingDeveloper):
    """Invoca TypeScript mediante Node, sin shell ni resolución de .cmd."""

    @staticmethod
    def commands(language: str) -> tuple[tuple[str, ...], ...]:
        if language == "typescript":
            cli = _typescript_cli()
            if not cli:
                return (("typescript_cli_missing",),)
            strict = (
                "node", cli, "--strict", "--noEmit", "--module", "nodenext",
                "--target", "ES2022", "main.ts",
            )
            emit = (
                "node", cli, "--noCheck", "--module", "nodenext",
                "--target", "ES2022", "--outDir", "dist", "--rootDir", ".",
            )
            return strict, emit, ("node", "--test", "dist/test_*.js")
        return StrictNodeStagingDeveloper.commands(language)
