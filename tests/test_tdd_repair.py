from pathlib import Path

from igris_os.programming import (
    EngineeringWorkflow, PythonTddMicroRepairer, PythonTddProjectRepairer,
)


def test_tdd_repairer_repairs_simple_math_project(tmp_path: Path):
    (tmp_path / "app.py").write_text(
        "def add(a, b):\n    return 0\n\ndef multiply(a, b):\n    return 0\n",
        encoding="utf-8",
    )
    (tmp_path / "test_app.py").write_text(
        "from app import add, multiply\n\n"
        "def test_add():\n    assert add(2, 3) == 5\n    assert add(-1, 4) == 3\n\n"
        "def test_multiply():\n    assert multiply(3, 4) == 12\n    assert multiply(-2, 5) == -10\n",
        encoding="utf-8",
    )

    before = EngineeringWorkflow().run(
        tmp_path, ("python", "-m", "pytest", "-q"), confirmed=True, timeout=20)
    assert before.run is not None
    assert before.run.returncode != 0

    result = PythonTddMicroRepairer().repair(tmp_path)

    assert result.ok
    assert result.changed_files == ("app.py",)
    after = EngineeringWorkflow().run(
        tmp_path, ("python", "-m", "pytest", "-q"), confirmed=True, timeout=20)
    assert after.run is not None
    assert after.run.returncode == 0


def test_tdd_repairer_reverts_unverified_changes(tmp_path: Path):
    original = "def convert(value):\n    return None\n"
    (tmp_path / "app.py").write_text(original, encoding="utf-8")
    (tmp_path / "test_app.py").write_text(
        "from app import convert\n\n"
        "def test_convert():\n    assert convert('abc') == {'unsupported': 'shape'}\n",
        encoding="utf-8",
    )

    result = PythonTddMicroRepairer().repair(tmp_path)

    assert not result.ok
    assert (tmp_path / "app.py").read_text(encoding="utf-8") == original


def test_project_tdd_repairer_finds_repairable_module_in_multifile_project(tmp_path: Path):
    (tmp_path / "main.py").write_text(
        "from service import total_items\n\n"
        "def run(items):\n    return total_items(items)\n",
        encoding="utf-8",
    )
    (tmp_path / "service.py").write_text(
        "def total_items(items):\n    return 0\n",
        encoding="utf-8",
    )
    (tmp_path / "test_service.py").write_text(
        "from main import run\nfrom service import total_items\n\n"
        "def test_total_items():\n    assert total_items(['a', 'b', 'c']) == 3\n\n"
        "def test_run_delegates_to_service():\n    assert run(['x', 'y']) == 2\n",
        encoding="utf-8",
    )

    result = PythonTddProjectRepairer().repair(tmp_path)

    assert result.ok
    assert result.changed_files == ("service.py",)
    after = EngineeringWorkflow().run(
        tmp_path, ("python", "-m", "pytest", "-q"), confirmed=True, timeout=20)
    assert after.run is not None
    assert after.run.returncode == 0
