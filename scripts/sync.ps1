# Export ~/.claude into the claude-config repo, then commit and push.
# Runs unattended from a Claude Code SessionEnd hook: never prompts, always exits 0,
# and records the outcome in ~/.claude-config/last-sync.json for the SessionStart notice.
$ErrorActionPreference = 'Continue'

$RepoDir = Split-Path -Parent $PSScriptRoot
$StateDir = Join-Path $env:USERPROFILE '.claude-config'
$LogFile = Join-Path $StateDir 'sync.log'
$SyncBranch = 'main'
$ExitBusy = 3
# Paths written by `ccsync export`; only these are reverted after a failed export.
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

function Set-Status([bool]$Ok, [string]$Message) {
    Push-Location $RepoDir
    try {
        if ($Ok) { $null = Invoke-Native 'py' @('-3', '-m', 'ccsync', 'status', '--set-ok') }
        else { $null = Invoke-Native 'py' @('-3', '-m', 'ccsync', 'status', '--set-fail', $Message) }
    } finally { Pop-Location }
}

function Fail([string]$Message) {
    Write-Log "FAIL: $Message"
    Set-Status $false $Message
    exit 0
}

Push-Location $RepoDir
try {
    $branch = Invoke-Native 'git' @('rev-parse', '--abbrev-ref', 'HEAD')
    if ($branch.Output -ne $SyncBranch) { Fail "repo is on '$($branch.Output)', not '$SyncBranch'; sync skipped" }

    $export = Invoke-Native 'py' @('-3', '-m', 'ccsync', 'export')
    if ($export.Code -eq $ExitBusy) { Write-Log 'another sync is running; skipped'; exit 0 }
    if ($export.Code -ne 0) {
        # Undo partial exports so a blocked secret never lingers in the working tree.
        foreach ($path in $ExportedPaths) {
            if (Test-Path (Join-Path $RepoDir $path)) {
                $null = Invoke-Native 'git' @('checkout', '-q', 'HEAD', '--', $path)
            }
        }
        $null = Invoke-Native 'git' (@('clean', '-fdq', '--') + $ExportedPaths)
        Fail $export.Output
    }

    $null = Invoke-Native 'git' @('add', '-A')
    $diff = Invoke-Native 'git' @('diff', '--cached', '--quiet')
    if ($diff.Code -ne 0) {
        $commit = Invoke-Native 'git' @('commit', '-q', '-m', 'chore: sync claude config')
        if ($commit.Code -ne 0) { Fail "git commit failed: $($commit.Output)" }
        Write-Log 'committed changes'
    }

    # Always push: retries commits left behind by an earlier failed push.
    $push = Invoke-Native 'git' @('push', '-q', 'origin', "HEAD:$SyncBranch")
    if ($push.Code -ne 0) { Fail "git push failed: $($push.Output)" }

    Write-Log 'ok'
    Set-Status $true 'ok'
} finally {
    Pop-Location
}
exit 0
