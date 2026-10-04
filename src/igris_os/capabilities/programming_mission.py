"""Entrada unica de los encargos de programacion del panel y la consola."""
from pathlib import Path

from igris_os.ai import OllamaClient, build_model_client
from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult
from igris_os.programming.mission_team import ProgrammingTeam
from igris_os.programming.mission_delivery import deliver_programming


def register_programming_mission(registry):
    registry.register(CapabilitySpec('programming.mission',
        'Planifica, programa con herramientas, prueba y revisa un encargo multiarchivo',
        ActionRisk.EXTERNAL, True, timeout_seconds=3600), execute_programming)
    registry.register(CapabilitySpec('programming.deliver',
        'Entrega los cambios revisados tras comprobar de nuevo su integridad y pruebas',
        ActionRisk.EXTERNAL, True, timeout_seconds=600), deliver_programming)


def execute_programming(payload):
    objective = str(payload.get('objective', '')).strip()
    root = str(payload.get('root', '')).strip()
    if (payload.get('requires_existing') and not root) or payload.get('requested_root'):
        return ExecutionResult(False, 'WORK_NEEDS_INPUT',
            'Necesito identificar el proyecto que debo modificar.', data={
                'work_status': 'needs_input', 'input_kind': 'project_path',
                'questions': ['¿Cual es la ruta completa de la carpeta del proyecto?'],
                'project_candidates': payload.get('project_candidates', []),
                'original_modified': False})
    # Si el propio encargo exige una biblioteca grafica externa, pidela de
    # forma determinista antes de invocar al planificador LLM. Asi una ruta
    # posterior nunca cae al chatbot ni el planificador intenta inventar una
    # prueba sin disponer de los assets que debe integrar.
    from igris_os.application.programming_intent import requires_external_graphic_resources
    if root and requires_external_graphic_resources(objective) and not payload.get('resource_roots'):
        return ExecutionResult(False, 'WORK_NEEDS_INPUT',
            'Necesito la biblioteca de recursos graficos indicada en el encargo.', data={
                'work_status': 'needs_input', 'input_kind': 'resource_path',
                'questions': ['¿Cual es la ruta completa de la carpeta con las piezas o modelos 3D que debo usar?'],
                'original_modified': False})
    if payload.get('active_project_job'):
        return ExecutionResult.failure('Ese proyecto tiene una mision en curso: ' +
            str(payload['active_project_job'])[:8], 'WORK_ALREADY_RUNNING')
    from igris_os.application.delivery_request import requested_delivery
    contract = requested_delivery(objective)
    # Re-evaluate the OS desktop location when resuming an older rc4 mission.
    destination = str(payload.get('destination') or contract.get('destination') or '')
    client = build_model_client(timeout=180)
    client.output_token_limit = 8192
    client.context_window = 32768
    team = ProgrammingTeam(client, Path(payload['workspace']),
        preferred_model=str(payload.get('model', '')),
        on_progress=payload.get('on_progress'), max_calls=payload.get('max_calls', 32),
        max_seconds=payload.get('max_seconds', 1800))
    return team.execute(objective, source=Path(root) if root else None,
        original_objective=str(payload.get('original_objective', '')),
        answers=payload.get('clarifications', []), allow_downloads=payload.get('allow_downloads') is True,
        destination=destination, resource_roots=payload.get('resource_roots', []),
        resume_report=str(payload.get('resume_report', '')), delivery_contract=contract)
