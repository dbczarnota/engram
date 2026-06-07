"""Brain setup health check: honest metrics on how the memory system performs over recent sessions.
Filters out trivial sessions (< MIN_PROMPTS real user prompts). Backs the /brain-health skill;
the pure helpers below are unit-tested in tests/test_health_check.py."""
from __future__ import annotations

import collections
import glob
import json
import os
import re
import sys
import time

BASE = os.path.expanduser(r"~\.claude\projects")
FILES = glob.glob(os.path.join(BASE, "*", "*.jsonl"))
MIN_PROMPTS = 3
DEFAULT_DAYS = 30


def blocks(content):
    if isinstance(content, str):
        return [("text", content)]
    out = []
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict):
                out.append((b.get("type"), b))
    return out


def within_window(mtime: float, days: int) -> bool:
    """True if a file mtime (epoch seconds) is within the last `days`."""
    return (time.time() - mtime) <= days * 86400


def is_frontmatter_junk(snippet: str) -> bool:
    """A recall snippet that is raw YAML frontmatter rather than prose."""
    s = snippet.strip()
    return s.startswith("---") or s[:14].lstrip("- ").startswith("type:")


def classify_recall_used(entries: list, idx: int, paths: list[str]) -> bool:
    """After an auto-recall injection at entries[idx], did a LATER entry Read one of the surfaced
    notes or mention its stem in assistant text?"""
    if not paths:
        return False
    stems = [os.path.basename(p).rsplit(".", 1)[0] for p in paths]
    for o in entries[idx + 1:]:
        m = o.get("message")
        if not isinstance(m, dict):
            continue
        for bt, b in blocks(m.get("content")):
            if bt == "tool_use" and isinstance(b, dict) and b.get("name") == "Read":
                fp = str((b.get("input") or {}).get("file_path", ""))
                if any(s in fp for s in stems):
                    return True
            if bt == "text" and isinstance(b, str) and any(s in b for s in stems):
                return True
    return False


def graphify_hint_followed(entries: list) -> tuple[int, int]:
    """(# graphify-hint injections, # followed later by a `graphify query/path/explain` call).
    Measures whether sub-project C actually changed behavior."""
    hinted = followed = 0
    for i, o in enumerate(entries):
        if o.get("type") != "attachment":
            continue
        att = o.get("attachment") or {}
        if att.get("type") != "hook_additional_context":
            continue
        cont = att.get("content") or []
        text = "\n".join(cont) if isinstance(cont, list) else str(cont)
        if "Code graph available for this repo" not in text:
            continue
        hinted += 1
        for o2 in entries[i + 1:]:
            m = o2.get("message")
            if not isinstance(m, dict):
                continue
            done = False
            for bt, b in blocks(m.get("content")):
                if bt == "tool_use" and isinstance(b, dict) and b.get("name") in ("Bash", "PowerShell"):
                    cmd = str((b.get("input") or {}).get("command", ""))
                    if re.search(r"\bgraphify\s+(query|path|explain)\b", cmd):
                        followed += 1
                        done = True
                        break
            if done:
                break
    return hinted, followed


def load(f):
    out = []
    try:
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if line:
                out.append(json.loads(line))
    except Exception:
        pass
    return out


def count_prompts(entries):
    n = 0
    for o in entries:
        m = o.get("message")
        if not isinstance(m, dict) or m.get("role") != "user":
            continue
        bl = blocks(m.get("content"))
        if any(bt == "tool_result" for bt, _ in bl):
            continue
        txt = " ".join(b for bt, b in bl if bt == "text" and isinstance(b, str))
        if txt.strip():
            n += 1
    return n


def main(days: int = DEFAULT_DAYS):
    n_total = n_kept = 0
    n_prompts = 0
    sessions_with_recall = set()
    recall_events = 0
    used = ignored = 0
    total_snip = junk_snip = 0
    brain_reads = collections.Counter()
    sessions_with_brain_read = set()
    skill_uses = collections.Counter()
    surfaced = collections.Counter()
    # graphify
    gfx_skill = gfx_cli = gfx_reads = 0
    sessions_with_gfx = set()
    gfx_hint_shown = gfx_hint_followed_n = 0

    for f in FILES:
        try:
            if not within_window(os.path.getmtime(f), days):
                continue
        except OSError:
            continue
        entries = load(f)
        n_total += 1
        if count_prompts(entries) < MIN_PROMPTS:
            continue
        n_kept += 1

        h_shown, h_followed = graphify_hint_followed(entries)
        gfx_hint_shown += h_shown
        gfx_hint_followed_n += h_followed

        recall_here = []  # (idx, surfaced_paths)
        for i, o in enumerate(entries):
            if o.get("type") == "attachment":
                att = o.get("attachment") or {}
                if att.get("type") == "hook_additional_context":
                    cont = att.get("content") or []
                    text = "\n".join(cont) if isinstance(cont, list) else str(cont)
                    if "Engram auto-recall" in text:
                        sessions_with_recall.add(f)
                        recall_events += 1
                        paths = re.findall(r"(\S+\.md) ::", text)
                        for p in paths:
                            surfaced[p] += 1
                        for ln in text.splitlines():
                            mm = re.search(r"::.*?[—-] (.+)$", ln)
                            if mm:
                                body = mm.group(1).strip()
                                total_snip += 1
                                if is_frontmatter_junk(body):
                                    junk_snip += 1
                        recall_here.append((i, paths))
                continue

            m = o.get("message")
            if not isinstance(m, dict):
                continue
            role = m.get("role")
            bl = blocks(m.get("content"))

            if role == "user":
                if any(bt == "tool_result" for bt, _ in bl):
                    continue
                txt = " ".join(b for bt, b in bl if bt == "text" and isinstance(b, str))
                mcmd = re.search(r"<command-name>/?([a-z0-9:-]+)", txt)
                if mcmd:
                    name = mcmd.group(1)
                    skill_uses[name] += 1
                    if "graphify" in name:
                        gfx_skill += 1
                        sessions_with_gfx.add(f)
                if txt.strip():
                    n_prompts += 1

            elif role == "assistant":
                for bt, b in bl:
                    if bt != "tool_use" or not isinstance(b, dict):
                        continue
                    name = b.get("name")
                    inp = b.get("input") or {}
                    if name == "Read":
                        fp = str(inp.get("file_path", ""))
                        if re.search(r"[\\/]brain[\\/]", fp):
                            brain_reads[fp] += 1
                            sessions_with_brain_read.add(f)
                        if re.search(r"graphify-out|GRAPH_REPORT|graph\.(json|html)|OVERVIEW\.md", fp):
                            gfx_reads += 1
                            sessions_with_gfx.add(f)
                    elif name == "Skill":
                        sk = str(inp.get("skill", ""))
                        if sk:
                            skill_uses[sk] += 1
                            if "graphify" in sk:
                                gfx_skill += 1
                                sessions_with_gfx.add(f)
                    elif name in ("Bash", "PowerShell"):
                        cmd = str(inp.get("command", ""))
                        if re.search(r"\bgraphify\b", cmd):
                            gfx_cli += 1
                            sessions_with_gfx.add(f)
                        if re.search(r"graphify-out|GRAPH_REPORT", cmd):
                            gfx_reads += 1
                            sessions_with_gfx.add(f)

        for idx, paths in recall_here:
            if not paths:
                continue
            if classify_recall_used(entries, idx, paths):
                used += 1
            else:
                ignored += 1

    k = max(n_kept, 1)
    print("=" * 70)
    print(f"BRAIN HEALTH - last {days} days, sessions with >= {MIN_PROMPTS} prompts")
    print("=" * 70)
    print(f"sessions in window / kept        : {n_total} / {n_kept}  (dropped {n_total-n_kept} trivial)")
    print(f"real user prompts (kept)         : {n_prompts}")
    print()
    print("--- AUTO-RECALL ---")
    print(f"sessions with >=1 injection      : {len(sessions_with_recall)}  ({100*len(sessions_with_recall)//k}% of kept)")
    print(f"total injections                 : {recall_events}")
    jp = (100 * junk_snip // total_snip) if total_snip else 0
    print(f"snippets / frontmatter-junk      : {total_snip} / {junk_snip}  ({jp}% junk)")
    up = (100 * used // (used + ignored)) if (used + ignored) else 0
    print(f"used in-session / ignored        : {used} / {ignored}  ({up}% used)")
    print()
    print("--- GRAPHIFY ---")
    print(f"sessions that touched graphify   : {len(sessions_with_gfx)}  ({100*len(sessions_with_gfx)//k}% of kept)")
    print(f"  /graphify skill invocations    : {gfx_skill}")
    print(f"  graphify CLI calls (bash/pwsh) : {gfx_cli}")
    print(f"  reads of graphify-out/reports  : {gfx_reads}")
    hf = (100 * gfx_hint_followed_n // gfx_hint_shown) if gfx_hint_shown else 0
    print(f"  graphify-hint shown / followed : {gfx_hint_shown} / {gfx_hint_followed_n}  ({hf}% acted on)")
    print()
    print("--- MANUAL VAULT ACCESS ---")
    print(f"sessions that Read a brain/ file : {len(sessions_with_brain_read)}  ({100*len(sessions_with_brain_read)//k}%)")
    print(f"total brain/ Read calls          : {sum(brain_reads.values())}")
    print("top brain/ files Read:")
    for p, c in brain_reads.most_common(12):
        print(f"  {c:4d}  {re.sub(r'.*[\\/]brain[\\/]', '', p)}")
    print()
    print("--- SKILLS / COMMANDS ---")
    for kk, c in skill_uses.most_common(20):
        print(f"  {c:4d}  {kk}")
    print()
    print("--- NOTES SURFACED BY AUTO-RECALL ---")
    for p, c in surfaced.most_common(20):
        print(f"  {c:4d}  {p}")


if __name__ == "__main__":
    _days = DEFAULT_DAYS
    if len(sys.argv) > 1:
        try:
            _days = int(sys.argv[1])
        except ValueError:
            pass
    main(_days)
