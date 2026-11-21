# Export ~/.claude into the claude-config repo, then commit and push.
# Runs unattended from a Claude Code SessionEnd hook: never prompts, always exits 0,
# and records the outcome in ~/.claude-config/last-sync.json for the SessionStart notice.
$ErrorActionPreference = 'Continue'

# Never wait for credentials in a detached hook: fail fast instead of hanging.
$env:GIT_TERMINAL_PROMPT = '0'
$env:GCM_INTERACTIVE = 'never'

$RepoDir = Split-Path -Parent $PSScriptRoot
$StateDir = Join-Path $env:USERPROFILE '.claude-config'
$LogFile = Join-Path $StateDir 'sync.log'
$RunLock = Join-Path $StateDir 'sync-run.lock'
$RunLockStaleMinutes = 15
$SyncBranch = 'main'
$ExitBusy = 3
$MaxStatusChars = 1500
# Paths written by `ccsync export`: the only paths this script stages, commits or reverts.
$ExportedPaths = @('skills', 'agents', 'commands', 'CLAUDE.base.md', 'CLAUDE.windows.md', 'CLAUDE.linux.md', 'plugins.json', 'mcp.json')

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

function Write-Log([string]$Message) {
    $stamp = (Get-Date).ToString('s')
    Add-Content -Path $LogFile -Value "[$stamp] $Message" -Encoding utf8
}

function Invoke-Native([string]$Exe, [string[]]$Arguments) {
    # PS 5.1 wraps native stderr in ErrorRecords; "$_" keeps just the text.
    # Blank stderr lines stringify to the exception type name; drop them.
    $lines = & $Exe @Arguments 2>&1 | ForEach-Object { "$_" } |
        Where-Object { $_ -and $_ -ne 'System.Management.Automation.RemoteException' }
    return [pscustomobject]@{ Code = $LASTEXITCODE; Output = ($lines -join "`n").Trim() }
}

function Format-StatusMessage([string]$Message) {
    # PS 5.1 drops empty native args and does not escape embedded quotes; keep the arg safe.
    $clean = ($Message -replace '"', "'" -replace "`r?`n", ' | ').Trim()
    if (-not $clean) { $clean = 'unknown error' }
    if ($clean.Length -gt $MaxStatusChars) { $clean = $clean.Substring(0, $MaxStatusChars) + '...' }
    return $clean
}

function Set-Status([bool]$Ok, [string]$Message) {
    if ($Ok) { $null = Invoke-Native 'py' @('-3', '-m', 'ccsync', 'status', '--set-ok') }
    else { $null = Invoke-Native 'py' @('-3', '-m', 'ccsync', 'status', '--set-fail', (Format-StatusMessage $Message)) }
}

function Open-RunLock {
    if ((Test-Path $RunLock) -and ((Get-Item $RunLock).LastWriteTime -lt (Get-Date).AddMinutes(-$RunLockStaleMinutes))) {
        Remove-Item $RunLock -Force -ErrorAction SilentlyContinue
    }
    try {
        return [System.IO.File]::Open($RunLock, 'CreateNew', 'Write', 'None')
    } catch [System.IO.IOException] {
        return $null
    }
}

function Get-StageablePaths {
    # `git add -- <path>` fails on a path that neither exists nor is tracked.
    foreach ($path in $ExportedPaths) {
        $tracked = (Invoke-Native 'git' @('ls-files', '--', $path)).Output
        if ((Test-Path (Join-Path $RepoDir $path)) -or $tracked) { $path }
    }
}

function Undo-PartialExport {
    # A blocked export must never leave a secret lingering in the working tree.
    foreach ($path in $ExportedPaths) {
        if ((Invoke-Native 'git' @('ls-files', '--', $path)).Output) {
            $null = Invoke-Native 'git' @('checkout', '-q', 'HEAD', '--', $path)
        }
    }
    $null = Invoke-Native 'git' (@('clean', '-fdq', '--') + $ExportedPaths)
}

# Returns $null on success, 'busy' if another sync holds the export lock, else an error message.
function Invoke-Sync {
    $branch = Invoke-Native 'git' @('rev-parse', '--abbrev-ref', 'HEAD')
    if ($branch.Output -ne $SyncBranch) { return "repo is on '$($branch.Output)', not '$SyncBranch'; sync skipped" }

    # Anything dirty outside the exported paths (hand edits, notes, build output) is never auto-committed.
    $excludes = $ExportedPaths | ForEach-Object { ":(exclude)$_" }
    $dirty = Invoke-Native 'git' (@('status', '--porcelain', '--untracked-files=all', '--', '.') + $excludes)
    if ($dirty.Output) { return "uncommitted changes outside exported paths, sync skipped: $($dirty.Output)" }

    $export = Invoke-Native 'py' @('-3', '-m', 'ccsync', 'export')
    if ($export.Code -eq $ExitBusy) { return 'busy' }
    if ($export.Code -ne 0) {
        Undo-PartialExport
        return $export.Output
    }

    $stage = @(Get-StageablePaths)
    if ($stage.Count -gt 0) {
        $add = Invoke-Native 'git' (@('add', '-A', '--') + $stage)
        if ($add.Code -ne 0) { return "git add failed: $($add.Output)" }
    }
    $diff = Invoke-Native 'git' @('diff', '--cached', '--quiet')
    if ($diff.Code -ne 0) {
        $commit = Invoke-Native 'git' @('commit', '-q', '-m', 'chore: sync claude config')
        if ($commit.Code -ne 0) { return "git commit failed: $($commit.Output)" }
        Write-Log 'committed changes'
    }

    # Always push: retries commits left behind by an earlier failed push.
    $push = Invoke-Native 'git' @('push', '-q', 'origin', "HEAD:$SyncBranch")
    if ($push.Code -ne 0) { return "git push failed: $($push.Output)" }
    return $null
}

$lock = Open-RunLock
if (-not $lock) {
    Write-Log 'another sync is running; skipped'
    exit 0
}

Push-Location $RepoDir
try {
    $result = Invoke-Sync
    if ($result -eq 'busy') {
        Write-Log 'export lock held by another sync; skipped'
    } elseif ($result) {
        Write-Log "FAIL: $result"
        Set-Status $false $result
    } else {
        Write-Log 'ok'
        Set-Status $true 'ok'
    }
} finally {
    Pop-Location
    $lock.Dispose()
    Remove-Item $RunLock -Force -ErrorAction SilentlyContinue
}
exit 0
