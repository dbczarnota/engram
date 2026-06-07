# _meta/semantic/tests/test_scope.py
from autorecall import _note_in_scope

SCOPE = ["standards", "lessons"]


def test_scope_includes_std_lessons_and_project_wiki():
    assert _note_in_scope("standards/agents.md", SCOPE, True)
    assert _note_in_scope("lessons/kinde.md", SCOPE, True)
    assert _note_in_scope("projects/scrape2llm/scrape2llm.md", SCOPE, True)


def test_scope_excludes_journals_todos_inbox():
    assert not _note_in_scope("projects/scrape2llm/journal.md", SCOPE, True)
    assert not _note_in_scope("projects/scrape2llm/todos.md", SCOPE, True)
    assert not _note_in_scope("lessons/_inbox/2026-06-07-x.md", SCOPE, True)


def test_project_wiki_off_when_disabled():
    assert not _note_in_scope("projects/scrape2llm/scrape2llm.md", SCOPE, False)


def test_scope_includes_feature_notes():
    assert _note_in_scope("projects/x/features/fact-extraction.md", SCOPE, True)


def test_scope_excludes_feature_inbox():
    assert not _note_in_scope("projects/x/features/_inbox/2026-06-07-draft.md", SCOPE, True)


def test_feature_off_when_wiki_disabled():
    assert not _note_in_scope("projects/x/features/fact-extraction.md", SCOPE, False)
