from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from igris_os.application.project_development import DevelopedProjectMission, StagedProject
from igris_os.application.project_flow import ProjectFlow, ProjectStage
from igris_os.application.project_mission import ProjectMission
from igris_os.application.project_planning import PlannedProjectMission
from igris_os.application.project_repair import ProjectRepairAdapter, ProjectRepairEvidence
from igris_os.application.project_testing import ProjectTestEvidence, ProjectTestingAdapter
from igris_os.application.python_testing import PythonPytestVerifierAdapter
from igris_os.application.python_lifecycle import build_python_project_lifecycle


class ProjectTestingAdapterTests(unittest.TestCase):
    def test_pytest_failure_retains_bounded_diagnostic_for_repair(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'test_main.py').touch()
            workflow = Mock()
            diagnostic = 'prefix\n' * 1500 + '\nE AssertionError: expected 3, got 2\n1 failed in 0.10s'
            workflow.run.return_value = SimpleNamespace(
                executed=True, run=SimpleNamespace(returncode=1, timed_out=False,
                                                   stdout=diagnostic, stderr=''))
            evidence = PythonPytestVerifierAdapter(workflow).verify(self.developed(root))
            self.assertTrue(evidence.executed)
            self.assertFalse(evidence.passed)
            self.assertIn('AssertionError: expected 3, got 2', evidence.summary)
            self.assertLess(len(evidence.summary), 4200)

    def test_final_review_does_not_open_another_repair_cycle(self):
        verifier = Mock()
        with TemporaryDirectory() as directory, \
                patch('igris_os.application.python_lifecycle.PythonRepairReviewAdapter') as review, \
                patch('igris_os.application.python_lifecycle.PythonRepairingVerifierAdapter') as repair, \
                patch('igris_os.application.python_lifecycle.ProjectLifecycle'):
            build_python_project_lifecycle(Mock(), Path(directory), 'local-model',
                                           developer=Mock(), verifier=verifier)
            review.assert_called_once_with(verifier)
            self.assertIs(repair.call_args.args[-1], verifier)

    def developed(self, root: Path) -> DevelopedProjectMission:
        flow = ProjectFlow()
        for stage in (ProjectStage.REQUEST, ProjectStage.PLAN, ProjectStage.DEVELOP):
            flow = flow.record(stage, stage.value, success=True)
        mission = ProjectMission(Mock(), flow)
        return DevelopedProjectMission(
            PlannedProjectMission(mission, Mock()), StagedProject(root, ("main.py",)))

    def test_executed_results_reach_repair_without_hiding_failures(self):
        for passed in (True, False):
            with self.subTest(passed=passed):
                evidence = ProjectTestEvidence(True, passed, ("python", "-m", "unittest"), "result")
                verifier = Mock()
                verifier.verify.return_value = evidence
                developed = self.developed(Path("."))
                tested = ProjectTestingAdapter(verifier).test(developed)
                self.assertIs(tested.evidence, evidence)
                self.assertIs(tested.mission.mission.mission.flow.next_stage, ProjectStage.REPAIR)
                summary = tested.mission.mission.mission.flow.evidence[-1].summary
                self.assertIn("aprobadas" if passed else "fallidas", summary)
                self.assertIs(developed.mission.mission.flow.next_stage, ProjectStage.TEST)

    def test_missing_execution_evidence_blocks_progress(self):
        for evidence in (
            ProjectTestEvidence(False, False, ("python",), "result"),
            ProjectTestEvidence(True, False, (), "result"),
            ProjectTestEvidence(True, False, (" ",), "result"),
            ProjectTestEvidence(True, False, ("python",), " "),
        ):
            with self.subTest(evidence=evidence):
                verifier = Mock()
                verifier.verify.return_value = evidence
                with self.assertRaises(ValueError):
                    ProjectTestingAdapter(verifier).test(self.developed(Path(".")))

    def test_failed_post_repair_tests_block_delivery(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.py").touch()
            verifier = Mock()
            verifier.verify.return_value = ProjectTestEvidence(True, False, ("python",), "failure")
            tested = ProjectTestingAdapter(verifier).test(self.developed(root))
            repairer = Mock()
            repairer.repair.return_value = ProjectRepairEvidence(
                root, True, True, False, ("main.py",), "still failing")
            with self.assertRaisesRegex(ValueError, "pruebas posteriores"):
                ProjectRepairAdapter(repairer).repair(tested)
            self.assertIs(tested.mission.mission.mission.flow.next_stage, ProjectStage.REPAIR)

    def test_successful_repair_after_failed_tests_reaches_delivery(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.py").touch()
            verifier = Mock()
            verifier.verify.return_value = ProjectTestEvidence(True, False, ("python",), "failure")
            tested = ProjectTestingAdapter(verifier).test(self.developed(root))
            repairer = Mock()
            repairer.repair.return_value = ProjectRepairEvidence(
                root, True, True, True, ("main.py",), "fixed and verified")
            repaired = ProjectRepairAdapter(repairer).repair(tested)
            self.assertIs(repaired.mission.mission.mission.mission.flow.next_stage, ProjectStage.DELIVER)


if __name__ == "__main__":
    unittest.main()