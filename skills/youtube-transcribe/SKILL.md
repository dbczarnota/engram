---
name: youtube-transcribe
description: "Transcribe and summarize a YouTube video via the deployed stream2llm API. Use when the user pastes a youtube.com / youtu.be link and asks to summarize it, watch/listen to it, get its transcript, or relate it to a project (e.g. 'streść mi to', 'obejrzyj i powiedz jak to się ma do projektu X'). Returns the full verbatim transcript plus stream2llm's digest; you then do the user's actual ask."
---

# youtube-transcribe

Given a YouTube URL, get its **transcript + summary** back through the deployed **stream2llm** HTTP API
(under the dedicated "YouTube transcription brain" key), then do whatever the user actually asked —
summarize, extract points, or compare against a project.

Do **not** use yt-dlp or any local tool. Every call goes through stream2llm.

## Two modes: quick (default) vs deep

- **quick (default)** — reuse the video's **existing YouTube subtitles**. Fast and cheap (no audio
  transcription / Gemini tokens). If the video has no subtitles, stream2llm automatically falls back to a
  full audio listen, so quick never returns nothing. **This is the default — use it unless the user asks to go deeper.**
- **deep** (`--deep`) — skip subtitles and do the **full audio transcription** (Gemini listens to the
  whole video). Slower and costs tokens, but higher fidelity and includes speaker turns.

**When to use `--deep`:** when the user asks to go deeper / listen carefully / be thorough —
e.g. "wejdź w to głębiej", "przesłuchaj dokładnie", "dokładny odsłuch", "uważnie", "porządnie",
"nie z napisów". Otherwise stay on the default quick path.

The two modes are cached **separately** per video. Asking for `--deep` after a quick run is a cache miss
and starts a fresh full-audio job (you pay for the deep listen) — it does **not** return the subtitle result.
The JSON output includes a `"mode"` field (`quick` | `deep`) so you can tell the user which path ran.

## How it works

A stdlib helper script holds all the API mechanics. Run the `yt_transcribe.py` that sits next to this
SKILL.md (i.e. inside the installed skill directory, typically `~/.claude/skills/youtube-transcribe/`):

```
python ~/.claude/skills/youtube-transcribe/yt_transcribe.py <command> <url> [--language pl] [--deep]
```

Commands:
- `get <url>` — submit if the video is new (for this mode), else fetch the result. **Use this by default.**
- `submit <url>` — just enqueue (returns a subscription id).
- `fetch <url|subscription_id>` — retrieve when ready.

Flags (all commands):
- `--deep` — full audio transcription instead of the quick subtitles path (see "Two modes" above).
  Omit it for the default quick path.
- `--language pl|en` — language of the **summary** only (transcript stays in the spoken language).

The helper reads the API key from `~/.claude/stream2llm.env` (`STREAM2LLM_API_KEY`). It never prints the key.

## Procedure

1. **Run** `get "<url>"` — quick path by default. Add `--deep` only if the user asked to go deeper /
   listen carefully (see "Two modes"). Pass `--language en`/`--language pl` to set the **summary** language
   (the transcript is always verbatim in the spoken language regardless). Default `pl`.
2. **Read the JSON output:**
   - `"error"` present → surface it. If it says no API key, tell the user to put
     `STREAM2LLM_API_KEY=str_...` in `~/.claude/stream2llm.env` (see `stream2llm.env.example`).
   - `"mode"` tells you which path ran (`quick` = subtitles, `deep` = full audio listen).
   - `"status"` is `active`/`processing` (just submitted) → transcription is running. Quick (subtitles)
     is usually fast; deep (full audio + Gemini) is usually a few minutes. Tell the user it's processing
     and that you'll fetch it when they're ready (or when they say "sprawdź"/"gotowe?"). **Do not block-poll for minutes.**
   - `"status": "completed"` → you now have `transcript` (full verbatim text) and `digest`
     (stream2llm's stories/summaries). Proceed to step 3.
3. **Do the user's actual request** using the transcript: summarize, pull key points, or analyze how it
   relates to the named project (grep the brain vault / project for context as usual). The `digest` is a
   helpful starting summary but **you** write the answer the user asked for.

## Fetching later

When the user comes back ("gotowe?", "pokaż", "sprawdź"), run `fetch "<url>"` (the same URL — the helper
remembers the job in its cache). **Pass the same mode you submitted with** (add `--deep` if the original
run was deep), since the cache is per mode. If still `active`, report progress (`chunks_so_far`) and
suggest trying again shortly.

## Notes

- Re-submitting the same URL+mode is cheap: the helper caches `video_id:mode → subscription_id`, so it
  won't re-transcribe (and re-pay) a video it already submitted in that mode. Switching mode (quick→deep)
  intentionally starts a fresh job.
- Long videos → more chunks → longer wait; the helper paginates results automatically.
- Only youtube.com / youtu.be links are accepted (the API rejects other hosts).
</content>
</invoke>
