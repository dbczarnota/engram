#requires -Version 7
# Guards: every brain hook must no-op (exit 0, no output) when REVIEWLOOP_NESTED is set, so the
# review-loop's nested agent session is never hijacked by reminders/recall/capture.

Describe 'review-loop nested-session hook guards' {
  BeforeEach { $env:REVIEWLOOP_NESTED = '1' }
  AfterEach  { Remove-Item Env:REVIEWLOOP_NESTED -ErrorAction SilentlyContinue }

  It 'sessionstart.ps1 emits nothing when nested' {
    $out = '{}' | & (Join-Path $PSScriptRoot 'sessionstart.ps1')
    $out | Should -BeNullOrEmpty
  }
  It 'autorecall.ps1 emits nothing when nested' {
    $out = '{}' | & (Join-Path $PSScriptRoot 'autorecall.ps1')
    $out | Should -BeNullOrEmpty
  }
  It 'capture.ps1 emits nothing when nested' {
    $out = '{}' | & (Join-Path $PSScriptRoot 'capture.ps1')
    $out | Should -BeNullOrEmpty
  }
  It 'stop.ps1 emits nothing when nested' {
    $out = '{}' | & (Join-Path $PSScriptRoot 'stop.ps1')
    $out | Should -BeNullOrEmpty
  }
  It 'posttooluse-track.ps1 emits nothing when nested' {
    $out = '{}' | & (Join-Path $PSScriptRoot 'posttooluse-track.ps1')
    $out | Should -BeNullOrEmpty
  }
}
