"""Examen de la ruta real de IGRIS sobre un repositorio deliberadamente defectuoso."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import time

from igris_os.ai import OllamaClient
from igris_os.ai.model_selection import coding_model_candidates
from igris_os.programming.mission_team import ProgrammingTeam
from igris_os.programming.mission_delivery import deliver_programming
from igris_os.programming.mission_workspace import save_json
from .acceptance_cases import CONTRACTS
from .external_acceptance import verify_candidate, source_hashes


BROKEN_REPOSITORY = {
    'storage.py': '''import json
from pathlib import Path

def load(path):
    return {}

def save(path, data):
    Path(path).write_text(json.dumps(data), encoding="utf-8")
''',
    'service.py': '''import storage

class Inventory:
    def __init__(self, path):
        self.path = path
        self.data = storage.load(path)

    def add(self, sku, quantity):
        self.data[sku] = quantity
        storage.save(self.path, self.data)

    def adjust(self, sku, delta):
        self.data[sku] += delta
        storage.save(self.path, self.data)

    def snapshot(self):
        return self.data
''',
    'report.py': 'def total_units(stock):\n    return sum(stock.values())\n',
    'app.py': '''from pathlib import Path
from service import Inventory
from report import total_units

def main():
    stock = Inventory(Path("stock.json"))
    print("Unidades:", total_units(stock.snapshot()))

if __name__ == "__main__":
    main()
''',
    'test_original.py': '''from report import total_units
from service import Inventory

def test_existing_reporting():
    assert total_units({"x": 2, "y": 4}) == 6

def test_add_valid_item(tmp_path):
    stock = Inventory(tmp_path / "items.json")
    stock.add("a", 3)
    assert stock.snapshot() == {"a": 3}
''',
    'README.md': '# Repositorio de examen\nEl inventario tiene errores de validacion y persistencia.\n',
}


def run_autonomy_exam(client, workspace, *, model='', max_calls=40, on_progress=None,
                      team_factory=ProgrammingTeam):
    workspace = Path(workspace).resolve()
    if workspace.exists():
        raise ValueError('El examen necesita una carpeta nueva para conservar la evidencia anterior')
    workspace.mkdir(parents=True)
    started = time.monotonic()
    live = type(client) is OllamaClient and team_factory is ProgrammingTeam
    report = {'schema': 1, 'status': 'running', 'scope': 'repository_inventory',
        'started_at': datetime.now(timezone.utc).isoformat(),
        'execution_mode': 'live_local_backend' if live else 'test_fixture',
        'autonomy_demonstrated': False, 'functional_checks_passed': False,
        'requested_model': model, 'models_used': [], 'model_calls': 0, 'checks': {},
        'workspace': str(workspace), 'report': str(workspace / 'autonomy_exam.json')}
    save_json(Path(report['report']), report)
    team = None
    try:
        models = client.models()
        report['available_models'] = list(models)
        selected = coding_model_candidates(models, model)
        if not selected:
            raise ValueError('No hay modelos de programacion accesibles en un backend local')
        if ':cloud' in selected[0].casefold():
            raise ValueError('Este examen requiere un modelo local, no un modelo cloud')
        report['selected_model'] = selected[0]
        original = workspace / 'input_repository'
        original.mkdir()
        for name, content in BROKEN_REPOSITORY.items():
            (original / name).write_text(content, encoding='utf-8')
        before = source_hashes(original)
        baseline = verify_candidate(original, 'repository_inventory', workspace / 'baseline')
        report['checks']['baseline_rejected'] = not baseline['ok']
        report['baseline_report'] = baseline['report']
        if baseline['ok']:
            raise ValueError('El examen no detecta los defectos iniciales; resultado invalido')
        rounds = []

        def external_check(project):
            checked = verify_candidate(project, 'repository_inventory',
                                       workspace / f'acceptance_{len(rounds) + 1:02}')
            rounds.append(checked)
            return {'ok': checked['ok'], 'report': checked['report'],
                'error': checked.get('error', ''),
                'output': checked.get('external', {}).get('process', {}).get('output', '')[-9000:]}

        team = team_factory(client, workspace / 'mission', preferred_model=selected[0],
            max_calls=max_calls, max_seconds=1800, on_progress=on_progress,
            acceptance_check=external_check)
        result = team.execute(CONTRACTS['repository_inventory'], source=original)
        report['mission'] = {'ok': result.ok, 'message': result.message, 'data': result.data}
        report['acceptance_rounds'] = [r['report'] for r in rounds]
        report['checks']['original_preserved_before_delivery'] = source_hashes(original) == before
        if not result.ok:
            raise ValueError(result.message)
        changed = result.data['work_delivery']['changed_files']
        report['checks']['both_modules_changed'] = all(p in changed for p in ('service.py', 'storage.py'))
        report['checks']['external_passed_before_delivery'] = bool(rounds and rounds[-1]['ok'])
        if not all(report['checks'].values()):
            raise ValueError('No se cumplieron todos los criterios del examen')
        # Publication affects only the benchmark's own input repository. It is
        # part of the explicit local exam, never the user's application folders.
        delivered = deliver_programming({'report': result.data['work_delivery']['report'],
            'workspace': str(workspace / 'delivery'), 'user_accepted': False})
        report['delivery'] = {'ok': delivered.ok, 'message': delivered.message, 'data': delivered.data}
        if not delivered.ok:
            raise ValueError(delivered.message)
        final = verify_candidate(original, 'repository_inventory', workspace / 'after_delivery')
        report['final_verification'] = final['report']
        report['checks']['external_passed_after_delivery'] = final['ok']
        report['checks']['unrelated_module_preserved'] = source_hashes(original).get('report.py') == before['report.py']
        report['checks']['original_tests_preserved'] = source_hashes(original).get('test_original.py') == before['test_original.py']
        report['checks']['backup_exists'] = bool(delivered.data.get('backup') and Path(delivered.data['backup']).is_dir())
        report['functional_checks_passed'] = all(report['checks'].values())
        report['autonomy_demonstrated'] = live and report['functional_checks_passed']
        report['status'] = ('passed' if live else 'passed_fixture') if report['functional_checks_passed'] else 'failed'
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        report.update(status='blocked', error=str(exc), autonomy_demonstrated=False)
    except KeyboardInterrupt:
        report.update(status='cancelled', error='Examen cancelado por el usuario', autonomy_demonstrated=False)
    finally:
        if team is not None:
            report['model_calls'] = len(team.calls)
            report['models_used'] = sorted({c['model'] for c in team.calls})
            report['backends_used'] = sorted({c.get('backend', '') for c in team.calls})
        report['duration_seconds'] = round(time.monotonic() - started, 3)
        save_json(Path(report['report']), report)
    return report
