from __future__ import annotations

from collections import Counter


class StopController:
    def __init__(self, max_iter: int, budget_tokens: int, stagnation_limit: int = 2) -> None:
        self.max_iter = max_iter
        self.budget_tokens = budget_tokens
        self.stagnation_limit = stagnation_limit
        self._seen: Counter[str] = Counter()

    def check(self, iteration: int, tokens_spent: int, fingerprints: set[str]) -> tuple[bool, str]:
        if tokens_spent >= self.budget_tokens:
            return (False, "budget")
        if not fingerprints:
            return (False, "clean")
        self._seen.update(fingerprints)
        if any(c >= self.stagnation_limit for c in self._seen.values()):
            return (False, "stagnation")
        if iteration >= self.max_iter:
            return (False, "max_iter")
        return (True, "")
