from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True, slots=True)
class DeploymentResult:
    ok: bool
    message: str
    artifacts: tuple[str, ...] = ()
    logs: str = ""


class DevOpsPipeline:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def generate_dockerfile(self, language: str, base_image: str = "") -> str:
        dockerfiles = {
            "python": f"""FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
""",
            "rust": f"""FROM rust:1.75-slim AS builder
WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release
FROM debian:bookworm-slim
COPY --from=builder /app/target/release/app /usr/local/bin/app
EXPOSE 8080
CMD ["app"]
""",
            "node": f"""FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
EXPOSE 3000
CMD ["node", "dist/index.js"]
""",
            "cpp": f"""FROM debian:bookworm AS builder
WORKDIR /app
COPY CMakeLists.txt src/
RUN cmake -B build -S . && cmake --build build --config Release
FROM debian:bookworm-slim
COPY --from=builder /app/build/app /usr/local/bin/app
EXPOSE 8080
CMD ["app"]
""",
        }
        return dockerfiles.get(language, dockerfiles["python"])

    def generate_ci(self, language: str) -> str:
        templates = {
            "python": """name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.12'}
      - run: pip install -r requirements.txt
      - run: python -m pytest -q
""",
            "rust": """name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions-rs/toolchain@v1
        with: {toolchain: stable}
      - run: cargo test --all-targets
""",
            "node": """name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: {node-version: '20'}
      - run: npm ci
      - run: npm test
""",
        }
        return templates.get(language, templates["python"])

    def generate_deployment_script(self, target: str) -> str:
        if target == "azure":
            return """az group create --name igris-rg --location eastus
az appservice plan create --name igris-plan --resource-group igris-rg --sku B1 --is-linux
az webapp create --name igris-app --resource-group igris-rg --plan igris-plan --runtime "PYTHON|3.12"
az webapp deploy --name igris-app --resource-group igris-rg --src-path ./dist --type zip
"""
        if target == "docker":
            return """docker build -t igris-app .
docker run -d -p 8080:8080 --name igris igris-app
"""
        return ""

    def generate_release_notes(self, changes: Sequence[str]) -> str:
        notes = "# Release Notes\n\n"
        for change in changes:
            notes += f"- {change}\n"
        return notes

    def validate_environment(self) -> dict:
        tools = {
            "docker": "docker --version",
            "git": "git --version",
            "node": "node --version",
            "npm": "npm --version",
            "python": "python --version",
            "cargo": "cargo --version",
            "cmake": "cmake --version",
            "mvn": "mvn --version",
        }
        available = {}
        for tool, cmd in tools.items():
            try:
                import subprocess
                result = subprocess.run(cmd.split(), capture_output=True,
                                        text=True, timeout=5, check=False)
                available[tool] = result.returncode == 0
            except Exception:
                available[tool] = False
        return available


class MultimediaProPipeline:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        self.ffmpeg = self._find_ffmpeg()
        self.blender = self._find_blender()

    def transcode(self, source: Path, output: Path, *,
                  codec: str = "libx264", preset: str = "medium") -> DeploymentResult:
        if not self.ffmpeg:
            return DeploymentResult(False, "FFmpeg no disponible")
        cmd = [str(self.ffmpeg), "-i", str(source), "-c:v", codec,
               "-preset", preset, "-y", str(output)]
        try:
            result = self._run(cmd, "Transcode")
            if result.ok and output.exists():
                return DeploymentResult(True, "Transcode completado",
                                        (str(output),), result.stdout)
            return DeploymentResult(False, result.message, logs=result.stdout)
        except Exception as exc:
            return DeploymentResult(False, str(exc))

    def extract_audio(self, source: Path, output: Path,
                      format: str = "mp3") -> DeploymentResult:
        if not self.ffmpeg:
            return DeploymentResult(False, "FFmpeg no disponible")
        cmd = [str(self.ffmpeg), "-i", str(source), "-vn", "-acodec", "libmp3lame",
               "-q:a", "2", "-y", str(output)]
        try:
            result = self._run(cmd, "Extract audio")
            return DeploymentResult(result.ok, result.message,
                                    (str(output),) if result.ok else (),
                                    result.stdout)
        except Exception as exc:
            return DeploymentResult(False, str(exc))

    def generate_thumbnail(self, source: Path, output: Path,
                           time: float = 0.0) -> DeploymentResult:
        if not self.ffmpeg:
            return DeploymentResult(False, "FFmpeg no disponible")
        cmd = [str(self.ffmpeg), "-ss", str(time), "-i", str(source),
               "-vframes", "1", "-y", str(output)]
        try:
            result = self._run(cmd, "Thumbnail")
            return DeploymentResult(result.ok, result.message,
                                    (str(output),) if result.ok else (),
                                    result.stdout)
        except Exception as exc:
            return DeploymentResult(False, str(exc))

    def analyze_media(self, source: Path) -> dict:
        if not self.ffmpeg:
            return {"error": "FFmpeg no disponible"}
        cmd = [str(self.ffmpeg), "-i", str(source)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    timeout=10, check=False)
            info = {}
            for pattern in [r"Duration: (\d{2}:\d{2}:\d{2}\.\d+)",
                            r"Video: (\w+)",
                            r"Audio: (\w+)",
                            r"(\d{3,5}x\d{3,5})"]:
                match = re.search(pattern, result.stderr)
                if match:
                    info[pattern.split(":")[0].strip("()")] = match.group(1)
            return info
        except Exception as exc:
            return {"error": str(exc)}

    def _run(self, cmd: Sequence[str], label: str) -> DeploymentResult:
        try:
            result = subprocess.run(list(cmd), capture_output=True, text=True,
                                    timeout=60, check=False)
            ok = result.returncode == 0
            return DeploymentResult(
                ok, "OK" if ok else result.stderr.strip(),
                (), result.stdout.strip() if ok else result.stderr.strip(),
            )
        except subprocess.TimeoutExpired:
            return DeploymentResult(False, "timeout", diagnostics=("timeout",))
        except Exception as exc:
            return DeploymentResult(False, str(exc), diagnostics=(str(exc),))

    @staticmethod
    def _find_ffmpeg() -> Path | None:
        for name in ("ffmpeg", "ffmpeg.exe"):
            path = shutil.which(name)
            if path:
                return Path(path)
        return None

    @staticmethod
    def _find_blender() -> Path | None:
        for name in ("blender", "blender.exe"):
            path = shutil.which(name)
            if path:
                return Path(path)
        return None
