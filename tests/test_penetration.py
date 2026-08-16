# -*- coding: utf-8 -*-
"""Pruebas de penetracion del runner restringido.

Cada caso usa un vector que la lista negra de ``ast`` del taller NO detecta
(``getattr``, ``importlib``, acceso al ``open`` real via ``tokenize``...).
Si la frontera es real, ``verify()`` debe rechazarlos.
"""
import pathlib

from igris_os.programming.workshop import PythonWorkshop

PASSING_TESTS = (
    "import unittest\n"
    "from solution import ok\n"
    "class T(unittest.TestCase):\n"
    "    def test_ok(self): self.assertTrue(ok())\n"
)


def _rejected(tmp_path, solution) -> bool:
    result = PythonWorkshop(tmp_path).verify(solution, PASSING_TESTS)
    return not result.ok


def test_getattr_os_system_blocked(tmp_path):
    assert _rejected(
        tmp_path,
        "import os\ndef ok(): return True\n"
        "getattr(os, 'system')('echo pwned')\n",
    )


def test_importlib_subprocess_blocked(tmp_path):
    assert _rejected(
        tmp_path,
        "import importlib\ndef ok(): return True\n"
        "importlib.import_module('subprocess').Popen(['echo','pwned'])\n",
    )


def test_importlib_socket_blocked(tmp_path):
    assert _rejected(
        tmp_path,
        "import importlib\ndef ok(): return True\n"
        "importlib.import_module('socket')\n",
    )


def test_real_open_via_tokenize_outside_workspace_blocked(tmp_path):
    outside = tmp_path.parent / "igris_pwn.txt"
    solution = (
        "import tokenize\ndef ok(): return True\n"
        f"tokenize._builtin_open({str(outside)!r}, 'w').write('pwned')\n"
    )
    assert _rejected(tmp_path, solution)
    assert not outside.exists()


def test_os_open_raw_fd_blocked(tmp_path):
    assert _rejected(
        tmp_path,
        "import os\ndef ok(): return True\n"
        "os.open('C:/x', os.O_RDONLY)\n",
    )


def test_open_builtin_outside_workspace_blocked(tmp_path):
    outside = tmp_path.parent / "igris_pwn2.txt"
    solution = (
        "def ok(): return True\n"
        f"open({str(outside)!r}, 'w').write('pwned')\n"
    )
    assert _rejected(tmp_path, solution)
    assert not outside.exists()


def test_legit_solution_still_runs(tmp_path):
    result = PythonWorkshop(tmp_path).verify(
        "def add(a, b):\n    return a + b\n",
        "import unittest\nfrom solution import add\n"
        "class T(unittest.TestCase):\n"
        "    def test_add(self): self.assertEqual(add(2, 3), 5)\n",
    )
    assert result.ok
    assert (pathlib.Path(tmp_path) / "verification.json").exists()
