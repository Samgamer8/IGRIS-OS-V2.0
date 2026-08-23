import ast
import json
import re
from dataclasses import dataclass, field
from typing import Any

from igris_os.ai.ollama import ModelReply, OllamaClient


@dataclass(frozen=True, slots=True)
class GenerationResult:
    ok: bool
    files: dict[str, str] = field(default_factory=dict)
    structure: str = ""
    instructions: str = ""
    error: str = ""


class ProjectGenerator:
    TEMPLATES: dict[str, dict[str, str]] = {
        "python": {
            "package": (
                "pyproject.toml\nsrc/{name}/__init__.py\nsrc/{name}/core.py\nsrc/{name}/cli.py\n"
                "tests/test_{name}.py\ndocs/README.md\nDockerfile\nREADME.md\n"
            ),
        },
        "godot": {
            "platformer": (
                "project.godot\nscenes/main.tscn\nscenes/player.tscn\nscenes/enemy.tscn\n"
                "scenes/ui.tscn\nscripts/player.gd\nscripts/enemy.gd\nscripts/ui.gd\n"
                "scripts/save_manager.gd\nassets/tileset.tres\nassets/audio/\n"
            ),
            "rpg": (
                "project.godot\nscenes/main.tscn\nscenes/player.tscn\nscenes/npc.tscn\n"
                "scripts/player.gd\nscripts/inventory.gd\nscripts/dialog.gd\nscripts/quest.gd\n"
                "scripts/save_manager.gd\nassets/\n"
            ),
            "shooter": (
                "project.godot\nscenes/main.tscn\nscenes/player.tscn\nscenes/enemy.tscn\n"
                "scripts/player.gd\nscripts/weapon.gd\nscripts/projectile.gd\nscripts/ui.gd\nassets/\n"
            ),
        },
        "web": {
            "fullstack": (
                "backend/main.py\nbackend/models.py\nbackend/routes.py\nbackend/requirements.txt\n"
                "frontend/src/App.jsx\nfrontend/src/index.jsx\nfrontend/package.json\n"
                "frontend/vite.config.js\ndatabase/schema.sql\nREADME.md\n"
            ),
        },
    }

    def __init__(self, client: OllamaClient | None = None, model: str = "llama3") -> None:
        self.client = client or OllamaClient()
        self.model = model

    def generate_project(self, description: str, language: str, framework: str = "") -> GenerationResult:
        lang = language.lower().strip()
        framework = framework.strip().lower()
        templates = self.TEMPLATES.get(lang, self.TEMPLATES["python"])
        key = framework if framework in templates else next(iter(templates))
        structure = templates[key]
        project_name = re.sub(r"[^a-z0-9_]", "_", description.lower())[:20] or "project"
        structure = structure.replace("{name}", project_name)
        prompt = (
            "You are a senior engineer. Return ONLY raw file contents separated by '---FILE: path---' markers. "
            f"Generate a {lang} project{f' using {framework}' if framework else ''}.\n"
            f"Description: {description}\nProject name: {project_name}\nRequired structure:\n{structure}\n"
            "Include proper imports, error handling, docstrings, and unit tests where applicable.\n"
        )
        reply: ModelReply = self.client.generate(prompt, self.model)
        files = self._parse_marked(reply.text) if reply.ok else {}
        if not files:
            files = self._fallback_project(description, lang, framework, structure)
        validated = self._validate(files)
        instructions = self._instructions(description, lang, framework, list(validated.keys()))
        return GenerationResult(True, validated, structure, instructions)

    def generate_game(self, description: str, genre: str = "platformer") -> GenerationResult:
        genre = genre.lower().strip()
        templates = self.TEMPLATES.get("godot", {})
        key = genre if genre in templates else "platformer"
        structure = templates[key]
        prompt = (
            "You are a Godot 4 expert. Return ONLY raw file contents separated by '---FILE: path---' markers. "
            f"Generate a complete {genre} game.\nDescription: {description}\nRequired structure:\n{structure}\n"
            "Use Godot 4 GDScript syntax, proper class architecture, input actions, signals, and export variables.\n"
            "Include player controller with WASD/arrow keys, camera follow, and scene transitions.\n"
        )
        if genre == "platformer":
            prompt += "Include tileset collision, enemy patrol AI, UI HUD, audio effects, and JSON save/load.\n"
        elif genre == "rpg":
            prompt += "Include inventory system, NPC dialog trees, quest tracking, and save system.\n"
        elif genre == "shooter":
            prompt += "Include weapon switching, projectile physics, enemy spawning, and ammo system.\n"
        reply: ModelReply = self.client.generate(prompt, self.model)
        files = self._parse_marked(reply.text) if reply.ok else {}
        if not files:
            files = self._fallback_game(description, genre)
        validated = self._validate(files)
        instructions = (
            f"Open Godot 4, import folder as {genre} project, run main scene. "
            "WASD/arrows to move, Space/Left click to interact."
        )
        return GenerationResult(True, validated, structure, instructions)

    def generate_fullstack_app(self, description: str) -> GenerationResult:
        structure = self.TEMPLATES["web"]["fullstack"]
        prompt = (
            "You are a fullstack architect. Return ONLY raw file contents separated by '---FILE: path---' markers. "
            f"Generate a fullstack web app.\nDescription: {description}\nRequired structure:\n{structure}\n"
            "Backend: FastAPI with SQLAlchemy models, Pydantic schemas, CORS middleware, and API docs.\n"
            "Frontend: React with Vite, fetch API calls, routing, and responsive CSS.\n"
            "Database: PostgreSQL schema with proper indexes and relationships.\n"
            "Include error handling, validation, and health check endpoints.\n"
        )
        reply: ModelReply = self.client.generate(prompt, self.model)
        files = self._parse_marked(reply.text) if reply.ok else {}
        if not files:
            files = self._fallback_fullstack(description)
        validated = self._validate(files)
        instructions = (
            "Backend: cd backend && pip install -r requirements.txt && uvicorn main:app --reload\n"
            "Frontend: cd frontend && npm install && npm run dev\n"
            "Database: Apply database/schema.sql to PostgreSQL.\n"
            "API docs available at http://localhost:8000/docs"
        )
        return GenerationResult(True, validated, structure, instructions)

    def _parse_marked(self, text: str) -> dict[str, str]:
        files: dict[str, str] = {}
        parts = re.split(r"---FILE:\s*(.*?)\s*---", text)
        for i in range(1, len(parts), 2):
            path = parts[i].strip()
            content = parts[i + 1] if i + 1 < len(parts) else ""
            if path:
                files[path] = content.strip()
        return files

    def _validate(self, files: dict[str, str]) -> dict[str, str]:
        validated: dict[str, str] = {}
        for path, content in files.items():
            try:
                if path.endswith(".py"):
                    try:
                        ast.parse(content)
                    except SyntaxError as exc:
                        content = f"# syntax validation failed: {exc}\n" + content
                elif path.endswith(".js") or path.endswith(".jsx"):
                    if not re.search(
                        r"\b(function|const|let|var|class|async|await|import|export)\b", content
                    ):
                        content = "// validation placeholder\n" + content
                elif path.endswith(".gd"):
                    if not re.search(r"\b(func|class|extends|signal|export)\b", content):
                        content = "# validation placeholder\n" + content
                elif path.endswith(".sql"):
                    if not re.search(r"\b(CREATE|INSERT|SELECT|ALTER|INDEX)\b", content, re.IGNORECASE):
                        content = "-- validation placeholder\n" + content
                validated[path] = content
            except Exception as exc:
                validated[path] = f"# validation error: {exc}\n" + content
        return validated

    def _instructions(self, description: str, lang: str, framework: str, files: list[str]) -> str:
        lines = [f"# {description}", f"Language: {lang}", f"Framework: {framework or 'none'}", f"Files: {', '.join(files)}"]
        if lang == "python":
            lines.append("Setup: pip install -r requirements.txt && python -m <package>")
        elif lang == "godot":
            lines.append("Setup: Open project.godot in Godot 4 and run the main scene.")
        elif lang == "web":
            lines.extend([
                "Backend: cd backend && pip install -r requirements.txt && uvicorn main:app --reload",
                "Frontend: cd frontend && npm install && npm run dev",
                "Database: Apply database/schema.sql to PostgreSQL.",
            ])
        return "\n".join(lines)

    def _fallback_project(self, description: str, lang: str, framework: str, structure: str) -> dict[str, str]:
        name = re.sub(r"[^a-z0-9_]", "_", description.lower())[:20] or "project"
        if lang == "python":
            return {
                "pyproject.toml": f'[project]\nname = "{name}"\nversion = "0.1.0"\ndescription = "{description}"\nrequires-python = ">=3.10"\n\n[project.scripts]\n{name} = "{name}.cli:main"\n',
                f"src/{name}/__init__.py": f'"""Generated {description} package."""\n__version__ = "0.1.0"\n',
                f"src/{name}/core.py": f"class {name.title().replace('_', '')}:\n    def __init__(self) -> None:\n        self.data: list[dict[str, Any]] = []\n    def run(self) -> str:\n        return '{description}'\n    def add_item(self, item: dict[str, Any]) -> None:\n        self.data.append(item)\n",
                f"src/{name}/cli.py": "import argparse\nfrom .core import Main\n\ndef main() -> None:\n    parser = argparse.ArgumentParser(description='CLI tool')\n    parser.add_argument('--run', action='store_true', help='Run the tool')\n    args = parser.parse_args()\n    if args.run:\n        print(Main().run())\n",
                f"tests/test_{name}.py": f"import pytest\nfrom {name}.core import Main\n\ndef test_main_run():\n    assert Main().run() == '{description}'\n",
                "Dockerfile": "FROM python:3.11-slim\nWORKDIR /app\nCOPY pyproject.toml .\nRUN pip install -e .\nCOPY src/ src/\nCMD ['python', '-m', f'{name}.cli']\n",
                "README.md": f"# {description}\nAuto-generated Python project.\n",
            }
        if lang == "web":
            return {
                "backend/main.py": "from fastapi import FastAPI\nfrom fastapi.middleware.cors import CORSMiddleware\n\napp = FastAPI(title='API', description='Generated API')\n\napp.add_middleware(\n    CORSMiddleware,\n    allow_origins=['*'],\n    allow_methods=['*'],\n    allow_headers=['*'],\n)\n\n@app.get('/')\ndef read_root():\n    return {'message': '" + description + "'}\n\n@app.get('/health')\ndef health():\n    return {'status': 'ok'}\n",
                "backend/models.py": "from sqlalchemy import Column, Integer, String\nfrom sqlalchemy.ext.declarative import declarative_base\n\nBase = declarative_base()\n\nclass Item(Base):\n    __tablename__ = 'items'\n    id = Column(Integer, primary_key=True)\n    name = Column(String(255), nullable=False)\n",
                "backend/requirements.txt": "fastapi==0.111.0\nuvicorn==0.30.0\nsqlalchemy==2.0.30\npsycopg2-binary==2.9.9\n",
                "frontend/src/App.jsx": "import { useState, useEffect } from 'react';\nexport default function App() {\n  const [data, setData] = useState(null);\n  useEffect(() => { fetch('/api/').then(r => r.json()).then(setData); }, []);\n  return <div><h1>App</h1><pre>{JSON.stringify(data, null, 2)}</pre></div>;\n}\n",
                "frontend/package.json": json.dumps({"name": "frontend", "private": True, "version": "0.0.0", "scripts": {"dev": "vite", "build": "vite build"}}, indent=2),
                "database/schema.sql": "CREATE TABLE IF NOT EXISTS items (id SERIAL PRIMARY KEY, name TEXT NOT NULL);\n",
                "README.md": f"# {description}\n",
            }
        return {"README.md": f"# {description}\nGenerated {lang} project.\n"}

    def _fallback_game(self, description: str, genre: str) -> dict[str, str]:
        if genre == "platformer":
            return {
                "project.godot": "; Engine configuration file.\nconfig_version=5\n[application]\n\n[input]\nmove_left=InputEventKey\nmove_right=InputEventKey\njump=InputEventKey\n",
                "scenes/main.tscn": '[gd_scene load_steps=2 format=3 uid="uid://main"]\n[ext_resource type="PackedScene" uid="uid://player" path="res://scenes/player.tscn"]\n[node name="Main" type="Node2D"]\n[node name="Player" parent="." instance=ExtResource("uid://player")]\n',
                "scenes/player.tscn": '[gd_scene load_steps=2 format=3 uid="uid://player"]\n[node name="Player" type="CharacterBody2D"]\n[node name="Sprite2D" type="Sprite2D" parent="."]\n[node name="CollisionShape2D" type="CollisionShape2D" parent="."]\n[node name="Camera2D" type="Camera2D" parent="."]\n',
                "scripts/player.gd": "extends CharacterBody2D\nconst SPEED = 300.0\nconst JUMP_VELOCITY = -400.0\nvar gravity = 980.0\nfunc _physics_process(delta):\n    if not is_on_floor():\n        velocity.y += gravity * delta\n    if Input.is_action_just_pressed('jump') and is_on_floor():\n        velocity.y = JUMP_VELOCITY\n    var direction = Input.get_axis('move_left', 'move_right')\n    velocity.x = direction * SPEED\n    move_and_slide()\n",
                "scripts/enemy.gd": "extends CharacterBody2D\n@export var patrol_distance: float = 100.0\n@export var speed: float = 100.0\nvar start_x: float = 0.0\nvar direction: int = 1\nfunc _ready() -> void:\n    start_x = position.x\nfunc _physics_process(delta):\n    position.x += direction * speed * delta\n    if abs(position.x - start_x) > patrol_distance:\n        direction *= -1\n",
                "scripts/ui.gd": "extends CanvasLayer\nfunc _ready() -> void:\n    pass\n",
                "scripts/save_manager.gd": "extends Node\nconst SAVE_PATH = 'user://savegame.json'\nfunc save_game(data: dict) -> void:\n    var file = FileAccess.open(SAVE_PATH, FileAccess.WRITE)\n    if file:\n        file.store_string(JSON.stringify(data))\nfunc load_game() -> dict:\n    var file = FileAccess.open(SAVE_PATH, FileAccess.READ)\n    return JSON.parse_string(file.get_as_text()) if file else {}\n",
            }
        if genre == "rpg":
            return {
                "project.godot": "; Engine configuration file.\nconfig_version=5\n",
                "scenes/main.tscn": '[gd_scene load_steps=2 format=3 uid="uid://main"]\n[node name="Main" type="Node2D"]\n',
                "scripts/player.gd": "extends CharacterBody2D\nconst SPEED = 200.0\nfunc _physics_process(delta):\n    var direction = Input.get_vector('ui_left', 'ui_right', 'ui_up', 'ui_down')\n    velocity = direction * SPEED\n    move_and_slide()\n",
                "scripts/inventory.gd": "extends Node\nvar items: Array[String] = []\nsignal inventory_changed\nfunc add_item(item: String) -> void:\n    items.append(item)\n    inventory_changed.emit()\nfunc remove_item(item: String) -> void:\n    items.erase(item)\n    inventory_changed.emit()\n",
                "scripts/dialog.gd": "extends CanvasLayer\nsignal dialog_finished\nvar lines: Array[String] = []\nvar current_line: int = 0\nfunc start(dialog_lines: Array[String]) -> void:\n    lines = dialog_lines\n    current_line = 0\n    show()\nfunc next_line() -> void:\n    current_line += 1\n    if current_line >= lines.size():\n        hide()\n        dialog_finished.emit()\n",
                "scripts/quest.gd": "extends Node\nvar quests: dict = {}\nsignal quest_updated\nfunc start_quest(id: String) -> void:\n    quests[id] = {'active': True, 'completed': False}\n    quest_updated.emit()\nfunc complete_quest(id: String) -> void:\n    if id in quests:\n        quests[id]['completed'] = True\n        quests[id]['active'] = False\n        quest_updated.emit()\n",
                "scripts/save_manager.gd": "extends Node\nconst SAVE_PATH = 'user://savegame.json'\nfunc save_game(data: dict) -> void:\n    var file = FileAccess.open(SAVE_PATH, FileAccess.WRITE)\n    if file:\n        file.store_string(JSON.stringify(data))\nfunc load_game() -> dict:\n    var file = FileAccess.open(SAVE_PATH, FileAccess.READ)\n    return JSON.parse_string(file.get_as_text()) if file else {}\n",
            }
        if genre == "shooter":
            return {
                "project.godot": "; Engine configuration file.\nconfig_version=5\n[input]\nshoot=InputEventMouseButton\n",
                "scenes/main.tscn": '[gd_scene load_steps=2 format=3 uid="uid://main"]\n[node name="Main" type="Node2D"]\n',
                "scripts/player.gd": "extends CharacterBody2D\nconst SPEED = 300.0\nfunc _physics_process(delta):\n    var direction = Input.get_vector('ui_left', 'ui_right', 'ui_up', 'ui_down')\n    velocity = direction * SPEED\n    move_and_slide()\nfunc shoot() -> void:\n    var projectile = preload('res://scripts/projectile.gd').new()\n    projectile.position = position\n    projectile.direction = (get_global_mouse_position() - position).normalized()\n    get_parent().add_child(projectile)\n",
                "scripts/weapon.gd": "extends Node\n@export var damage: int = 10\n@export var fire_rate: float = 0.5\n@export var ammo: int = 30\nvar can_shoot: bool = true\nfunc shoot() -> void:\n    if ammo > 0 and can_shoot:\n        can_shoot = False\n        ammo -= 1\n        await get_tree().create_timer(fire_rate).timeout\n        can_shoot = True\n",
                "scripts/projectile.gd": "extends CharacterBody2D\n@export var speed: float = 800.0\n@export var lifetime: float = 2.0\nvar direction: Vector2 = Vector2.RIGHT\nfunc _ready() -> void:\n    await get_tree().create_timer(lifetime).timeout\n    queue_free()\nfunc _physics_process(delta):\n    velocity = direction * speed\n    move_and_slide()\n",
                "scripts/ui.gd": "extends CanvasLayer\nfunc _ready() -> void:\n    pass\n",
            }
        return {"README.md": f"# {description}\nGenerated {genre} game.\n"}

    def _fallback_fullstack(self, description: str) -> dict[str, str]:
        return {
            "backend/main.py": "from fastapi import FastAPI\nfrom fastapi.middleware.cors import CORSMiddleware\n\napp = FastAPI(title='API', description='Generated API')\n\napp.add_middleware(\n    CORSMiddleware,\n    allow_origins=['*'],\n    allow_methods=['*'],\n    allow_headers=['*'],\n)\n\n@app.get('/')\ndef read_root():\n    return {'message': '" + description + "'}\n\n@app.get('/health')\ndef health():\n    return {'status': 'ok'}\n",
            "backend/models.py": "from sqlalchemy import Column, Integer, String\nfrom sqlalchemy.ext.declarative import declarative_base\n\nBase = declarative_base()\n\nclass Item(Base):\n    __tablename__ = 'items'\n    id = Column(Integer, primary_key=True)\n    name = Column(String(255), nullable=False)\n",
            "backend/routes.py": "from fastapi import APIRouter\nfrom pydantic import BaseModel\n\nrouter = APIRouter()\n\nclass ItemCreate(BaseModel):\n    name: str\n\n@router.get('/items')\ndef list_items():\n    return []\n\n@router.post('/items')\ndef create_item(item: ItemCreate):\n    return {'name': item.name}\n",
            "backend/requirements.txt": "fastapi==0.111.0\nuvicorn==0.30.0\nsqlalchemy==2.0.30\npsycopg2-binary==2.9.9\n",
            "frontend/src/App.jsx": "import { useState, useEffect } from 'react';\nexport default function App() {\n  const [data, setData] = useState(null);\n  useEffect(() => { fetch('/api/').then(r => r.json()).then(setData); }, []);\n  return <div><h1>App</h1><pre>{JSON.stringify(data, null, 2)}</pre></div>;\n}\n",
            "frontend/package.json": json.dumps({"name": "frontend", "private": True, "version": "0.0.0", "scripts": {"dev": "vite", "build": "vite build"}}, indent=2),
            "database/schema.sql": "CREATE TABLE IF NOT EXISTS items (id SERIAL PRIMARY KEY, name TEXT NOT NULL);\n",
            "README.md": f"# {description}\n",
        }
