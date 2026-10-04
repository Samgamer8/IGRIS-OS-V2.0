from pathlib import Path
from dataclasses import replace

from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult


def register_neural_image(registry):
    registry.register(CapabilitySpec(
        'image.neural_sphere', 'Dibuja una o dos esferas neuronales y verifica el PNG; no IA generativa',
        ActionRisk.WRITE_WORKSPACE, True, timeout_seconds=60,
        tags=('image', 'procedural', 'local')), render_neural_image)


def render_neural_image(payload):
    from igris_os.multimedia.neural_image import NeuralImageRenderer
    progress = payload.get('on_progress')
    try:
        if progress:
            progress(15, 'Dibujando esferas neuronales en la mision')
        result = NeuralImageRenderer(Path(payload['workspace'])).render(
            count=payload.get('count', 2), width=payload.get('width', 1920), height=payload.get('height', 1080))
        if progress:
            progress(100, 'PNG guardado y verificado')
        artifact = {**result, 'media_type': 'image/png'}
        reply = ExecutionResult.success('Imagen creada y verificada mediante dibujo programatico local',
                        **result, artifact=artifact)
        return replace(reply, payload_output={'artifact': artifact})
    except (ValueError, OSError, RuntimeError) as exc:
        return ExecutionResult.failure(str(exc), 'NEURAL_IMAGE_FAILED')