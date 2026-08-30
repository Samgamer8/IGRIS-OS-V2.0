from __future__ import annotations

import os
import shutil

from igris_os.application.node_staging import StrictNodeStagingDeveloper


class CertifiedNodeStagingDeveloper(StrictNodeStagingDeveloper):
    """Variante Windows certificada con invocación segura de tsc.cmd."""

    @staticmethod
    def commands(language: str) -> tuple[tuple[str, ...], ...]:
        if language == "typescript":
            tsc = shutil.which("tsc")
            if not tsc:
                return (("tsc_missing",),)
            comspec = os.environ.get("ComSpec", "C:\\Windows\\System32\\cmd.exe")
            strict = (
                comspec, "/d", "/s", "/c", tsc,
                "--strict", "--noEmit", "--module", "nodenext",
                "--target", "ES2022", "main.ts",
            )
            emit = (
                comspec, "/d", "/s", "/c", tsc,
                "--noCheck", "--module", "nodenext", "--target", "ES2022",
                "--outDir", "dist", "--rootDir", ".",
            )
            return strict, emit, ("node", "--test", "dist/test_*.js")
        return super(CertifiedNodeStagingDeveloper,
                     CertifiedNodeStagingDeveloper).commands(language)
