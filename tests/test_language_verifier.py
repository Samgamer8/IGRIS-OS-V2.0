from unittest.mock import Mock

from igris_os.programming.languages import (
    Language, MultiLanguageVerifier, UniversalQualityGate,
)


def test_typescript_syntax_check_uses_node_without_package_manager(tmp_path):
    source = tmp_path / "src" / "main.ts"
    source.parent.mkdir()
    source.write_text("export const answer: number = 42;", encoding="utf-8")
    verifier = MultiLanguageVerifier(tmp_path)
    verifier._run = Mock(return_value=(True, "OK", 0, "", ""))

    result = verifier.verify(source)

    assert result.ok
    assert verifier._run.call_args.args[0] == (
        "node", "--experimental-strip-types", "--check", "src/main.ts",
    )


def test_quality_gate_does_not_claim_tests_when_no_typescript_tests_exist(tmp_path):
    source = tmp_path / "main.ts"
    source.write_text("export const answer: number = 42;", encoding="utf-8")
    gate = UniversalQualityGate(tmp_path)

    result = gate._run_tests(source, Language.TYPESCRIPT)

    assert not result.ok
    assert "No se encontraron pruebas" in result.message


def test_quality_gate_runs_local_node_test_files(tmp_path):
    source = tmp_path / "src" / "main.ts"
    source.parent.mkdir()
    source.write_text("export const answer: number = 42;", encoding="utf-8")
    test_file = source.parent / "main.test.ts"
    test_file.write_text("", encoding="utf-8")
    gate = UniversalQualityGate(tmp_path)
    gate.verifier._run = Mock(return_value=(True, "OK", 0, "# pass 1\n", ""))

    result = gate._run_tests(source, Language.TYPESCRIPT)

    assert result.ok
    command = gate.verifier._run.call_args.args[0]
    assert tuple(command[:4]) == (
        "node", "--experimental-strip-types", "--test", "--test-reporter=tap",
    )
    assert command[-1] == "src/main.test.ts"


def test_unavailable_security_analyzer_is_not_reported_as_passed(tmp_path):
    source = tmp_path / "main.ts"
    source.write_text("export const answer: number = 42;", encoding="utf-8")
    result = UniversalQualityGate(tmp_path)._security_scan(source, Language.TYPESCRIPT)

    assert not result.ok
    assert "no hay analizador" in result.message
