from types import SimpleNamespace
from unittest.mock import Mock, patch

from igris_os.programming.languages import Language
from igris_os.programming.multilang import MultiLanguageCoordinator


def _coordinator():
    coordinator = MultiLanguageCoordinator.__new__(MultiLanguageCoordinator)
    coordinator._last_diagnostic = ""
    return coordinator


def test_typescript_tests_run_with_node_without_npx_or_package_downloads(tmp_path):
    run = Mock(return_value=SimpleNamespace(
        returncode=0, timed_out=False, stdout="# tests 1\n# pass 1", stderr=""))
    fake = SimpleNamespace(run=run)
    with patch("igris_os.security.sandbox.JobObjectSandbox", return_value=fake):
        assert _coordinator()._run_project_tests(tmp_path, Language.TYPESCRIPT)
    command = run.call_args.args[0]
    assert command == [
        "node", "--experimental-strip-types", "--test", "--test-reporter=tap",
        "src/main.test.ts",
    ]
    assert "npx" not in command


def test_gdscript_requires_a_test_runner_success_marker(tmp_path):
    failing_run = Mock(return_value=SimpleNamespace(
        returncode=0, timed_out=False, stdout="Godot started", stderr=""))
    failing = SimpleNamespace(run=failing_run)
    with patch("igris_os.security.sandbox.JobObjectSandbox", return_value=failing):
        assert not _coordinator()._run_project_tests(tmp_path, Language.GDSCRIPT)

    passing_run = Mock(return_value=SimpleNamespace(
        returncode=0, timed_out=False,
        stdout="IGRIS_TESTS_PASSED: 3", stderr=""))
    passing = SimpleNamespace(run=passing_run)
    with patch("igris_os.security.sandbox.JobObjectSandbox", return_value=passing):
        assert _coordinator()._run_project_tests(tmp_path, Language.GDSCRIPT)
    assert passing_run.call_args.args[0] == [
        "godot", "--headless", "--path", ".", "--script", "tests/test_runner.gd",
    ]
