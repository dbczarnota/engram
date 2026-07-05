<#
.SYNOPSIS
  Prune loop-generated branches that are already integrated. Deletes ONLY `fix/*` and `integrate/*`
  branches that are MERGED into master (i.e. you accepted them and merged) — using `git branch -d`, which
  itself refuses to delete an unmerged branch, so it is doubly safe.

  NEVER deletes:
    - `wip/*` branches — they back the needs-human dossiers (`git checkout wip/...` to see the attempt),
    - any UNMERGED branch — those are still awaiting your prod/canary/discard decision,
    - a branch currently checked out in a worktree (git refuses; we skip it).
  Also runs `git worktree prune` to drop stale worktree registrations.

.PARAMETER Repo    Target repository path (the one the loops ran against, e.g. myrepo).
.PARAMETER DryRun  List what would be deleted; change nothing.

.EXAMPLE
  pwsh -File cleanup-branches.ps1 -Repo C:\...\myrepo -DryRun
  pwsh -File cleanup-branches.ps1 -Repo C:\...\myrepo
#>
param(
  [Parameter(Mandatory)][string]$Repo,
  [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
function Say($m) { Write-Host "[branch-cleanup] $m" }

# Is it a git repo?
& git -C $Repo rev-parse --git-dir *> $null
if ($LASTEXITCODE -ne 0) { Say "Not a git repo: $Repo"; exit 1 }

# Branches merged into master, restricted to loop-generated fix/* and integrate/* (never wip/*, never master).
$merged = & git -C $Repo branch --merged master --format '%(refname:short)' |
  Where-Object { $_ -and $_ -ne 'master' -and ($_ -like 'fix/*' -or $_ -like 'integrate/*') }

$fixN  = ((& git -C $Repo branch --list 'fix/*')       | Measure-Object).Count
$wipN  = ((& git -C $Repo branch --list 'wip/*')       | Measure-Object).Count
$intN  = ((& git -C $Repo branch --list 'integrate/*') | Measure-Object).Count
Say "repo has: fix/*=$fixN  integrate/*=$intN  wip/*=$wipN (wip always kept)"

if (-not $merged) { Say 'no merged fix/* or integrate/* branches to prune.'; & git -C $Repo worktree prune; exit 0 }

if ($DryRun) {
  Say 'DRY RUN - would delete these MERGED branches:'
  $merged | ForEach-Object { "  $_" }
  Say "unmerged fix/* and all wip/* are kept."
  exit 0
}

foreach ($b in $merged) {
  & git -C $Repo branch -d $b *> $null      # -d refuses unmerged / checked-out -> safe
  if ($LASTEXITCODE -eq 0) { Say "deleted $b" } else { Say "skipped $b (checked out or not fully merged)" }
}
& git -C $Repo worktree prune
Say 'done.'
