# _meta/semantic/tests/test_packaging.py
from autorecall import _first_sentence, _format_tiered


def test_first_sentence_prefers_rule_line():
    body = "Some intro.\n**Rule:** put blobs behind a Protocol. More text.\n"
    assert "put blobs behind a Protocol" in _first_sentence(body)


def test_tier1_pointer_and_tier2_fullchunk():
    rows = [
        ("standards/a.md", "Standard A", "**Rule:** do A always. Extra.", 0.9, 2),
        ("lessons/b.md", "Lesson B", "Some body about B that is long enough to matter.", 0.4, 1),
    ]
    out = _format_tiered(rows, token_budget=350)
    assert out is not None
    assert "Standard A" in out and "do A always" in out
    assert "lessons/b.md" in out
