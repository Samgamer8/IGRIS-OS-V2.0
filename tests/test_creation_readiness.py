import json

from igris_os.evaluation import FullApplicationCreationBenchmark


class DeterministicCreationClient:
    def generate_json(self, prompt, model, schema):
        return type("Reply", (), {
            "ok": True,
            "text": json.dumps({
                "name": "task_manager",
                "readme": "# Task manager\n\nRun with pytest.",
                "files": {
                    "model.py": (
                        "from dataclasses import dataclass\n\n"
                        "@dataclass\nclass Task:\n    title: str\n    completed: bool = False\n"
                    ),
                    "service.py": (
                        "from model import Task\n\n"
                        "class TaskService:\n"
                        "    def __init__(self): self.tasks = []\n"
                        "    def add(self, title): self.tasks.append(Task(title))\n"
                        "    def complete(self, title):\n"
                        "        next(task for task in self.tasks if task.title == title).completed = True\n"
                        "    def list(self): return self.tasks\n"
                    ),
                    "main.py": (
                        "from service import TaskService\n\n"
                        "def main():\n    return TaskService()\n"
                    ),
                    "test_service.py": (
                        "from service import TaskService\n\n"
                        "def test_task_lifecycle():\n"
                        "    service = TaskService()\n"
                        "    service.add('ship')\n"
                        "    service.complete('ship')\n"
                        "    assert service.list()[0].completed\n"
                    ),
                },
            }),
        })()


def test_full_application_creation_benchmark_verifies_real_artifacts(tmp_path):
    benchmark = FullApplicationCreationBenchmark(DeterministicCreationClient())

    report = benchmark.write_report(tmp_path / "creation_readiness.json")

    assert report["kind"] == "full_application_creation_readiness"
    assert report["passed"] is True
    assert report["score"] == 100
    assert (tmp_path / "creation_readiness.json").is_file()