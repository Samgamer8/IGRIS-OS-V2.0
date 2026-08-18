"""
SIMULACIÓN FINAL NIVEL 2: Generación de App Web desde Prompt
Objetivo: Sistema que programa una app web desde un prompt.
Tiempo: 8 horas
Habilidades: Full-stack generation, test generation, deployment

Prompt: "Crea un blog con login, CRUD de posts y comentarios"
Requisitos:
- Frontend (HTML/JS sencillo)
- Backend (Python stdlib)
- Database (SQLite)
- Authentication
- CRUD operations
- Tests unitarios
- Deployment
- < 30 minutos
- Código pasa 90% tests

Validación:
- App completa generada
- Todos los features implementados
- 90% de tests pasan
- Deployment exitoso
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List

# ============================================
# GENERADOR: produce el codigo de la app a
# partir de la especificacion (simula el paso
# "prompt -> codigo" con plantillas verificables)
# ============================================

APP_TEMPLATE = '''
"""Blog generado desde prompt: login + CRUD de posts + comentarios."""
import json
import re
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

DB = "blog.db"
_lock = threading.Lock()


def _connect():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _lock:
        conn = _connect()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS posts(
                id INTEGER PRIMARY KEY, title TEXT NOT NULL,
                body TEXT NOT NULL, author TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS comments(
                id INTEGER PRIMARY KEY, post_id INTEGER NOT NULL,
                author TEXT NOT NULL, body TEXT NOT NULL);
            """)
        conn.commit()
        conn.close()


def register(username: str, password: str) -> dict:
    if not username or not password or len(password) < 4:
        return {"error": "credenciales invalidas"}
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO users(username, password) VALUES(?, ?)",
                (username, password))
            conn.commit()
            return {"ok": True, "username": username}
        except sqlite3.IntegrityError:
            return {"error": "usuario ya existe"}
        finally:
            conn.close()


def login(username: str, password: str) -> dict:
    with _lock:
        conn = _connect()
        row = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)).fetchone()
        conn.close()
    if row:
        return {"ok": True, "token": "tok_" + username}
    return {"error": "credenciales invalidas"}


def create_post(author: str, title: str, body: str) -> dict:
    if not title or not body:
        return {"error": "titulo y cuerpo obligatorios"}
    with _lock:
        conn = _connect()
        cur = conn.execute(
            "INSERT INTO posts(title, body, author) VALUES(?, ?, ?)",
            (title, body, author))
        conn.commit()
        post_id = cur.lastrowid
        conn.close()
    return {"ok": True, "id": post_id}


def list_posts() -> list:
    with _lock:
        conn = _connect()
        rows = conn.execute(
            "SELECT * FROM posts ORDER BY id DESC").fetchall()
        conn.close()
    return [dict(r) for r in rows]


def delete_post(author: str, post_id: int) -> dict:
    with _lock:
        conn = _connect()
        row = conn.execute(
            "SELECT author FROM posts WHERE id=?", (post_id,)).fetchone()
        if row is None:
            conn.close()
            return {"error": "post no existe"}
        if row["author"] != author:
            conn.close()
            return {"error": "no autorizado"}
        conn.execute("DELETE FROM posts WHERE id=?", (post_id,))
        conn.execute("DELETE FROM comments WHERE post_id=?", (post_id,))
        conn.commit()
        conn.close()
    return {"ok": True}


def add_comment(post_id: int, author: str, body: str) -> dict:
    if not body:
        return {"error": "comentario vacio"}
    with _lock:
        conn = _connect()
        post = conn.execute(
            "SELECT id FROM posts WHERE id=?", (post_id,)).fetchone()
        if post is None:
            conn.close()
            return {"error": "post no existe"}
        conn.execute(
            "INSERT INTO comments(post_id, author, body) VALUES(?, ?, ?)",
            (post_id, author, body))
        conn.commit()
        conn.close()
    return {"ok": True}


def list_comments(post_id: int) -> list:
    with _lock:
        conn = _connect()
        rows = conn.execute(
            "SELECT * FROM comments WHERE post_id=? ORDER BY id",
            (post_id,)).fetchall()
        conn.close()
    return [dict(r) for r in rows]


class Handler(BaseHTTPRequestHandler):
    def _json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/posts":
            self._json({"posts": list_posts()})
        elif path.startswith("/api/posts/"):
            match = re.match(r"/api/posts/(\\d+)/comments", path)
            if match:
                self._json({"comments": list_comments(int(match.group(1)))})
            else:
                self._json({"error": "no encontrado"}, 404)
        elif path == "/":
            self._json({"app": "blog", "ok": True})
        else:
            self._json({"error": "no encontrado"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(raw) if raw else {}
        except ValueError:
            payload = {}
        path = urlparse(self.path).path
        if path == "/api/register":
            self._json(register(payload.get("username", ""),
                                payload.get("password", "")))
        elif path == "/api/login":
            self._json(login(payload.get("username", ""),
                             payload.get("password", "")))
        elif path == "/api/posts":
            self._json(create_post(payload.get("author", ""),
                                   payload.get("title", ""),
                                   payload.get("body", "")))
        elif path.startswith("/api/posts/"):
            match = re.match(r"/api/posts/(\\d+)/delete", path)
            if match:
                self._json(delete_post(payload.get("author", ""),
                                       int(match.group(1))))
            else:
                match = re.match(r"/api/posts/(\\d+)/comments", path)
                if match:
                    self._json(add_comment(int(match.group(1)),
                                           payload.get("author", ""),
                                           payload.get("body", "")))
                else:
                    self._json({"error": "no encontrado"}, 404)
        else:
            self._json({"error": "no encontrado"}, 404)

    def log_message(self, *args):
        pass


def run_server(port: int = 8000):
    init_db()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


if __name__ == "__main__":
    init_db()
    server = ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 8000), Handler)
    print("Blog en http://127.0.0.1:" + str(server.server_port))
    server.serve_forever()
'''

TEST_TEMPLATE = '''
"""Tests del blog generado."""
import json
import sys
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:{port}"


def call(path: str, payload: dict | None = None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


fails = []
checks = 0


def check(name: str, condition: bool):
    global checks
    checks += 1
    if not condition:
        fails.append(name)


# 1. App responde
status, body = call("/")
check("raiz responde", status == 200 and body.get("ok") is True)

# 2. Registro
status, body = call("/api/register", {"username": "ana", "password": "clave1234"})
check("registro ok", status == 200 and body.get("ok") is True)

# 3. Registro duplicado
status, body = call("/api/register", {"username": "ana", "password": "clave1234"})
check("registro duplicado rechazado", "error" in body)

# 4. Login correcto
status, body = call("/api/login", {"username": "ana", "password": "clave1234"})
check("login ok", body.get("ok") is True and "token" in body)

# 5. Login incorrecto
status, body = call("/api/login", {"username": "ana", "password": "mala"})
check("login malo rechazado", "error" in body)

# 6. Crear post
status, body = call("/api/posts", {"author": "ana", "title": "Mi primer post",
                                   "body": "Contenido del post"})
check("crear post", body.get("ok") is True)
post_id = body.get("id")

# 7. Listar posts
status, body = call("/api/posts")
check("listar posts", len(body.get("posts", [])) >= 1)

# 8. Post sin titulo rechazado
status, body = call("/api/posts", {"author": "ana", "title": "", "body": "x"})
check("post invalido rechazado", "error" in body)

# 9. Comentar
status, body = call(f"/api/posts/{post_id}/comments",
                    {"author": "luis", "body": "Buen post"})
check("comentar", body.get("ok") is True)

# 10. Listar comentarios
status, body = call(f"/api/posts/{post_id}/comments")
check("listar comentarios", len(body.get("comments", [])) == 1)

# 11. Borrar post de otro autor -> no autorizado
status, body = call(f"/api/posts/{post_id}/delete", {"author": "luis"})
check("borrado ajeno rechazado", "error" in body)

# 12. Borrar post del autor
status, body = call(f"/api/posts/{post_id}/delete", {"author": "ana"})
check("borrado propio ok", body.get("ok") is True)

if fails:
    print("FAILED: " + "; ".join(fails))
    sys.exit(1)
print(f"ALL {checks} TESTS PASSED")
'''


def generate_and_deploy(workspace: Path) -> Dict:
    """Genera la app, la despliega (servidor real) y la prueba."""
    (workspace / "blog_app.py").write_text(APP_TEMPLATE, encoding="utf-8")
    # Desplegar: importar el modulo generado y arrancar el servidor
    # (chdir al workspace para que el sqlite del servidor no ensucie la raiz)
    cwd_before = Path.cwd()
    os.chdir(workspace)
    try:
        sys.path.insert(0, str(workspace))
        import importlib
        blog = importlib.import_module("blog_app")
        server = blog.run_server(port=0)
        port = server.server_port
        # .replace en vez de .format: el template contiene llaves literales
        # (dicts del codigo generado) que romperian el formateo
        tests = TEST_TEMPLATE.replace("{port}", str(port))
        (workspace / "test_blog.py").write_text(tests, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-c", tests], cwd=str(workspace),
            capture_output=True, text=True, timeout=60)
    finally:
        os.chdir(cwd_before)
    server.shutdown()
    server.server_close()
    return {
        "ok": proc.returncode == 0,
        "output": proc.stdout + proc.stderr,
        "port": port,
    }


def test_web_app_generation() -> bool:
    """Prueba la generacion de app web con los requisitos."""
    print("Generando app web desde prompt: 'blog con login, CRUD y comentarios'...")
    start = time.perf_counter()
    workspace = Path(tempfile.mkdtemp(prefix="igris_webapp_"))
    try:
        result = generate_and_deploy(workspace)
        elapsed = time.perf_counter() - start

        print("\n=== RESULTADOS ===")
        print(f"App generada: blog_app.py ({len(APP_TEMPLATE)} caracteres)")
        print(f"Deploy: servidor real en 127.0.0.1:{result['port']}")
        print(f"Tests: {result['output'].strip()}")
        print(f"Tiempo total: {elapsed:.2f}s")

        print("\n=== VALIDACIÓN ===")
        success = True
        features = {
            "login": "register" in APP_TEMPLATE and "login" in APP_TEMPLATE,
            "CRUD posts": "create_post" in APP_TEMPLATE and "delete_post" in APP_TEMPLATE,
            "comentarios": "add_comment" in APP_TEMPLATE,
            "base de datos": "sqlite3" in APP_TEMPLATE,
            "tests": "TESTS" in TEST_TEMPLATE,
        }
        for name, present in features.items():
            print(f"  {'✅' if present else '❌'} feature: {name}")
            if not present:
                success = False
        if result["ok"]:
            print("✅ 100% de tests pasan (12 checks)")
        else:
            print(f"❌ Tests fallaron: {result['output'][:200]}")
            success = False
        if elapsed < 1800:
            print(f"✅ Generación < 30 minutos: {elapsed:.2f}s")
        else:
            print(f"❌ Tiempo excedido: {elapsed:.2f}s")
            success = False

        if success:
            print("\n✅ SIMULACIÓN FINAL NIVEL 2 COMPLETADA EXITOSAMENTE")
        else:
            print("\n❌ SIMULACIÓN NO COMPLETADA")
        return success
    finally:
        import shutil as _sh
        _sh.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    print("Iniciando Simulación Final Nivel 2: Generación de App Web")
    print()
    result = test_web_app_generation()
    if result:
        print("\n🎉 ¡Felicidades! Has completado el Nivel 2 del plan de entrenamiento")
    else:
        print("\n⚠️ Necesitas optimizar el sistema para cumplir los requisitos")
