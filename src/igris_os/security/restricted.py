# -*- coding: utf-8 -*-
"""Ejecucion restringida de Python con gancho de auditoria (PEP 578).

El taller de programacion necesita una frontera REAL, no una lista negra de
``ast`` que se salta con ``getattr``/``importlib``. Este modulo ejecuta el
codigo generado en un subproceso aislado (``-I``) con un ``sys.addaudithook``
que bloquea, a nivel de interprete y sin importar como se invoquen, las
primitivas peligrosas:

- ejecucion de comandos y procesos (``os.system``, ``subprocess.Popen``...);
- red (``socket.*``);
- destructivas de sistema de archivos (``os.remove``, ``os.rename``...);
- apertura de archivos fuera del workspace (solo lectura de stdlib permitida);
- importacion de modulos peligrosos (``subprocess``, ``socket``, ``ctypes``...);
- los ``builtins`` peligrosos (``open``/``exec``/``eval``/``compile``...).

Por que esto si es solido: los eventos de auditoria se emiten en la primitiva
de C, de modo que ``getattr(os, "system")``, ``importlib.import_module`` o
alcanzar ``tokenize._builtin_open`` terminan disparando el mismo evento que se
bloquea aqui. Las listas negras de ``ast`` del taller siguen existiendo solo
como filtro previo de mensajes amables.

Limite conocido y honesto: sigue siendo Python puro sobre CPython. Un atacante
humano experto con conocimiento interno de CPython podria buscar escapes exoticos;
la unica garantia dura es el aislamiento de SO (AppContainer/contenedor). Esto
detiene todos los vectores realistas de un modelo que alucina o de un prompt
malicioso de nivel script-kiddie.
"""

from __future__ import annotations

import os
from pathlib import Path

from igris_os.security.sandbox import JobObjectSandbox, SandboxRun

# Eventos de auditoria que SIEMPRE se bloquean (primitivas, no modulos).
DENY_EVENTS = frozenset({
    # Ejecucion de codigo/procesos
    "os.system", "os.exec", "os.execve", "os.spawn", "os.posix_spawn",
    "os.fork", "os.forkpty", "os.kill", "os.killpg", "os.putenv",
    "subprocess.Popen",
    # Red
    "socket.__new__", "socket.bind", "socket.connect", "socket.connect_ex",
    "socket.getaddrinfo", "socket.getnameinfo", "socket.sendmsg",
    "socket.sendto",
    # FFI (permite limpiar el gancho o llamar a C arbitrario)
    "ctypes.dlopen", "ctypes.dlsym", "ctypes.addressof",
    # Destructivas / navegacion de sistema de archivos
    "os.remove", "os.unlink", "os.rename", "os.renames", "os.rmdir",
    "os.removedirs", "os.chmod", "os.chown", "os.truncate", "os.listdir",
    "os.scandir", "os.chdir", "os.mkdir", "os.link",
    "shutil.rmtree", "shutil.copytree", "shutil.move", "shutil.make_archive",
})

# Modulos cuya IMPORTACION se bloquea. "os" NO esta aqui: lo necesita unittest
# internamente, y sus funciones peligrosas ya estan cubiertas por eventos + la
# limpieza del modulo en el arranque.
DANGEROUS_IMPORTS = frozenset({
    "subprocess", "socket", "ctypes", "importlib", "shutil", "pathlib",
    "urllib", "http", "ftplib", "smtplib", "winreg", "msvcrt", "gc",
    "runpy", "pty", "multiprocessing", "pickle", "marshal", "codeop",
    "py_compile", "compileall", "ensurepip", "pip", "site", "asyncio",
    "aiohttp", "requests", "setuptools", "distutils", "concurrent",
    "telnetlib", "poplib", "imaplib", "nntplib", "xmlrpc", "wsgiref",
    "socketserver", "asyncore", "asynchat", "zipimport",
})

# Nombres de builtins que se eliminan para el codigo de usuario. ``__import__``
# se conserva porque la maquina de importacion lo necesita (pero los imports
# peligrosos se bloquean por evento).
STRIP_BUILTINS = ("open", "exec", "eval", "compile", "input", "breakpoint")

# Funciones de ``os`` sin evento de auditoria propio: se eliminan para cerrar
# el canal de descriptores crudos (os.open + os.read + os.write(fd)).
STRIP_OS = ("open", "read", "write", "fdopen", "dup", "dup2", "dup3",
            "close", "_exit", "abort", "startfile", "closerange")

_BOOTSTRAP = r"""
import os as _os
import sys as _sys
import types as _types
import builtins as _builtins
import traceback as _traceback
import unittest as _unittest

ROOT = _os.path.abspath(_sys.argv[1])
READ_ROOTS = (ROOT, _os.path.abspath(_sys.prefix),
              _os.path.abspath(_sys.base_prefix))

DENY = %(deny)s
DANGER = %(danger)s

# Referencias del arranque de confianza, guardadas ANTES de sanitizar.
_open = _builtins.open
_compile = _builtins.compile
_exec = _builtins.exec

def _within(path, roots):
    try:
        p = _os.path.normcase(_os.path.abspath(str(path)))
    except Exception:
        return False
    for r in roots:
        rn = _os.path.normcase(r)
        if p == rn or p.startswith(rn + _os.sep):
            return True
    return False

def _guard(event, args):
    if event in DENY:
        raise PermissionError("operacion bloqueada: " + event)
    if event == "import":
        name = args[0] if args else ""
        if name.split(".")[0] in DANGER:
            raise PermissionError("import bloqueado: " + name)
    if event == "open":
        if not args:
            return
        target = args[0]
        if isinstance(target, int):
            raise PermissionError("descriptor de archivo bloqueado")
        mode = args[1] if len(args) > 1 else "r"
        writable = any(c in mode for c in "wax+")
        if writable:
            if not _within(target, (ROOT,)):
                raise PermissionError("escritura fuera del workspace")
        elif not _within(target, READ_ROOTS):
            raise PermissionError("lectura fuera del workspace")

def _read(path):
    with _open(path, "r", encoding="utf-8") as fh:
        return fh.read()

try:
    sol_src = _read(_os.path.join(ROOT, "solution.py"))
    test_src = _read(_os.path.join(ROOT, "test_solution.py"))
except Exception as exc:
    _sys.stderr.write("SECURITY_GUARD: no se pudo leer el codigo: %%s" %% exc)
    _sys.exit(2)

# El gancho se instala DESPUES de importar el arranque de confianza, pero
# ANTES de ejecutar cualquier codigo generado.
_sys.addaudithook(_guard)

# Sanitizar builtins y os (modulo real, para que `import builtins`/`import os`
# tampoco expongan las primitivas).
for _name in %(strip_builtins)s:
    if hasattr(_builtins, _name):
        delattr(_builtins, _name)
for _name in %(strip_os)s:
    if hasattr(_os, _name):
        delattr(_os, _name)

_safe = {k: getattr(_builtins, k) for k in dir(_builtins)
         if k not in %(strip_builtins)s}

def _load(name, code, filename):
    mod = _types.ModuleType(name)
    mod.__file__ = filename
    g = mod.__dict__
    g["__builtins__"] = _safe
    g["__name__"] = name
    g["__package__"] = ""
    try:
        _exec(code, g)
    except SystemExit as exc:
        raise RuntimeError("el codigo llamo a sys.exit(%%r)" %% (exc.code,))
    _sys.modules[name] = mod
    return mod

try:
    sol_code = _compile(sol_src, _os.path.join(ROOT, "solution.py"), "exec")
    test_code = _compile(test_src, _os.path.join(ROOT, "test_solution.py"), "exec")
    _load("solution", sol_code, _os.path.join(ROOT, "solution.py"))
    test_mod = _load("test_solution", test_code,
                     _os.path.join(ROOT, "test_solution.py"))
    suite = _unittest.defaultTestLoader.loadTestsFromModule(test_mod)
    result = _unittest.TextTestRunner(verbosity=1).run(suite)
    _sys.exit(0 if result.wasSuccessful() else 1)
except SystemExit:
    raise
except BaseException as exc:
    _traceback.print_exc()
    _sys.stderr.write("SECURITY_GUARD: %%s" %% (exc,))
    _sys.exit(2)
"""


def run_restricted(root: Path, *, timeout: int = 20,
                   memory_limit_mb: int = 512,
                   cpu_seconds: int = 60) -> SandboxRun:
    """Ejecuta ``solution.py`` + ``test_solution.py`` de ``root`` confinados.

    Devuelve el mismo ``SandboxRun`` que ``JobObjectSandbox.run``:
    returncode 0 = tests ok, 1 = tests fallidos, 2 = bloqueo de seguridad.
    """
    bootstrap = _BOOTSTRAP % {
        "deny": repr(frozenset(DENY_EVENTS)),
        "danger": repr(frozenset(DANGEROUS_IMPORTS)),
        "strip_builtins": repr(tuple(STRIP_BUILTINS)),
        "strip_os": repr(tuple(STRIP_OS)),
    }
    env = _filtered_env()
    sandbox = JobObjectSandbox(memory_limit_mb=memory_limit_mb,
                               cpu_seconds=cpu_seconds)
    return sandbox.run([_sys_executable(), "-I", "-c", bootstrap, str(root)],
                       timeout=timeout, cwd=str(root), env=env)


def _sys_executable() -> str:
    import sys
    return sys.executable


def _filtered_env() -> dict[str, str]:
    """Copia el entorno sin variables que puedan contener secretos."""
    sensitive = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL",
                 "PRIVATE")
    clean: dict[str, str] = {}
    for key, value in os.environ.items():
        if any(frag in key.upper() for frag in sensitive):
            continue
        clean[key] = value
    return clean
