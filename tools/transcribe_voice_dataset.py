import argparse
import json
import subprocess
from pathlib import Path

from faster_whisper import WhisperModel


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="small")
    args = parser.parse_args()
    root = Path(args.output).resolve()
    audio_root = root / "audio"
    audio_root.mkdir(parents=True, exist_ok=True)
    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    records = []
    index = 1
    for part, raw_source in enumerate(args.input, 1):
        source = Path(raw_source).resolve()
        segments, info = model.transcribe(
            str(source), language="es", beam_size=5,
            vad_filter=True, word_timestamps=True,
            condition_on_previous_text=False)
        for segment in segments:
            text = segment.text.strip()
            length = float(segment.end - segment.start)
            if not text or length < 0.8 or length > 30:
                continue
            output = audio_root / f"{index:04d}.wav"
            run = subprocess.run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{segment.start:.3f}", "-t", f"{length:.3f}",
                "-i", str(source), "-ar", "24000", "-ac", "1",
                "-c:a", "pcm_s16le", str(output),
            ], capture_output=True, text=True, timeout=45)
            if run.returncode != 0:
                raise RuntimeError(run.stderr[-1000:] or "Fallo de corte")
            records.append({
                "index": index, "audio": str(output), "text": text,
                "source": str(source), "source_part": part,
                "start": round(segment.start, 3),
                "end": round(segment.end, 3),
                "seconds": round(length, 3),
                "avg_logprob": round(float(segment.avg_logprob), 4),
            })
            index += 1
    manifest = root / "transcribed_segments.json"
    manifest.write_text(json.dumps({
        "model": args.model, "language": "es", "segments": records,
        "count": len(records),
        "total_seconds": round(sum(item["seconds"] for item in records), 3),
        "requires_text_review": True,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
