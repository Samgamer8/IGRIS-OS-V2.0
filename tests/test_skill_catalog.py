from igris_os.skills import (
    OrchestrationAdvisor,
    OrchestrationMode,
    SkillCatalog,
    SkillDefinition,
    SkillPhase,
    SkillSummary,
    build_engineering_catalog,
)


def test_progressive_disclosure_loads_only_selected_skill():
    loaded = []
    summary_a = SkillSummary(
        "build-a", "build", SkillPhase.BUILD, ("component",))
    summary_b = SkillSummary(
        "review-b", "review", SkillPhase.REVIEW, ("audit",))

    def loader(summary):
        def load():
            loaded.append(summary.name)
            return SkillDefinition(summary, ("step",), ("proof",))
        return load

    catalog = SkillCatalog(
        (summary_a, summary_b),
        {"build-a": loader(summary_a), "review-b": loader(summary_b)})

    selected = catalog.discover(
        "build this component", SkillPhase.BUILD)
    assert [item.name for item in selected] == ["build-a"]
    assert loaded == []

    catalog.load(selected[0].name)
    assert loaded == ["build-a"]
    assert catalog.loaded_names == ("build-a",)


def test_skill_gate_requires_steps_evidence_and_no_red_flags():
    skill = build_engineering_catalog().load("evidence-debug")
    result = SkillCatalog.verify(
        skill,
        skill.steps,
        {
            "reproduction": "failing command",
            "diagnostic": "line 5 parse error",
            "regression_test": "pytest passed",
        })
    assert result.passed

    rejected = SkillCatalog.verify(
        skill, skill.steps[:-1], {"reproduction": "yes"},
        ("unbounded retry detected",))
    assert not rejected.passed
    assert rejected.missing_steps
    assert rejected.missing_evidence
    assert rejected.red_flags == ("unbounded retry",)


def test_orchestration_advisor_uses_task_topology():
    assert OrchestrationAdvisor.choose(
        independent_tasks=3) == OrchestrationMode.PARALLEL_FAN_OUT
    assert OrchestrationAdvisor.choose(
        independent_tasks=3,
        shared_mutable_state=True) == OrchestrationMode.DIRECT
    assert OrchestrationAdvisor.choose(
        has_ordered_dependencies=True
    ) == OrchestrationMode.SEQUENTIAL_PIPELINE
    assert OrchestrationAdvisor.choose(
        research_input_size=50,
        expected_digest_size=5
    ) == OrchestrationMode.RESEARCH_ISOLATION


def test_catalog_rejects_incomplete_skill_contracts():
    summary = SkillSummary("empty", "invalid", SkillPhase.BUILD, ())
    try:
        SkillCatalog((summary,), {"empty": lambda: SkillDefinition(
            summary, ("step",), ("proof",))})
    except ValueError as error:
        assert "needs triggers" in str(error)
    else:
        raise AssertionError("incomplete skill was accepted")


def test_routing_eval_measures_realistic_prompts_without_loading_skills():
    catalog = build_engineering_catalog()
    result = catalog.evaluate_routing((
        ("implement this isolated component", "component-build"),
        ("repair this compile error", "evidence-debug"),
        ("audit and approve final quality", "final-quality-gate"),
        ("clarify ambiguous requirements", "clarify-contract"),
    ), minimum_accuracy=1.0)
    assert result.passed
    assert result.accuracy == 1.0
    assert result.failures == ()
    assert catalog.loaded_names == ()
