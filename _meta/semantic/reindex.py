from __future__ import annotations

import time
from pathlib import Path

from embedder import Embedder, build_embedder
from index import build_index, index_dir


def run(vault_root: Path, embedder: Embedder | None = None) -> str:
    embedder = embedder or build_embedder()
    start = time.perf_counter()
    stats = build_index(vault_root, embedder)
    # Prune per-session auto-recall dedupe state — stale after a rebuild.
    for f in index_dir(vault_root).glob("seen-*.json"):
        f.unlink(missing_ok=True)
    elapsed = time.perf_counter() - start
    return (
        f"reindex done: files={stats.files} chunks={stats.chunks} "
        f"embedded={stats.embedded} cached={stats.cached} "
        f"embedder={embedder.name} elapsed={elapsed:.1f}s"
    )


def main() -> None:
    # _meta/semantic/reindex.py -> parents[2] is the vault root.
    vault_root = Path(__file__).resolve().parents[2]
    print(run(vault_root))


if __name__ == "__main__":
    main()
