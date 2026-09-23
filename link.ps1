#Requires -Version 5.1
<#
.SYNOPSIS
    Link skills from this repo into ~/.claude/, ~/.codex/, and ~/.gemini/antigravity-cli/.

.DESCRIPTION
    PowerShell variant of link.sh. Creates Windows junction points via
    New-Item -ItemType Junction. Junctions work without Developer Mode
    or elevation and are followed by tools that don't chase symlinks.

.PARAMETER DryRun
    Show what would be done without doing it.

.PARAMETER Unlink
    Remove links (restore nothing; just unlink).

.PARAMETER Prune
    Only remove dead links that point into this repo.

.PARAMETER NoClaude
    Skip linking and pruning for Claude (~/.claude/skills).

.PARAMETER NoCodex
    Skip linking and pruning for Codex (~/.codex/skills).

.PARAMETER NoGemini
    Skip linking and pruning for Gemini (~/.gemini/antigravity-cli/skills).

.EXAMPLE
    ./link.ps1

.EXAMPLE
    ./link.ps1 -DryRun

.EXAMPLE
    ./link.ps1 -Unlink

.EXAMPLE
    ./link.ps1 -Prune

.EXAMPLE
    ./link.ps1 -NoClaude -NoCodex
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Unlink,
    [switch]$Prune,
    [switch]$NoClaude,
    [switch]$NoCodex,
    [switch]$NoGemini
)

$ErrorActionPreference = 'Stop'

$Repo      = $PSScriptRoot
$BackupDir = Join-Path $Repo ".backups/$(Get-Date -Format 'yyyyMMdd-HHmmss')"

# Items managed by other repos (agent-commit-command, etc.) — skip these.
$SkipClaudeSkills = @('macos-automation-skill')

function Test-IsLink {
    param([string]$Path)
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    return ($null -ne $item -and $item.LinkType -in @('SymbolicLink', 'Junction'))
}

function Get-LinkTargetPath {
    param([string]$Path)
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    if ($null -eq $item -or $item.LinkType -notin @('SymbolicLink', 'Junction')) { return $null }
    if ($item.PSObject.Properties['LinkTarget'] -and $item.LinkTarget) {
        return [string]$item.LinkTarget
    }
    if ($item.Target) {
        return [string](@($item.Target)[0])
    }
    return $null
}

function Test-PathsEqual {
    param(
        [string]$First,
        [string]$Second
    )

    if ([string]::IsNullOrWhiteSpace($First) -or [string]::IsNullOrWhiteSpace($Second)) {
        return $false
    }

    try {
        $firstPath = [System.IO.Path]::GetFullPath($First).TrimEnd('\', '/')
        $secondPath = [System.IO.Path]::GetFullPath($Second).TrimEnd('\', '/')
    }
    catch {
        return $false
    }

    return [string]::Equals($firstPath, $secondPath, [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-IsRepoTarget {
    param([string]$Target)

    if ([string]::IsNullOrWhiteSpace($Target) -or -not [System.IO.Path]::IsPathRooted($Target)) {
        return $false
    }

    try {
        $repoRoot = [System.IO.Path]::GetFullPath($Repo).TrimEnd('\', '/')
        $targetPath = [System.IO.Path]::GetFullPath($Target).TrimEnd('\', '/')
    }
    catch {
        return $false
    }

    $repoPrefix = $repoRoot + [System.IO.Path]::DirectorySeparatorChar
    return $targetPath.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)
}

function Invoke-Link {
    param(
        [Parameter(Mandatory)][string]$Source,
        [Parameter(Mandatory)][string]$Destination
    )

    if ($Unlink) {
        if (Test-IsLink $Destination) {
            Write-Host "unlink $Destination"
            if (-not $DryRun) { Remove-Item -LiteralPath $Destination -Force }
        }
        return
    }

    # If dest is already a correct link, skip.
    if (Test-IsLink $Destination) {
        $current = Get-LinkTargetPath $Destination
        if (Test-PathsEqual $current $Source) {
            Write-Host "ok     $Destination -> $Source"
            return
        }
        # Link exists but points elsewhere — remove it.
        Write-Host "relink $Destination"
        if (-not $DryRun) { Remove-Item -LiteralPath $Destination -Force }
    }
    elseif (Test-Path -LiteralPath $Destination) {
        # Dest exists and is NOT a link — back it up.
        $destName = Split-Path -Leaf $Destination
        Write-Host "backup $Destination -> $BackupDir/$destName"
        if (-not $DryRun) {
            New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
            Move-Item -LiteralPath $Destination -Destination (Join-Path $BackupDir $destName)
        }
    }

    Write-Host "link   $Destination -> $Source"
    if (-not $DryRun) {
        New-Item -ItemType Junction -Path $Destination -Value $Source | Out-Null
    }
}

# Remove links in $Directory that point into this repo but whose target is gone.
function Invoke-PruneDirectory {
    param([Parameter(Mandatory)][string]$Directory)

    if (-not (Test-Path -LiteralPath $Directory -PathType Container)) { return }

    foreach ($item in Get-ChildItem -LiteralPath $Directory -Force) {
        $link = $item.FullName
        if (-not (Test-IsLink $link)) { continue }

        $target = Get-LinkTargetPath $link
        # Only touch links we manage (pointing into this repo).
        if (-not (Test-IsRepoTarget $target)) { continue }
        if (Test-Path -LiteralPath $target) { continue }

        Write-Host "prune  $link -> $target (missing)"
        if (-not $DryRun) { Remove-Item -LiteralPath $link -Force }
    }
}

function Invoke-PruneAll {
    Write-Host "=== Prune dead links ==="
    if (-not $NoClaude) { Invoke-PruneDirectory "$HOME/.claude/skills" }
    if (-not $NoCodex)  { Invoke-PruneDirectory "$HOME/.codex/skills" }
    if (-not $NoGemini) { Invoke-PruneDirectory "$HOME/.gemini/antigravity-cli/skills" }
}

if ($Prune) {
    Invoke-PruneAll
    Write-Host ""
    Write-Host "Done."
    return
}

# --- Common skills (installed to Claude, Codex, and Gemini) ---
if (-not $NoClaude -or -not $NoCodex -or -not $NoGemini) {
    Write-Host "=== Common skills ==="
    if (-not $DryRun -and -not $Unlink) {
        if (-not $NoClaude) { New-Item -ItemType Directory -Path "$HOME/.claude/skills" -Force | Out-Null }
        if (-not $NoCodex)  { New-Item -ItemType Directory -Path "$HOME/.codex/skills" -Force | Out-Null }
        if (-not $NoGemini) { New-Item -ItemType Directory -Path "$HOME/.gemini/antigravity-cli/skills" -Force | Out-Null }
    }
    foreach ($item in Get-ChildItem -LiteralPath "$Repo/common-skills" -Directory) {
        $name = $item.Name
        if (-not $NoClaude) { Invoke-Link -Source "$Repo/common-skills/$name" -Destination "$HOME/.claude/skills/$name" }
        if (-not $NoCodex)  { Invoke-Link -Source "$Repo/common-skills/$name" -Destination "$HOME/.codex/skills/$name" }
        if (-not $NoGemini) { Invoke-Link -Source "$Repo/common-skills/$name" -Destination "$HOME/.gemini/antigravity-cli/skills/$name" }
    }
}

# --- Claude-only skills ---
if (-not $NoClaude -and (Test-Path -LiteralPath "$Repo/claude-skills" -PathType Container)) {
    Write-Host "=== Claude skills ==="
    foreach ($item in Get-ChildItem -LiteralPath "$Repo/claude-skills" -Directory) {
        $name = $item.Name
        if ($name -eq 'skills') { continue }  # skip nested 'skills' dir if present
        if ($SkipClaudeSkills -contains $name) { continue }
        Invoke-Link -Source "$Repo/claude-skills/$name" -Destination "$HOME/.claude/skills/$name"
    }
}

# --- Codex-only skills ---
if (-not $NoCodex -and (Test-Path -LiteralPath "$Repo/codex-skills" -PathType Container)) {
    Write-Host "=== Codex skills ==="
    foreach ($item in Get-ChildItem -LiteralPath "$Repo/codex-skills" -Directory) {
        $name = $item.Name
        Invoke-Link -Source "$Repo/codex-skills/$name" -Destination "$HOME/.codex/skills/$name"
    }
}

# --- Gemini-only skills ---
if (-not $NoGemini -and (Test-Path -LiteralPath "$Repo/gemini-skills" -PathType Container)) {
    Write-Host "=== Gemini skills ==="
    foreach ($item in Get-ChildItem -LiteralPath "$Repo/gemini-skills" -Directory) {
        $name = $item.Name
        Invoke-Link -Source "$Repo/gemini-skills/$name" -Destination "$HOME/.gemini/antigravity-cli/skills/$name"
    }
}

Invoke-PruneAll

Write-Host ""
Write-Host "Done."
