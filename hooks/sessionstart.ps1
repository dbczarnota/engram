#requires -Version 7
# SessionStart hook: if lesson drafts are pending in lessons/_inbox/, inject a short reminder.
$ErrorActionPreference = "Stop"
try {
  $raw = [Console]::In.ReadToEnd()
  $brain = if ($env:BRAIN_HOME) { $env:BRAIN_HOME } else { "<BRAIN_PATH>" }
  $inbox = "$brain\lessons\_inbox"
  if (-not (Test-Path $inbox)) { exit 0 }
  $drafts = @(Get-ChildItem $inbox -Filter *.md -ErrorAction SilentlyContinue)
  if ($drafts.Count -eq 0) { exit 0 }
  $names = ($drafts | ForEach-Object { $_.BaseName }) -join ", "
  $msg = "📥 You have $($drafts.Count) lesson draft(s) pending review in lessons/_inbox/: $names. Run /remember-lesson to promote or discard."
  $out = @{ hookSpecificOutput = @{ hookEventName = "SessionStart"; additionalContext = $msg } }
  $out | ConvertTo-Json -Depth 6 -Compress
  exit 0
} catch { exit 0 }
