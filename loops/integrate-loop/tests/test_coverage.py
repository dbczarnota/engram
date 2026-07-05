from __future__ import annotations

import coverage


COBERTURA = """<?xml version="1.0"?>
<coverage>
 <packages><package><classes>
  <class filename="backend/a.py"><lines>
    <line number="5" hits="3"/><line number="6" hits="0"/><line number="7" hits="1"/>
  </lines></class>
 </classes></package></packages>
</coverage>"""


DIFF = """diff --git a/backend/a.py b/backend/a.py
--- a/backend/a.py
+++ b/backend/a.py
@@ -4,2 +4,4 @@ def f():
 x = 1
+y = 2
+z = 3
@@ -20,0 +22,1 @@
+# a comment line
diff --git a/tests/test_a.py b/tests/test_a.py
--- a/tests/test_a.py
+++ b/tests/test_a.py
@@ -1,0 +1,1 @@
+assert True
"""


def test_parse_cobertura_lines_and_hits():
    cov = coverage.parse_cobertura(COBERTURA)
    assert cov == {"backend/a.py": {5: 3, 6: 0, 7: 1}}


def test_added_prod_lines_ignores_tests():
    added = coverage.added_prod_lines(DIFF)
    # new lines 5,6 (the @@+4,4 hunk) and 22 (the comment-only hunk, still a prod-file added line —
    # non-executable filtering happens later in fully_covered via absence from coverage); test file ignored
    assert added == {"backend/a.py": {5, 6, 22}}


def test_fully_covered_true_when_all_executable_added_lines_hit():
    # added line 5 is executable+covered (hits 3); line 6 executable+UNcovered (hits 0)
    assert coverage.fully_covered({"backend/a.py": {5}}, {"backend/a.py": {5: 3, 6: 0}}) is True
    assert coverage.fully_covered({"backend/a.py": {5, 6}}, {"backend/a.py": {5: 3, 6: 0}}) is False


def test_fully_covered_ignores_non_executable_added_lines():
    # added line 99 is not in coverage -> non-executable (comment/blank) -> ignored -> covered
    assert coverage.fully_covered({"backend/a.py": {99}}, {"backend/a.py": {5: 3}}) is True


def test_fully_covered_empty_added_is_true():
    assert coverage.fully_covered({}, {}) is True


def test_fully_covered_fails_safe_when_file_absent_from_coverage():
    # the CRITICAL: a changed file not measured at all (path mismatch / new file) -> NOT covered -> demote
    assert coverage.fully_covered({"backend/new.py": {5}}, {"backend/a.py": {5: 3}}) is False


def test_fully_covered_matches_suffix_paths():
    # cobertura reports 'a.py' (source=backend) while the diff path is 'backend/a.py' -> must still match
    assert coverage.fully_covered({"backend/a.py": {5}}, {"a.py": {5: 3}}) is True
    assert coverage.fully_covered({"backend/a.py": {6}}, {"a.py": {6: 0}}) is False   # matched + uncovered
