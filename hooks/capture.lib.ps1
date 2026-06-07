# Shared helpers for capture.ps1 (dot-sourced; defines functions only, no side effects).

# Condense a raw transcript JSONL into a small text digest for the summarizer:
# keep user prompts + assistant text, drop tool_use/tool_result/image blobs, then cap to
# the LAST $MaxChars characters (most recent conversation). Piping the raw tail instead
# can be megabytes of tool-result JSON, which stalls `claude -p` past the hook timeout.
function Get-CondensedTranscript {
  param(
    [Parameter(Mandatory)] [string] $Path,
    [int] $MaxChars = 40000,
    [int] $MaxLineChars = 50000,
    [int] $TailBytes = 4MB
  )
  # Read only the last $TailBytes of the file via a raw stream, so cost is independent of total
  # transcript size. `Get-Content -Tail` is pathologically slow here: it materializes every line
  # (some multi-MB tool_result blobs) with PowerShell metadata before any filtering can run.
  $fs = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
  try {
    $start = [Math]::Max(0, $fs.Length - $TailBytes)
    $fs.Seek($start, [System.IO.SeekOrigin]::Begin) | Out-Null
    $sr = New-Object System.IO.StreamReader($fs, [System.Text.Encoding]::UTF8)
    $raw = $sr.ReadToEnd()
  } finally { $fs.Dispose() }
  $lines = $raw -split "`n"
  if ($start -gt 0 -and $lines.Count -gt 1) { $lines = $lines[1..($lines.Count - 1)] }  # drop partial first line

  $parts = New-Object System.Collections.Generic.List[string]
  foreach ($line in $lines) {
    if (-not $line.Trim()) { continue }
    # Skip giant lines before parsing: tool_result/large tool_use blobs carry no summary-worthy
    # text, and ConvertFrom-Json on multi-MB strings is pathologically slow in PowerShell.
    if ($line.Length -gt $MaxLineChars) { continue }
    try { $o = $line | ConvertFrom-Json } catch { continue }
    if ($o.type -ne "user" -and $o.type -ne "assistant") { continue }
    $msg = $o.message
    if (-not $msg) { continue }
    $role = "" + $msg.role
    $content = $msg.content
    $text = ""
    if ($content -is [string]) {
      $text = $content
    } else {
      foreach ($b in $content) {
        if ($b.type -eq "text" -and $b.text) { $text += "`n" + $b.text }
      }
    }
    $text = $text.Trim()
    if ($text) { $parts.Add("${role}: $text") }
  }
  $digest = ($parts -join "`n`n").Trim()
  if ($digest.Length -gt $MaxChars) { $digest = $digest.Substring($digest.Length - $MaxChars) }
  return $digest
}

# --- Session scratch: a cheap, crash-proof per-session black box (no LLM). ---
function _ScratchPath {
  param([string]$Brain, [string]$SessionId)
  $safe = ($SessionId -replace '[^A-Za-z0-9_-]', '_')
  return Join-Path $Brain "_meta\state\session-$safe.json"
}

function Get-SessionScratch {
  param([string]$Brain, [string]$SessionId)
  $p = _ScratchPath $Brain $SessionId
  if (Test-Path $p) {
    try { return Get-Content $p -Raw | ConvertFrom-Json } catch {}
  }
  return [pscustomobject]@{
    turns = 0; files = @(); prompts = @();
    committed = $false; journalEdited = $false; summarized = $false
  }
}

function _SaveScratch {
  param([string]$Brain, [string]$SessionId, $Scratch)
  $p = _ScratchPath $Brain $SessionId
  New-Item -ItemType Directory -Force (Split-Path $p) | Out-Null
  $Scratch | ConvertTo-Json -Depth 6 | Set-Content -Path $p -Encoding utf8
}

function Add-ScratchTurn {
  param([string]$Brain, [string]$SessionId, [string]$Prompt)
  $s = Get-SessionScratch -Brain $Brain -SessionId $SessionId
  $s.turns = [int]$s.turns + 1
  if ($Prompt) {
    $clip = if ($Prompt.Length -gt 200) { $Prompt.Substring(0, 200) } else { $Prompt }
    $s.prompts = @(@($s.prompts)) + $clip
  }
  _SaveScratch -Brain $Brain -SessionId $SessionId -Scratch $s
}

function Add-ScratchPrompt {
  param([string]$Brain, [string]$SessionId, [string]$Prompt)
  if (-not $Prompt) { return }
  $s = Get-SessionScratch -Brain $Brain -SessionId $SessionId
  $clip = if ($Prompt.Length -gt 200) { $Prompt.Substring(0, 200) } else { $Prompt }
  $s.prompts = @(@($s.prompts)) + $clip
  _SaveScratch -Brain $Brain -SessionId $SessionId -Scratch $s
}

function Add-ScratchFile {
  param([string]$Brain, [string]$SessionId, [string]$File)
  if (-not $File) { return }
  $s = Get-SessionScratch -Brain $Brain -SessionId $SessionId
  if (@($s.files) -notcontains $File) { $s.files = @(@($s.files)) + $File }
  if ((Split-Path $File -Leaf) -eq 'journal.md') { $s.journalEdited = $true }
  _SaveScratch -Brain $Brain -SessionId $SessionId -Scratch $s
}

function Set-ScratchFlag {
  param([string]$Brain, [string]$SessionId, [string]$Name, $Value)
  $s = Get-SessionScratch -Brain $Brain -SessionId $SessionId
  # Use Add-Member -Force so new properties (not in the default object) are created safely.
  $s | Add-Member -NotePropertyName $Name -NotePropertyValue $Value -Force
  _SaveScratch -Brain $Brain -SessionId $SessionId -Scratch $s
}

function Clear-SessionScratch {
  param([string]$Brain, [string]$SessionId)
  $p = _ScratchPath $Brain $SessionId
  if (Test-Path $p) { Remove-Item $p -Force -ErrorAction SilentlyContinue }
}

# --- Slug resolution (longest matching path prefix in project-map.json). ---
function Resolve-Slug {
  param([string]$Brain, [string]$Cwd)
  $mapPath = "$Brain\_meta\project-map.json"
  if (-not (Test-Path $mapPath)) { return $null }
  $map = Get-Content $mapPath -Raw | ConvertFrom-Json
  $cwd = ("" + $Cwd).TrimEnd('\')
  $slug = $null; $best = -1
  foreach ($p in $map.PSObject.Properties) {
    $key = $p.Name.TrimEnd('\')
    if ($cwd -eq $key -or $cwd.StartsWith("$key\")) {
      if ($key.Length -gt $best) { $best = $key.Length; $slug = $p.Value }
    }
  }
  return $slug
}

# --- Decide whether auto-capture should write a journal entry for this session. ---
# Gate: real work (edits OR commit OR >= MinTurns) AND not already summarized AND no manual checkpoint.
function Test-ShouldSummarize {
  param([string]$Brain, [string]$SessionId, [int]$MinTurns = 6)
  $s = Get-SessionScratch -Brain $Brain -SessionId $SessionId
  if ($s.summarized) { return $false }
  if ($s.journalEdited) { return $false }   # user ran /checkpoint this session
  $realWork = (@($s.files).Count -gt 0) -or $s.committed -or ([int]$s.turns -ge $MinTurns)
  return [bool]$realWork
}

# --- One model-agnostic capture: condense -> python -m summarize -> {journal,lesson,feature}.
# Writes the journal entry + stages lesson/feature drafts to _inbox. Best-effort. ---
function Invoke-Capture {
  param([string]$Brain, [string]$Slug, [string]$SessionId, [string]$TranscriptPath, [string]$Cwd, [switch]$Partial)
  if (-not $TranscriptPath -or -not (Test-Path $TranscriptPath)) { return $false }
  $journal = "$Brain\projects\$Slug\journal.md"
  if (-not (Test-Path $journal)) { return $false }
  $convo = Get-CondensedTranscript -Path $TranscriptPath
  if (-not $convo) { return $false }

  $lang = "English"
  try {
    $ecfg = Get-Content "$Brain\_meta\engram.json" -Raw | ConvertFrom-Json
    if ($ecfg.journal -and $ecfg.journal.language) { $lang = "" + $ecfg.journal.language }
  } catch {}
  $branch = ""
  try { $branch = (& git -C $Cwd rev-parse --abbrev-ref HEAD 2>$null) -join "" } catch {}
  $files = @((Get-SessionScratch -Brain $Brain -SessionId $SessionId).files)
  $match = "" + (Find-MatchingFeature -Brain $Brain -Slug $Slug -Files $files)

  # BRAIN_SEM_DIR lets tests point at the real semantic dir (with its venv) instead of copying it.
  $sem = if ($env:BRAIN_SEM_DIR) { $env:BRAIN_SEM_DIR } else { "$Brain\_meta\semantic" }
  $runArgs = @('run', '--directory', $sem)
  if (Test-Path "$sem\.env") { $runArgs += @('--env-file', "$sem\.env") }
  $runArgs += @('python', '-m', 'summarize', '--feature-match', $match, '--branch', $branch, '--lang', $lang)

  $env:BRAIN_CAPTURE_ACTIVE = "1"
  [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
  $raw = ($convo | & uv @runArgs 2>$null) -join "`n"
  $data = $null
  try { $data = $raw | ConvertFrom-Json } catch { return $false }
  if (-not $data) { return $false }

  $date = Get-Date -Format "yyyy-MM-dd"
  $wrote = $false

  $journalText = ("" + $data.journal).Trim()
  if ($journalText) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm"
    $branchTag = if ($branch -and $branch -ne "HEAD") { " - branch: $branch" } else { "" }
    $partialTag = if ($Partial) { " (partial)" } else { "" }
    $entry = "## $ts - session $SessionId$partialTag$branchTag`n$journalText`n`n"
    $existing = Get-Content $journal -Raw
    $firstEntry = [regex]::Match($existing, '(?m)^## ')
    if ($firstEntry.Success) {
      $merged = $existing.Substring(0, $firstEntry.Index) + $entry + $existing.Substring($firstEntry.Index)
    } else { $merged = $entry + $existing }
    Set-Content -Path $journal -Value $merged -Encoding utf8
    $wrote = $true
  }

  if ($data.lesson -and $data.lesson.tech) {
    $tech = ("" + $data.lesson.tech) -replace '[^A-Za-z0-9-]', '-'
    $li = "$Brain\lessons\_inbox"; New-Item -ItemType Directory -Force $li | Out-Null
    $fm = "---`ntype: lesson-draft`nstatus: draft`ntech: $tech`nsource_project: $Slug`nsource_session: $SessionId`ndate: $date`n---`n`n"
    Set-Content -Path "$li\$date-$tech.md" -Value ($fm + ("" + $data.lesson.body)) -Encoding utf8
  }

  if ($data.feature -and $data.feature.name) {
    $name = ("" + $data.feature.name) -replace '[^A-Za-z0-9-]', '-'
    $kind = "" + $data.feature.kind
    $fi = "$Brain\projects\$Slug\features\_inbox"; New-Item -ItemType Directory -Force $fi | Out-Null
    $updates = if ($kind -eq 'UPDATE') { "updates: $name`n" } else { "" }
    $fm = "---`ntype: feature-draft`nstatus: draft`nfeature: $name`n${updates}source_session: $SessionId`ndate: $date`n---`n`n"
    Set-Content -Path "$fi\$date-$name.md" -Value ($fm + ("" + $data.feature.body)) -Encoding utf8
  }

  return $wrote
}

# --- Feature matching: which existing feature note (if any) does this session's work belong to?
# Deterministic — intersects session-touched files with each feature note's `files:` list by suffix.
# Returns the feature's basename (slug) with the most overlap, or $null. ---
function Find-MatchingFeature {
  param([string]$Brain, [string]$Slug, [string[]]$Files)
  $dir = "$Brain\projects\$Slug\features"
  if (-not (Test-Path $dir)) { return $null }
  $sessionFiles = @(@($Files) | ForEach-Object { ($_ -replace '\\', '/').ToLower() })
  if ($sessionFiles.Count -eq 0) { return $null }
  $best = $null; $bestCount = 0
  # Sort by name so ties resolve deterministically (first alphabetically wins; $count -gt is strict).
  foreach ($f in (Get-ChildItem $dir -Filter *.md -ErrorAction SilentlyContinue | Sort-Object Name)) {
    $raw = Get-Content $f.FullName -Raw
    $line = [regex]::Match($raw, '(?m)^files:\s*(.+)$')
    if (-not $line.Success) { continue }
    $featFiles = [regex]::Matches($line.Groups[1].Value, '"([^"]+)"') |
      ForEach-Object { ($_.Groups[1].Value -replace '\\', '/').ToLower() }
    $count = 0
    foreach ($ff in $featFiles) {
      if (@($sessionFiles | Where-Object { $_.EndsWith($ff) }).Count -gt 0) { $count++ }
    }
    if ($count -gt $bestCount) { $bestCount = $count; $best = $f.BaseName }
  }
  return $best
}
