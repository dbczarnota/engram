"""stream2llm YouTube transcribe helper — stdlib only, zero dependencies.

The single source of truth for talking to the deployed stream2llm API. The skill
(SKILL.md) shells out to this; nothing re-derives the API mechanics in prose.

Commands:
    submit <url> [--language pl]   POST a video, print {subscription_id, video_id, status}
    fetch  <url|subscription_id>   poll; if completed print {status, transcript, digest, ...}
    get    <url> [--language pl]    submit if new (cache miss), else fetch

Config (first found wins):
    env vars STREAM2LLM_API_KEY / STREAM2LLM_BASE_URL
    file ~/.claude/stream2llm.env  (KEY=VALUE lines)
Override file/cache locations in tests via STREAM2LLM_ENV_FILE / STREAM2LLM_CACHE_FILE.

The API key is read and used but NEVER printed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

DEFAULT_BASE_URL = "https://api.stream2llm.com"

_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "music.youtube.com",
}

# A transport: (method, url, headers, body_bytes|None) -> (status_int, body_bytes).
Transport = Callable[[str, str, dict, bytes | None], "tuple[int, bytes]"]


class TranscribeError(Exception):
    """User-facing error with a clear message (no stack needed)."""


# --------------------------------------------------------------------------- #
# URL / video id
# --------------------------------------------------------------------------- #

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def parse_video_id(url: str) -> str | None:
    """Extract the 11-char YouTube video id from common URL shapes, or None."""
    if _ID_RE.match(url):  # already a bare id
        return url
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if host not in _YOUTUBE_HOSTS:
        return None
    if host == "youtu.be":
        cand = p.path.lstrip("/").split("/", 1)[0]
        return cand if _ID_RE.match(cand) else None
    # youtube.com variants
    if p.path == "/watch":
        from urllib.parse import parse_qs

        v = parse_qs(p.query).get("v", [""])[0]
        return v if _ID_RE.match(v) else None
    parts = [seg for seg in p.path.split("/") if seg]
    if len(parts) >= 2 and parts[0] in {"shorts", "live", "embed", "v"}:
        cand = parts[1]
        return cand if _ID_RE.match(cand) else None
    return None


def is_youtube_url(url: str) -> bool:
    return (urlparse(url).hostname or "").lower() in _YOUTUBE_HOSTS


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #


@dataclass
class Config:
    api_key: str
    base_url: str


def _default_env_file() -> Path:
    return Path(os.environ.get("STREAM2LLM_ENV_FILE") or (Path.home() / ".claude" / "stream2llm.env"))


def parse_env_file(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def load_config() -> Config:
    """env vars override the env file; raise a clear error if no key is found."""
    file_vals: dict[str, str] = {}
    env_path = _default_env_file()
    if env_path.exists():
        file_vals = parse_env_file(env_path.read_text(encoding="utf-8"))
    api_key = os.environ.get("STREAM2LLM_API_KEY") or file_vals.get("STREAM2LLM_API_KEY", "")
    base_url = (
        os.environ.get("STREAM2LLM_BASE_URL")
        or file_vals.get("STREAM2LLM_BASE_URL")
        or DEFAULT_BASE_URL
    ).rstrip("/")
    if not api_key:
        raise TranscribeError(
            f"No STREAM2LLM_API_KEY found. Set it in {env_path} "
            f"(STREAM2LLM_API_KEY=str_...) or as an environment variable."
        )
    return Config(api_key=api_key, base_url=base_url)


# --------------------------------------------------------------------------- #
# Job cache (cache key -> {subscription_id, status})
# --------------------------------------------------------------------------- #
# Cache is keyed by "<video_id>:<mode>" (mode = quick | deep) so the two modes
# never collide: a deep ("full listen") request after a quick (subtitles) one is
# a cache miss and re-transcribes, rather than returning the subtitle result.


def _mode_key(video_id: str, deep: bool) -> str:
    return f"{video_id}:{'deep' if deep else 'quick'}"


def _default_cache_file() -> Path:
    return Path(
        os.environ.get("STREAM2LLM_CACHE_FILE")
        or (Path.home() / ".claude" / ".cache" / "stream2llm-jobs.json")
    )


def load_cache() -> dict[str, dict]:
    p = _default_cache_file()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(cache: dict[str, dict]) -> None:
    p = _default_cache_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cache, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #


def _urllib_transport(method: str, url: str, headers: dict, body: bytes | None) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except urllib.error.URLError as e:
        raise TranscribeError(f"Cannot reach stream2llm ({url}): {e.reason}") from e


def _api(
    cfg: Config,
    transport: Transport,
    method: str,
    path: str,
    body: dict | None = None,
) -> tuple[int, object]:
    # A browser-ish UA is required: the API sits behind Cloudflare, which blocks
    # the default "Python-urllib" signature with HTTP 403 (error 1010).
    headers = {
        "X-API-Key": cfg.api_key,
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; brain-youtube-transcribe/1.0)",
    }
    data: bytes | None = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    status, raw = transport(method, f"{cfg.base_url}{path}", headers, data)
    try:
        parsed: object = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        parsed = raw.decode("utf-8", "replace")
    return status, parsed


def _detail(parsed: object, fallback: str) -> str:
    if isinstance(parsed, dict) and "detail" in parsed:
        return str(parsed["detail"])
    return fallback


# --------------------------------------------------------------------------- #
# Operations
# --------------------------------------------------------------------------- #


def submit(url: str, language: str, cfg: Config, transport: Transport, *, deep: bool = False) -> dict:
    """Enqueue a video. Default (``deep=False``) is the quick path: prefer the
    video's existing YouTube subtitles (the API falls back to a full audio listen
    if none exist). ``deep=True`` forces the full Gemini audio transcription."""
    if not is_youtube_url(url):
        raise TranscribeError("URL must be a youtube.com / youtu.be link.")
    video_id = parse_video_id(url)
    body = {
        "url": url,
        "name": f"brain yt {video_id or url}",
        "language": language,
        "include_transcript": True,
        "prefer_youtube_subtitles": not deep,
    }
    status, parsed = _api(cfg, transport, "POST", "/v2/youtube/items", body)
    if status == 401:
        raise TranscribeError("stream2llm rejected the API key (401). Check STREAM2LLM_API_KEY.")
    if status == 400:
        raise TranscribeError(_detail(parsed, "Video not processable (live-only / upcoming / bad URL)."))
    if status not in (200, 201) or not isinstance(parsed, dict):
        raise TranscribeError(f"submit failed (HTTP {status}): {_detail(parsed, str(parsed))}")
    sub_id = str(parsed["id"])
    result = {
        "subscription_id": sub_id,
        "video_id": video_id,
        "status": parsed.get("status", "active"),
        "mode": "deep" if deep else "quick",
    }
    if video_id:
        cache = load_cache()
        cache[_mode_key(video_id, deep)] = {"subscription_id": sub_id, "status": result["status"]}
        save_cache(cache)
    return result


def _resolve_sub_id(ref: str, deep: bool = False) -> str:
    """A bare 11-char id is a video id (cache lookup); anything else is a subscription id."""
    vid = parse_video_id(ref) if (is_youtube_url(ref) or _ID_RE.match(ref)) else None
    if vid:
        entry = load_cache().get(_mode_key(vid, deep))
        if not entry:
            mode = "deep" if deep else "quick"
            raise TranscribeError(f"No submitted {mode} job for {vid}. Run `submit` first.")
        return entry["subscription_id"]
    return ref  # assume it's a subscription id (UUID)


def assemble_transcript(results: list[dict]) -> str:
    rows = sorted(results, key=lambda c: c.get("chunk_start", 0))
    return "\n".join((c.get("raw_transcript") or "").strip() for c in rows if c.get("raw_transcript"))


def _fetch_all_results(sub_id: str, cfg: Config, transport: Transport) -> list[dict]:
    out: list[dict] = []
    cursor: str | None = None
    while True:
        path = f"/v2/streams/subscriptions/{sub_id}/results?limit=200"
        if cursor:
            path += f"&since_chunk_id={cursor}"
        status, parsed = _api(cfg, transport, "GET", path)
        if status != 200 or not isinstance(parsed, list) or not parsed:
            break
        out.extend(parsed)
        if len(parsed) < 200:
            break
        cursor = parsed[-1]["chunk_id"]
    return out


def render_digest(digests: list[dict]) -> list[dict]:
    """Flatten stream2llm digests to a compact list of stories."""
    stories: list[dict] = []
    for d in digests:
        for s in (d.get("payload") or {}).get("stories", []):
            stories.append(
                {
                    "title": s.get("title") or s.get("label"),
                    "summary": s.get("summary"),
                    "is_news": s.get("is_news"),
                    "facts": [f.get("text") if isinstance(f, dict) else f for f in (s.get("facts") or [])],
                }
            )
    return stories


def fetch(ref: str, cfg: Config, transport: Transport, *, deep: bool = False) -> dict:
    sub_id = _resolve_sub_id(ref, deep)
    status, sub = _api(cfg, transport, "GET", f"/v2/streams/subscriptions/{sub_id}")
    if status == 404:
        raise TranscribeError(f"Subscription {sub_id} not found.")
    if status != 200 or not isinstance(sub, dict):
        raise TranscribeError(f"status check failed (HTTP {status}): {_detail(sub, str(sub))}")
    sub_status = sub.get("status", "unknown")

    results = _fetch_all_results(sub_id, cfg, transport)
    if sub_status not in ("completed", "failed"):
        return {"status": sub_status, "subscription_id": sub_id, "chunks_so_far": len(results)}
    if sub_status == "failed":
        raise TranscribeError(f"stream2llm marked subscription {sub_id} as failed.")

    _, digests = _api(cfg, transport, "GET", f"/v2/streams/subscriptions/{sub_id}/digests?limit=100")
    transcript = assemble_transcript(results)
    last_end = max((c.get("chunk_end", 0) for c in results), default=0)
    return {
        "status": "completed",
        "subscription_id": sub_id,
        "chunk_count": len(results),
        "duration_s": round(last_end),
        "transcript": transcript,
        "digest": render_digest(digests if isinstance(digests, list) else []),
    }


def get(url: str, language: str, cfg: Config, transport: Transport, *, deep: bool = False) -> dict:
    video_id = parse_video_id(url)
    if video_id and _mode_key(video_id, deep) in load_cache():
        return fetch(url, cfg, transport, deep=deep)
    return submit(url, language, cfg, transport, deep=deep)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None, transport: Transport = _urllib_transport) -> int:
    ap = argparse.ArgumentParser(prog="yt_transcribe")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("submit", "fetch", "get"):
        sp = sub.add_parser(name)
        sp.add_argument("ref", help="YouTube URL (or subscription id for fetch)")
        sp.add_argument("--language", default="pl")
        sp.add_argument(
            "--deep",
            action="store_true",
            help="full audio transcription (Gemini) instead of the quick YouTube-subtitles path",
        )
    args = ap.parse_args(argv)
    try:
        cfg = load_config()
        if args.cmd == "submit":
            out = submit(args.ref, args.language, cfg, transport, deep=args.deep)
        elif args.cmd == "fetch":
            out = fetch(args.ref, cfg, transport, deep=args.deep)
        else:
            out = get(args.ref, args.language, cfg, transport, deep=args.deep)
    except TranscribeError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
