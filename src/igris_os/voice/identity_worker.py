from __future__ import annotations

import contextlib
import json
from pathlib import Path
import sys


SPAIN_MODEL_REPOSITORY = 'ResembleAI/Chatterbox-Multilingual-es-es'


def load_spanish_model(device: str):
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    from huggingface_hub import hf_hub_download
    from safetensors.torch import load_file

    t3_path = hf_hub_download(SPAIN_MODEL_REPOSITORY, filename='t3_es_es.safetensors')
    decoder_path = hf_hub_download(SPAIN_MODEL_REPOSITORY, filename='s3gen_v3.safetensors')
    model = ChatterboxMultilingualTTS.from_pretrained(device=device)
    model.t3.load_state_dict(load_file(t3_path, device='cpu'), strict=True)
    decoder_weights = load_file(decoder_path, device='cpu')
    current_weights = model.s3gen.state_dict()
    for buffer_name in ('tokenizer._mel_filters', 'tokenizer.window'):
        decoder_weights.setdefault(buffer_name, current_weights[buffer_name])
    model.s3gen.load_state_dict(decoder_weights, strict=True)
    return model


def synthesize(model, text: str, reference: Path, output: Path) -> None:
    if not text.strip():
        raise ValueError('No hay texto para sintetizar')
    if not reference.is_file() or reference.suffix.lower() != '.wav':
        raise ValueError('No existe el WAV de referencia')
    import soundfile
    import torch

    reference = reference.resolve()
    metadata = reference.stat()
    signature = (str(reference), metadata.st_mtime_ns, metadata.st_size)
    if getattr(model, '_igris_reference_signature', None) != signature:
        model.prepare_conditionals(str(reference), exaggeration=0.5)
        model._igris_reference_signature = signature
    minimum_samples = max(1, int(model.sr * len(text.split()) / 6))
    last_error: Exception | None = None
    # El fallo observado (repeticion de token que fuerza un EOS temprano) es
    # determinista para un texto dado: la misma semilla con los mismos
    # parametros siempre produce el mismo resultado degenerado. Cambiar solo
    # la semilla no basta si el patron de repeticion no depende del muestreo;
    # por eso cada reintento tambien endurece repetition_penalty, que es el
    # parametro que directamente castiga la repeticion causante del corte.
    attempts = ((42, 1.2), (43, 1.35), (44, 1.5), (45, 1.65))
    for seed, repetition_penalty in attempts:
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        try:
            audio = model.generate(
                text, language_id='es',
                exaggeration=0.5, cfg_weight=0.5, temperature=0.8,
                repetition_penalty=repetition_penalty)
            samples = audio.detach().cpu().numpy().reshape(-1)
        except (RuntimeError, ValueError) as exc:
            # Una semilla puede degenerar (p.ej. repeticion de token que fuerza
            # un EOS temprano y deja un tensor interno vacio). No se descarta
            # el intento completo: se prueba la siguiente semilla con mas
            # penalizacion de repeticion.
            last_error = exc
            continue
        if samples.size >= minimum_samples:
            soundfile.write(str(output), samples, model.sr, subtype='PCM_16')
            return
    if last_error is not None:
        raise ValueError(
            'La sintesis fallo en todas las semillas de reintento: ' + str(last_error))
    raise ValueError('La sintesis genero audio demasiado corto; no se reproducira una respuesta incompleta')


def main() -> None:
    model = None
    for line in sys.stdin:
        try:
            request = json.loads(line)
            with contextlib.redirect_stdout(sys.stderr):
                if model is None:
                    import torch

                    device = 'cuda' if torch.cuda.is_available() else 'cpu'
                    model = load_spanish_model(device)
                synthesize(model, request['text'], Path(request['reference']), Path(request['output']))
            result = {'ok': True}
        except Exception as exc:
            result = {'ok': False, 'error': str(exc)}
        print('IGRIS_VOICE:' + json.dumps(result), flush=True)


if __name__ == '__main__':
    main()