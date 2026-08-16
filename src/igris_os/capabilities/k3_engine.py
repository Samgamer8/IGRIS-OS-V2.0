"""Capacidades del motor LLM propio de IGRIS: Kimi K3 (port a Windows).

El motor vive en .tools/k3/ (fuentes, win_shims y binarios compilados con el
w64devkit interno; Apache-2.0, ver NOTICE). Estas capacidades permiten a IGRIS
verificar su motor contra la referencia exacta (k3.gate) y ejecutar inferencia
con un checkpoint local (k3.run), sin dependencias externas.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_TOOLS_K3 = _PROJECT_ROOT / ".tools" / "k3"
_BIN = _TOOLS_K3 / "bin"
_VERDICT = "ENGINE MATCHES THE REFERENCE EXACTLY"


def register_k3_capabilities(registry) -> None:
    registry.register(
        CapabilitySpec(
            "k3.gate",
            "Verifica el motor LLM propio (Kimi K3 port) contra la referencia exacta",
            ActionRisk.READ_ONLY,
            timeout_seconds=300,
            tags=("llm", "self_host", "verification"),
        ),
        lambda _: _k3_gate(),
    )
    registry.register(
        CapabilitySpec(
            "k3.run",
            "Ejecuta el motor K3 con un checkpoint local (config.json + model.safetensors)",
            ActionRisk.READ_ONLY,
            timeout_seconds=300,
            tags=("llm", "self_host", "inference"),
        ),
        lambda payload: _k3_run(payload),
    )


def _k3_gate() -> ExecutionResult:
    exe = _BIN / "k3_model.exe"
    if not exe.exists():
        return ExecutionResult.failure(
            "Motor no compilado: falta .tools/k3/bin/k3_model.exe (corre .tools/k3/build.ps1)",
            "K3_NOT_BUILT",
        )
    fixtures = _TOOLS_K3 / "tests" / "fixtures"
    try:
        proc = subprocess.run(
            [str(exe), str(fixtures)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult.timeout(120)
    out = proc.stdout + proc.stderr
    if proc.returncode == 0 and _VERDICT in out:
        gates = sum(1 for g in ("GATE 1", "GATE 2", "GATE 3") if g in out)
        verdict = out.split("VERDICT:", 1)[1].strip().splitlines()[0].strip()
        return ExecutionResult.success(
            "Motor K3 verificado contra la referencia exacta",
            gates=gates,
            verdict=verdict,
        )
    return ExecutionResult.failure(
        "El gate del motor K3 no paso", "K3_GATE_FAIL", stack_trace=out[-4000:]
    )


def _k3_run(payload: dict) -> ExecutionResult:
    exe = _BIN / "k3.exe"
    if not exe.exists():
        return ExecutionResult.failure(
            "Motor no compilado: falta .tools/k3/bin/k3.exe (corre .tools/k3/build.ps1)",
            "K3_NOT_BUILT",
        )
    model_dir = str(payload.get("model_dir", "") or "").strip()
    model_path = Path(model_dir) if model_dir else None
    has_checkpoint = bool(
        model_path
        and model_path.is_dir()
        and ((model_path / "config.json").exists() or (model_path / "model.safetensors").exists())
    )
    if not has_checkpoint:
        return ExecutionResult.failure(
            "Falta checkpoint local: model_dir debe contener config.json + model.safetensors",
            "K3_NO_MODEL",
        )
    prompt = str(payload.get("prompt", "") or "").strip()
    try:
        gen = max(1, min(int(payload.get("gen", 8) or 8), 512))
    except (TypeError, ValueError):
        gen = 8
    cmd = [str(exe), model_dir]
    if prompt:
        cmd += ["--prompt", prompt]
    cmd += ["--gen", str(gen), "--incremental"]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult.timeout(300)
    out = proc.stdout + proc.stderr
    if proc.returncode != 0:
        return ExecutionResult.failure(
            "k3 termino con error", "K3_RUN_FAIL", stack_trace=out[-4000:]
        )
    return ExecutionResult.success(
        "Inferencia completada con el motor propio",
        output=out[-6000:],
    )
