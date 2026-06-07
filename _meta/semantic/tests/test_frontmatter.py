# _meta/semantic/tests/test_frontmatter.py
from chunking import chunk_markdown


def test_frontmatter_not_chunked():
    content = (
        "---\n"
        "type: standard\n"
        "tags: [standard, storage]\n"
        "---\n\n"
        "# Standard: storage\n\n"
        "**Rule:** put blobs behind a Protocol.\n"
    )
    chunks = chunk_markdown("standards/x.md", content)
    bodies = " ".join(c.text for c in chunks)
    headings = " ".join(c.heading_path for c in chunks)
    assert "type: standard" not in bodies
    assert "tags:" not in bodies
    assert "Rule:" in bodies
    assert "Standard: storage" in headings
    assert all(not (c.heading_path == "" and "---" in c.text) for c in chunks)
