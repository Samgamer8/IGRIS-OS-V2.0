import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


FILTERS = (
    "highpass=f=90,lowpass=f=7800,"
    "afftdn=nr=24:nf=-40:tn=1:gs=10,"
    "loudnorm=I=-18:TP=-2:LRA=7,"
    "agate=threshold=0.006:ratio=2:attack=15:release=220")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="Micrófono (Realtek(R) Audio)")
    parser.add_argument("--output", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--consent", action="store_true")
    args = parser.parse_args()
    if not args.consent:
        parser.error("Debes confirmar --consent")
    root = Path(args.output).resolve()
    root.mkdir(parents=True, exist_ok=True)
    raw = root / "narration_raw.wav"
    clean = root / "narration_clean.wav"
    transcript = Path(args.text).resolve()
    input("Pulsa Enter para COMENZAR. Después lee el texto completo: ")
    process = subprocess.Popen([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "dshow", "-i", f"audio={args.device}",
        "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(raw),
    ], stdin=subprocess.PIPE, text=True)
    input("GRABANDO. Pulsa Enter únicamente cuando termines toda la narración: ")
    process.communicate("q\n", timeout=15)
    if process.returncode != 0 or not raw.is_file():
        raise RuntimeError("La grabación continua falló")
    run = subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw),
        "-af", FILTERS, "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le",
        str(clean),
    ], capture_output=True, text=True, timeout=120)
    if run.returncode != 0:
        raise RuntimeError(run.stderr[-1000:] or "La limpieza falló")
    manifest = {
        "speaker_consent": True,
        "purpose": "voz original autorizada para IGRIS OS",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "raw": str(raw), "clean": str(clean), "transcript": str(transcript),
        "segmented": False,
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("NARRACIÓN GUARDADA Y LIMPIADA:", clean)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
