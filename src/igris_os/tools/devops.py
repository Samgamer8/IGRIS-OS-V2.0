from __future__ import annotations

import json
import re
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
