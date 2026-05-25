from __future__ import annotations

import pytest

from fakes import FakeEmbedder


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()
