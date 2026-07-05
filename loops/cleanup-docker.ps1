<#
.SYNOPSIS
  Safe cleanup of Docker leftovers from the loops' testcontainers (the strong-path pytest re-verify in
  fix-loop / integrate-loop spins up pgvector/postgres containers; a hard-killed run leaves them stopped,
  and anonymous DB volumes + build cache accumulate).

  Removes ONLY:
    - stopped containers older than -ContainerAgeHours,
    - ANONYMOUS (64-hex) dangling volumes  -- i.e. ephemeral testcontainers volumes,
    - build cache older than -CacheAgeDays.
  NEVER touches: running containers, images (expensive to re-pull), or NAMED volumes. Named volumes
  (files2llm_postgres_data, stream2llm_postgres_data, wp-env-*, ...) hold real local dev data that is
  simply not mounted right now -- a blanket `docker volume prune` WOULD destroy them, so we never do that.
  The age filter also leaves an in-flight run's fresh containers alone.

.PARAMETER ContainerAgeHours  Only remove stopped containers older than this. Default 6.
.PARAMETER CacheAgeDays       Only prune build cache older than this. Default 7.
.PARAMETER DryRun             List what would be removed; change nothing.

.EXAMPLE
  pwsh -File cleanup-docker.ps1 -DryRun         # see exactly what it would remove
  pwsh -File cleanup-docker.ps1                 # do the cleanup
#>
param(
  [int]$ContainerAgeHours = 6,
  [int]$CacheAgeDays = 7,
  [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
function Say($m) { Write-Host "[docker-cleanup] $m" }

# Daemon reachable? If not, do nothing (not an error - Docker may just be off).
try { docker ps -q *> $null } catch { Say 'Docker daemon not reachable - nothing to do.'; exit 0 }

# Anonymous (ephemeral) volumes only: a 64-char hex name. Named project volumes are NEVER matched.
$anonVols = docker volume ls -qf 'dangling=true' | Where-Object { $_ -match '^[0-9a-f]{64}$' }

Say 'BEFORE:'; docker system df

if ($DryRun) {
  Say 'DRY RUN - nothing will be removed.'
  Say "stopped containers older than ${ContainerAgeHours}h that WOULD be removed:"
  docker ps -a --filter 'status=exited' --filter 'status=created' `
    --format '  {{.ID}}  {{.Image}}  {{.Status}}'
  Say 'anonymous (ephemeral) volumes that WOULD be removed:'
  if ($anonVols) { $anonVols | ForEach-Object { "  $_" } } else { Say '  (none)' }
  Say 'named project volumes are PRESERVED (never removed).'
  exit 0
}

Say "pruning stopped containers older than ${ContainerAgeHours}h..."
docker container prune -f --filter "until=${ContainerAgeHours}h" | ForEach-Object { Say $_ }

if ($anonVols) {
  Say "removing $($anonVols.Count) anonymous (ephemeral) volume(s); named project volumes preserved..."
  # -f each by id: scoped removal, so no named project data can ever be caught.
  $anonVols | ForEach-Object { docker volume rm -f $_ *> $null }
} else {
  Say 'no anonymous volumes to remove.'
}

$cacheHours = $CacheAgeDays * 24
Say "pruning build cache older than ${CacheAgeDays}d..."
docker builder prune -f --filter "until=${cacheHours}h" | ForEach-Object { Say $_ }

Say 'AFTER:'; docker system df
Say 'done.'
