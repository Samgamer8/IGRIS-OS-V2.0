from igris_os.evaluation import LocalTrainingRunner


def test_successful_training_is_recorded(tmp_path):
    session = LocalTrainingRunner(tmp_path / "memory").run()

    assert session.passed
    assert session.passed_count == session.total
    assert session.experience_id
    assert (tmp_path / "memory" / "experiences.jsonl").is_file()


def test_failed_training_is_not_promoted(tmp_path):
    class FailingBenchmark:
        def run(self):
            from igris_os.evaluation.local_benchmark import BenchmarkResult
            return (BenchmarkResult("forced_failure", False, "failure"),)

    session = LocalTrainingRunner(
        tmp_path / "memory", benchmark=FailingBenchmark()).run()

    assert not session.passed
    assert session.experience_id is None
    assert not (tmp_path / "memory" / "experiences.jsonl").exists()