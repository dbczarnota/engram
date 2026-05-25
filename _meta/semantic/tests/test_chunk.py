from chunking import Chunk, chunk_markdown, embed_input

SAMPLE = """---
type: standard
---
intro line before any heading

# Title

body of title

## Sub A

alpha text

### Deep

deep text

#### H4 stays in Deep

more deep
"""


def test_splits_by_h1_h3_and_builds_heading_path():
    chunks = chunk_markdown("standards/x.md", SAMPLE)
    paths = [c.heading_path for c in chunks]
    assert paths == ["", "Title", "Title › Sub A", "Title › Sub A › Deep"]


def test_h4_body_stays_in_enclosing_h3_chunk():
    chunks = chunk_markdown("standards/x.md", SAMPLE)
    deep = [c for c in chunks if c.heading_path.endswith("Deep")][0]
    assert "H4 stays in Deep" in deep.text
    assert "more deep" in deep.text


def test_frontmatter_kept_in_preheading_chunk():
    chunks = chunk_markdown("standards/x.md", SAMPLE)
    assert "type: standard" in chunks[0].text
    assert "intro line before any heading" in chunks[0].text


def test_content_hash_is_stable_and_path_independent():
    a = chunk_markdown("standards/x.md", SAMPLE)
    b = chunk_markdown("moved/elsewhere.md", SAMPLE)
    assert [c.content_hash for c in a] == [c.content_hash for c in b]


def test_embed_input_prefixes_heading_path():
    c = Chunk(path="p", heading_path="A › B", text="hello", content_hash="h")
    assert embed_input(c) == "A › B\n\nhello"
    c2 = Chunk(path="p", heading_path="", text="hello", content_hash="h")
    assert embed_input(c2) == "hello"


def test_empty_sections_are_skipped():
    chunks = chunk_markdown("p.md", "# Empty\n\n# Real\n\nx\n")
    assert [c.heading_path for c in chunks] == ["Real"]
