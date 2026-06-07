from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class Summarizer(Protocol):
    name: str
    def generate(self, system: str, user: str) -> str: ...


def _vault_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _cfg(key: str, default: str = "") -> str:
    try:
        data = json.loads((_vault_root() / "_meta" / "engram.json").read_text(encoding="utf-8"))
        v = (data.get("capture") or {}).get(key)
        return str(v) if v else default
    except Exception:
        return default


def _strip_fences(text: str) -> str:
    t = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.DOTALL)
    return (m.group(1) if m else t).strip()


def parse_capture_json(text: str) -> dict:
    try:
        obj = json.loads(_strip_fences(text))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def build_capture_prompt(matched_feature: str, branch: str, lang: str) -> tuple[str, str]:
    system = (
        "You analyze a software coding-session transcript and reply with ONLY a single JSON object "
        "(no prose, no code fence)."
    )
    hint = re.sub(r"^feat/|^feature/", "", branch)
    feat = (
        f'The session continued the existing feature "{matched_feature}"; if how it is built materially '
        f'changed set feature.kind="UPDATE" and feature.name="{matched_feature}".'
        if matched_feature
        else 'If the session built a coherent, nameable feature, set feature.kind="FEATURE" and a kebab '
        f'feature.name (prefer "{hint}" if it fits).'
    )
    user = (
        "Return JSON with keys:\n"
        f'- "journal": 3-6 terse markdown bullets (each starting "- ") of decisions/changes/in-progress/'
        f"TODOs, written in {lang}. Empty string if nothing substantive.\n"
        '- "lesson": if there was a NON-OBVIOUS, costly-to-track-down technical gotcha, '
        '{"tech":"<kebab>","body":"- How to spot it: ...\\n- The trap: ...\\n- The fix: ..."}; else null.\n'
        f'- "feature": {feat} Shape {{"kind":"FEATURE|UPDATE","name":"<kebab>","body":"## What it does\\n..."}}; '
        "else null.\n\nTranscript follows:\n\n"
    )
    return system, user


class GeminiSummarizer:
    def __init__(self, model: str, api_key: str | None = None) -> None:
        from google import genai
        key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY to use the Gemini summarizer.")
        self._client = genai.Client(api_key=key)
        self.model = model
        self.name = f"gemini:{model}"

    def generate(self, system: str, user: str) -> str:
        from google.genai import types
        resp = self._client.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(system_instruction=system, temperature=0.2),
        )
        return resp.text or ""


class ClaudeCliSummarizer:
    def __init__(self, model: str | None = None) -> None:
        self.model = model
        self.name = f"claude-cli:{model or 'default'}"

    def generate(self, system: str, user: str) -> str:
        # Resolve the real executable: on Windows `claude` is a `claude.CMD` npm shim that bare
        # subprocess (no shell) cannot find — shutil.which honors PATHEXT and returns the full path.
        exe = shutil.which("claude")
        if not exe:
            return ""
        args = [exe, "-p", system]
        if self.model:
            args += ["--model", self.model]
        try:
            r = subprocess.run(args, input=user, capture_output=True, text=True, encoding="utf-8")
        except OSError:
            return ""
        return r.stdout or ""


class OllamaSummarizer:
    def __init__(self, model: str, host: str | None = None) -> None:
        self.model = model
        self.host = host or os.environ.get("BRAIN_OLLAMA_HOST", "http://localhost:11434")
        self.name = f"ollama:{model}"

    def generate(self, system: str, user: str) -> str:
        import urllib.request
        body = json.dumps(
            {"model": self.model, "system": system, "prompt": user, "stream": False, "format": "json"}
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{self.host}/api/generate", data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=180) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8")).get("response", "")


def build_summarizer() -> Summarizer:
    provider = os.environ.get("BRAIN_CAPTURE_PROVIDER") or _cfg("provider", "gemini")
    model = os.environ.get("BRAIN_CAPTURE_MODEL") or _cfg("model", "")
    if provider == "gemini":
        return GeminiSummarizer(model or "gemini-3-flash-preview")
    if provider == "ollama":
        return OllamaSummarizer(model or "qwen2.5")
    if provider == "claude-cli":
        return ClaudeCliSummarizer(model or None)
    raise ValueError(f"Unknown capture provider: {provider!r}")


def normalize_capture(data: object) -> dict:
    """Coerce model output into the shape PowerShell expects: `journal` always a string (models
    sometimes return the bullets as a JSON array)."""
    if not isinstance(data, dict):
        return {}
    j = data.get("journal")
    if isinstance(j, list):
        data["journal"] = "\n".join(str(x) for x in j)
    elif j is None:
        data["journal"] = ""
    elif not isinstance(j, str):
        data["journal"] = str(j)
    return data


def run_capture(summarizer: Summarizer, transcript: str, matched_feature: str, branch: str, lang: str) -> dict:
    system, user = build_capture_prompt(matched_feature, branch, lang)
    return normalize_capture(parse_capture_json(summarizer.generate(system, user + transcript)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--feature-match", default="")
    ap.add_argument("--branch", default="")
    ap.add_argument("--lang", default="English")
    args = ap.parse_args()
    transcript = sys.stdin.read()
    shim = os.environ.get("BRAIN_SUMMARIZE_SHIM")
    if shim is not None:
        result = normalize_capture(parse_capture_json(shim))
    else:
        try:
            result = run_capture(build_summarizer(), transcript, args.feature_match, args.branch, args.lang)
        except Exception:
            result = {}
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    main()
