from igris_os.evaluation import TemporalProgrammingBenchmark


def test_temporal_benchmark_validates_all_project_stages(tmp_path):
    benchmark = TemporalProgrammingBenchmark()
    report = benchmark.write_report(tmp_path / "temporal.json")

    assert report["passed"] is True
    assert report["snapshots"] == 4
    assert report["score_start"] == 33
    assert report["score_end"] == 100
    assert report["improvement_points"] == 67
    assert (tmp_path / "temporal.json").is_file()


def test_temporal_benchmark_records_expected_evidence():
    results = TemporalProgrammingBenchmark().run()
    by_name = {result.name: result for result in results}

    assert by_name["v1_sintaxis_rota"].syntax_error
    assert by_name["v2_insegura"].security_risk
    assert by_name["v3_funcional"].tests_pass
    assert by_name["v4_verificada"].tests_pass
    assert all(result.passed for result in results)