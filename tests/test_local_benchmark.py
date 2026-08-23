from igris_os.evaluation import LocalProgrammingBenchmark, run_local_benchmark


def test_local_benchmark_passes_without_network():
    result = run_local_benchmark()
    assert result["passed"] is True
    assert result["passed_count"] == result["total"]


def test_local_benchmark_covers_programming_safety_cases():
    results = {item.name: item for item in LocalProgrammingBenchmark().run()}
    assert results["python_valido"].passed
    assert results["syntax_invalida"].passed
    assert results["eval_peligroso"].passed
    assert results["sandbox_execution"].passed
    assert results["sandbox_timeout"].passed
    assert results["forbidden_executable"].passed


def test_local_benchmark_covers_conversation_cases():
    results = {item.name: item for item in LocalProgrammingBenchmark().run()}
    assert results["conversation_saludo"].passed
    assert results["conversation_estado"].passed
    assert results["conversation_critica"].passed
    assert results["conversation_limite"].passed


def test_local_benchmark_records_promotable_training_session(tmp_path):
    report = LocalProgrammingBenchmark().run_and_record(tmp_path / "training.json")
    assert report["passed"] is True
    assert (tmp_path / "training.json").is_file()