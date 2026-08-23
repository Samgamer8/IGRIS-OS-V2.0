from igris_os.programming import PythonWorkshop


def test_verified_python_project(tmp_path):
    result = PythonWorkshop(tmp_path).verify(
        "def add(a, b):\n    return a + b\n",
        "import unittest\nfrom solution import add\n"
        "class T(unittest.TestCase):\n"
        "    def test_add(self): self.assertEqual(add(2, 3), 5)\n",
    )
    assert result.ok
    assert (tmp_path / "verification.json").exists()


def test_broken_tests_fail(tmp_path):
    result = PythonWorkshop(tmp_path).verify(
        "def add(a, b): return 0\n",
        "import unittest\nfrom solution import add\n"
        "class T(unittest.TestCase):\n"
        "    def test_add(self): self.assertEqual(add(2, 3), 5)\n",
    )
    assert not result.ok


def test_dangerous_code_is_blocked(tmp_path):
    result = PythonWorkshop(tmp_path).verify(
        "import subprocess\n", "import unittest\n")
    assert not result.ok


def test_generated_tests_are_security_checked(tmp_path):
    result = PythonWorkshop(tmp_path).verify(
        "def ok(): return True\n",
        "import shutil\nshutil.rmtree('datos')\n")
    assert not result.ok
    assert "peligrosa" in result.message


def test_destructive_attribute_calls_are_blocked(tmp_path):
    result = PythonWorkshop(tmp_path).verify(
        "from pathlib import Path\ndef clean(): Path('x').unlink()\n",
        "import unittest\n")
    assert not result.ok
    assert "sistema" in result.message


def test_lint_flags_undefined_name(tmp_path):
    report = PythonWorkshop(tmp_path).lint(
        "def f():\n    return no_existe\n")
    assert not report.ok
    assert any(issue.code == "E0602" for issue in report.issues)


def test_lint_accepts_clean_code(tmp_path):
    assert PythonWorkshop(tmp_path).lint(
        "def add(a, b):\n    return a + b\n").ok


def test_dependencies_classify_stdlib_vs_third_party(tmp_path):
    deps = PythonWorkshop(tmp_path).dependencies(
        "import os\nimport numpy as np\n")
    assert "os" in deps.stdlib
    assert "numpy" in deps.third_party


def test_verify_blocks_undefined_name(tmp_path):
    result = PythonWorkshop(tmp_path).verify(
        "def f():\n    return no_existe\n", "import unittest\n")
    assert not result.ok
    assert "Lint" in result.message
