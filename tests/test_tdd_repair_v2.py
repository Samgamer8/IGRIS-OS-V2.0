"""Regresiones estructurales de la línea de reparación TDD de IGRIS OS."""

from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "relative_path",
    (
        "main.py",
        "src/igris_os/core/contracts.py",
        "src/igris_os/core/igrisd.py",
        "src/igris_os/programming/tdd_repair.py",
    ),
)
def test_critical_python_files_exist_and_compile(relative_path: str):
    """Los archivos críticos deben existir en V5 y tener sintaxis válida."""
    path = PROJECT_ROOT / relative_path

    assert path.is_file(), f"Falta archivo crítico de V5: {relative_path}"
    source = path.read_text(encoding="utf-8")
    assert source.strip(), f"Archivo crítico vacío: {relative_path}"
    compile(source, str(path), "exec")


@pytest.mark.parametrize(
    "relative_path",
    (
        "src/igris_os/core",
        "src/igris_os/application",
        "src/igris_os/programming",
        "src/igris_os/evaluation",
        "tests",
        "docs",
        "tools",
    ),
)
def test_required_v5_components_exist(relative_path: str):
    """La fuente canónica V5 debe conservar sus componentes esenciales."""
    assert (PROJECT_ROOT / relative_path).is_dir(), (
        f"Falta componente obligatorio de V5: {relative_path}"
    )