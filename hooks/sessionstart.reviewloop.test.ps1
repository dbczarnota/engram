#requires -Version 7
BeforeAll {
  $script:hook = Join-Path $PSScriptRoot 'sessionstart.ps1'
}

Describe 'sessionstart review-loop reminder' {
  It 'reminds when an unread loop-report exists' {
    $brain = Join-Path ([System.IO.Path]::GetTempPath()) ("brain-" + [guid]::NewGuid())
    $rdir = Join-Path $brain 'projects\hf\loop-reports'
    New-Item -ItemType Directory -Force -Path $rdir | Out-Null
    "---`ntype: loop-report`nread: false`nauto_fixed: 3`n---`n" |
      Set-Content -Path (Join-Path $rdir '2026-07-01-0300.md') -Encoding utf8

    $env:BRAIN_HOME = $brain
    $out = '{}' | & $script:hook | ConvertFrom-Json
    $out.hookSpecificOutput.additionalContext | Should -Match 'review-loop'
    $out.hookSpecificOutput.additionalContext | Should -Match 'unread'
  }

  It 'stays silent when all reports are read' {
    $brain = Join-Path ([System.IO.Path]::GetTempPath()) ("brain-" + [guid]::NewGuid())
    $rdir = Join-Path $brain 'projects\hf\loop-reports'
    New-Item -ItemType Directory -Force -Path $rdir | Out-Null
    "---`ntype: loop-report`nread: true`n---`n" |
      Set-Content -Path (Join-Path $rdir 'old.md') -Encoding utf8
    $env:BRAIN_HOME = $brain
    $res = '{}' | & $script:hook
    if ($res) { ($res | ConvertFrom-Json).hookSpecificOutput.additionalContext | Should -Not -Match 'review-loop' }
  }
}
