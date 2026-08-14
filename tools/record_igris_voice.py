import argparse
from pathlib import Path

from igris_os.voice.dataset import (
    PILOT_SCRIPT, TRAINING_SESSION_1, VoiceDatasetRecorder,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Graba la voz autorizada de IGRIS")
    parser.add_argument("--device", default="Micrófono (Realtek(R) Audio)")
    parser.add_argument("--output", default="runtime/voice_dataset/pilot")
    parser.add_argument("--consent", action="store_true")
    parser.add_argument("--mode", choices=("pilot", "training1"), default="pilot")
    args = parser.parse_args()
    if not args.consent:
        parser.error("Debes confirmar --consent para grabar tu propia voz")
    recorder = VoiceDatasetRecorder(Path(args.output), args.device)
    samples = []
    script = TRAINING_SESSION_1 if args.mode == "training1" else PILOT_SCRIPT
    print("Lee cada frase con tono natural, firme y constante.")
    for index, phrase in enumerate(script, 1):
        print(f"\n[{index}/{len(script)}] {phrase}")
        answer = input("Pulsa Enter para grabar 10 segundos, o escribe s para saltar: ")
        if answer.strip().casefold() == "s":
            continue
        sample = recorder.record(index, phrase)
        samples.append(sample)
        print(f"Guardada: {sample.seconds:.1f}s")
    manifest = recorder.save_manifest(samples)
    print(f"Sesión terminada: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
