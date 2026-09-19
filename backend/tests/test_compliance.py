"""Compliance engine: text-only interpretation, fail-closed behavior, and
explanations for every flag (docs/18, CONTRACT.md §4.2)."""

from __future__ import annotations

from app.engines.compliance import (
    RuleFinding,
    ScreenSubject,
    run_screen,
)


def _manual_rules(*keys: str):
    from app.engines.compliance import RuleSeverity, RuleSpec

    return [
        RuleSpec(
            rule_key=k,
            severity=RuleSeverity.WARN,
            check_method="model_assisted",
            applies_to=("PROMPT_SCREEN",),
        )
        for k in keys
    ]


def _subject() -> ScreenSubject:
    return ScreenSubject(
        title="Solar panels on a rooftop",
        description="A clean rooftop solar installation.",
        keywords=["solar", "rooftop", "energy"],
    )


def test_visual_only_rules_never_auto_pass():
    # tq-02 (noise) and tq-03 (blur) cannot be evaluated from text → REVIEW.
    result = run_screen("PROMPT_SCREEN", _subject(), _manual_rules("tq-02", "tq-03"))
    assert result.result == "REVIEW"
    for f in result.findings:
        assert f.triggered is False
        assert f.explanation  # every flag explained


def test_fail_closed_check_errors_become_review():
    # Unknown automated rule key → not in AUTOMATED_CHECKS → falls to the
    # non-automated branch → REVIEW, never PASS.
    result = run_screen("PROMPT_SCREEN", _subject(), _manual_rules("not-a-real-rule"))
    assert result.result == "REVIEW"


def test_high_risk_finding_drives_overall():
    from app.engines.compliance import RuleSeverity, RuleSpec

    # ip-01: prohibited brand mention is a blocker → HIGH_RISK overall.
    subject = ScreenSubject(
        title="Company logo on a product box",
        description="Shoes.",
        keywords=["logo", "shoes"],
    )
    rules = [
        RuleSpec(
            rule_key="ip-01",
            severity=RuleSeverity.BLOCK,
            check_method="automated",
            applies_to=("PROMPT_SCREEN",),
        )
    ]
    result = run_screen("PROMPT_SCREEN", subject, rules)
    assert result.result == "HIGH_RISK"
    triggered = [f for f in result.findings if f.triggered]
    assert triggered
    for f in result.findings:
        assert f.explanation


def test_every_finding_has_explanation():
    result = run_screen("PROMPT_SCREEN", _subject(), _manual_rules("tq-02"))
    assert result.explanation  # overall explanation
    for f in result.findings:
        assert isinstance(f, RuleFinding)
        assert f.explanation
        assert f.rule_key
