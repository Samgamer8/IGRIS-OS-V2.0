from igris_os.evaluation import ProductionProgrammingReadinessBenchmark


def test_production_readiness_benchmark_repairs_projects_without_mocks(tmp_path):
    report = ProductionProgrammingReadinessBenchmark().write_report(
        tmp_path / "production_readiness.json")

    assert report["kind"] == "production_programming_readiness"
    assert report["passed"] is True
    assert report["score"] >= 75
    assert len(report["results"]) == 3
    assert any(item["name"] == "repair_multifile_project" for item in report["results"])
    assert (tmp_path / "production_readiness.json").is_file()
