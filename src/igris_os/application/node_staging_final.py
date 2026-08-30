from __future__ import annotations

from igris_os.application.node_staging import StrictNodeStagingDeveloper
from igris_os.application.node_staging_v3 import _typescript_cli


class FinalNodeStagingDeveloper(StrictNodeStagingDeveloper):
    """Ruta final JS/TS con compilación y tests sin shell ni descargas."""

    @staticmethod
    def commands(language: str) -> tuple[tuple[str, ...], ...]:
        if language == "typescript":
            cli = _typescript_cli()
            if not cli:
                return (("typescript_cli_missing",),)
            return (
                ("node", cli, "--strict", "--noEmit", "--module", "nodenext",
                 "--target", "ES2022", "main.ts"),
                ("node", cli, "--noCheck", "--module", "nodenext",
                 "--target", "ES2022", "--outDir", "dist", "--rootDir", ".",
                 "main.ts", "test_main.ts"),
                ("node", "--test", "dist/test_main.js"),
            )
        return StrictNodeStagingDeveloper.commands(language)
