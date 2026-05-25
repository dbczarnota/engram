# Test: Get-CondensedTranscript turns raw transcript JSONL into a small text digest:
# keeps user prompts + assistant text, drops tool_use/tool_result blobs, caps total size.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here "capture.lib.ps1")

$tmp = Join-Path ([IO.Path]::GetTempPath()) ("braincond_" + [Guid]::NewGuid().ToString("N") + ".jsonl")
try {
  $blob = "X" * 200000   # 200 KB tool-result payload that must NOT reach the summarizer
  $lines = @(
    (@{ type = "user";      message = @{ role = "user";      content = "please refactor the auth module" } } | ConvertTo-Json -Compress -Depth 6)
    (@{ type = "assistant"; message = @{ role = "assistant"; content = @(
        @{ type = "text";     text = "Sure, I will start by reading the file." }
        @{ type = "tool_use"; name = "Read"; input = @{ file_path = "auth.py" } }
    ) } } | ConvertTo-Json -Compress -Depth 6)
    (@{ type = "user";      message = @{ role = "user";      content = @(
        @{ type = "tool_result"; content = $blob }
    ) } } | ConvertTo-Json -Compress -Depth 6)
    (@{ type = "assistant"; message = @{ role = "assistant"; content = @(
        @{ type = "text";     text = "Done — extracted a helper and added a test." }
    ) } } | ConvertTo-Json -Compress -Depth 6)
    "{ this is not valid json and must be skipped"
  )
  Set-Content -Path $tmp -Value $lines -Encoding utf8

  $out = Get-CondensedTranscript -Path $tmp -MaxChars 40000

  if ($out -notmatch "refactor the auth module") { throw "FAIL: lost the user prompt. Got:`n$out" }
  if ($out -notmatch "extracted a helper")        { throw "FAIL: lost assistant text. Got:`n$out" }
  if ($out -match "XXXXXXXXXX")                    { throw "FAIL: tool_result blob leaked into digest" }
  if ($out.Length -gt 40000)                       { throw "FAIL: digest exceeds MaxChars ($($out.Length))" }
  if (-not $out.Trim())                            { throw "FAIL: empty digest" }

  "PASS: condensed digest keeps text, drops tool blobs, respects cap"
}
finally {
  if (Test-Path $tmp) { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
}
