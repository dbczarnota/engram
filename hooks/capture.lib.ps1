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
