"""Anti-spam rules SPAM-01…SPAM-07 (docs/19 §5, docs/22)."""

from __future__ import annotations

from app.engines.metadata import spam_check


def _rule_ids(violations) -> set[str]:
    return {v.rule_id for v in violations}


def test_spam_01_keyword_stuffing():
    v = spam_check(
        title="Sunset beach sunset beach sunset",
        description="A calm beach at sunset.",
        keywords=["beach", "sunset", "ocean"],
    )
    assert "SPAM-01" in _rule_ids(v)


def test_spam_02_irrelevant_trending_terms():
    v = spam_check(
        title="Quiet mountain cabin",
        description="A wooden cabin in the mountains.",
        keywords=["cabin", "mountains", "bitcoin"],
    )
    assert "SPAM-02" in _rule_ids(v)


def test_spam_03_misleading_claims():
    v = spam_check(
        title="Bestselling viral photo",
        description="A photo of a lake.",
        keywords=["lake", "water"],
    )
    assert "SPAM-03" in _rule_ids(v)


def test_spam_04_bait_terms():
    v = spam_check(
        title="Forest path wallpaper",
        description="A path through the forest.",
        keywords=["forest", "path"],
    )
    assert "SPAM-04" in _rule_ids(v)


def test_spam_05_prohibited_names():
    v = spam_check(
        title="City skyline at dusk",
        description="Downtown skyline.",
        keywords=["skyline", "nike", "city"],
    )
    assert "SPAM-05" in _rule_ids(v)


def test_spam_06_title_keyword_echo():
    v = spam_check(
        title="red bicycle",
        description="A red bicycle leaning on a wall.",
        keywords=["red", "bicycle"],
    )
    assert "SPAM-06" in _rule_ids(v)


def test_spam_07_description_stuffing():
    v = spam_check(
        title="Office desk",
        description="office desk office chair office lamp office desk office",
        keywords=["office", "desk", "chair", "lamp"],
    )
    assert "SPAM-07" in _rule_ids(v)


def test_clean_metadata_passes_all():
    v = spam_check(
        title="Barista pouring latte art in a sunlit cafe",
        description=(
            "A barista finishes a rosetta pour in a bright neighborhood cafe. "
            "Warm morning light, shallow depth of field; suitable for hospitality "
            "and small-business advertising."
        ),
        keywords=["barista", "latte art", "cafe interior", "morning light", "hospitality"],
    )
    assert v == []
