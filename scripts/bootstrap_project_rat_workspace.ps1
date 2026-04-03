param(
    [string]$WorkspaceRoot = (Join-Path $PSScriptRoot "..")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-AbsolutePath {
    param([Parameter(Mandatory = $true)][string]$PathString)

    if ([System.IO.Path]::IsPathRooted($PathString)) {
        return [System.IO.Path]::GetFullPath($PathString)
    }

    return [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $PathString))
}

function Write-Step {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host ""
    Write-Host ("=== " + $Message + " ===")
}

function Ensure-GitRepo {
    param(
        [Parameter(Mandatory = $true)][string]$TargetPath,
        [Parameter(Mandatory = $true)][string]$RepositoryUrl
    )

    if (Test-Path (Join-Path $TargetPath ".git")) {
        Write-Host ("[ok] " + $TargetPath)
        return
    }

    if (Test-Path $TargetPath) {
        throw "Target path exists but is not a git repository: $TargetPath"
    }

    & git clone --depth 1 $RepositoryUrl $TargetPath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to clone $RepositoryUrl"
    }
}

function Ensure-Download {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$TargetPath
    )

    if (Test-Path $TargetPath) {
        Write-Host ("[ok] " + $TargetPath)
        return
    }

    $parent = Split-Path -Path $TargetPath -Parent
    if (-not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent | Out-Null
    }

    Invoke-WebRequest -Uri $Url -OutFile $TargetPath
}

function Ensure-ExpandedArchive {
    param(
        [Parameter(Mandatory = $true)][string]$ArchivePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )

    if (Test-Path $DestinationPath) {
        Write-Host ("[ok] " + $DestinationPath)
        return
    }

    if (-not (Test-Path $ArchivePath)) {
        throw "Archive was not found: $ArchivePath"
    }

    New-Item -ItemType Directory -Path $DestinationPath -Force | Out-Null
    Expand-Archive -Path $ArchivePath -DestinationPath $DestinationPath -Force
}

function Sync-DirectoryContents {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )

    if (-not (Test-Path $SourcePath)) {
        return
    }

    New-Item -ItemType Directory -Path $DestinationPath -Force | Out-Null
    Get-ChildItem -Path $SourcePath -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $target = Join-Path $DestinationPath $_.Name
        if (Test-Path $target) {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
        Copy-Item -LiteralPath $_.FullName -Destination $target -Recurse -Force
    }
}

$WorkspaceRoot = Get-AbsolutePath -PathString $WorkspaceRoot
$toolsRoot = Join-Path $WorkspaceRoot "tools"
$downloadsRoot = Join-Path $toolsRoot "downloads"
$overlayPortsSource = Join-Path $WorkspaceRoot "workspace-overlays\rat-vcpkg\ports"
$overlayPortsDestination = Join-Path $WorkspaceRoot "rat-vcpkg\ports"

$repos = @{
    "materials-cpp" = "https://gitlab.com/Project-Rat/materials-cpp.git"
    "pyrat" = "https://gitlab.com/Project-Rat/pyrat.git"
    "rat-common" = "https://gitlab.com/Project-Rat/rat-common.git"
    "rat-distmesh-cpp" = "https://gitlab.com/Project-Rat/rat-distmesh-cpp.git"
    "rat-documentation" = "https://gitlab.com/Project-Rat/rat-documentation.git"
    "rat-math" = "https://gitlab.com/Project-Rat/rat-math.git"
    "rat-mlfmm" = "https://gitlab.com/Project-Rat/rat-mlfmm.git"
    "rat-models" = "https://gitlab.com/Project-Rat/rat-models.git"
    "rat-nl" = "https://gitlab.com/Project-Rat/rat-nl.git"
    "rat-vcpkg" = "https://gitlab.com/Project-Rat/rat-vcpkg.git"
    "vcpkg" = "https://github.com/microsoft/vcpkg.git"
}

Write-Step "Cloning required repositories"
foreach ($name in $repos.Keys | Sort-Object) {
    Ensure-GitRepo -TargetPath (Join-Path $WorkspaceRoot $name) -RepositoryUrl $repos[$name]
}

Write-Step "Syncing local rat-vcpkg overlays"
Sync-DirectoryContents -SourcePath $overlayPortsSource -DestinationPath $overlayPortsDestination

Write-Step "Ensuring portable tool downloads"
Ensure-Download -Url "https://aka.ms/vs/17/release/vs_BuildTools.exe" -TargetPath (Join-Path $toolsRoot "vs_BuildTools.exe")
Ensure-Download -Url "https://github.com/ninja-build/ninja/releases/download/v1.13.2/ninja-win.zip" -TargetPath (Join-Path $downloadsRoot "ninja-win.zip")
Ensure-Download -Url "https://github.com/Kitware/CMake/releases/download/v3.31.10/cmake-3.31.10-windows-x86_64.zip" -TargetPath (Join-Path $downloadsRoot "cmake-3.31.10-windows-x86_64.zip")
Ensure-ExpandedArchive -ArchivePath (Join-Path $downloadsRoot "ninja-win.zip") -DestinationPath (Join-Path $toolsRoot "ninja-1.13.2")
Ensure-ExpandedArchive -ArchivePath (Join-Path $downloadsRoot "cmake-3.31.10-windows-x86_64.zip") -DestinationPath (Join-Path $toolsRoot "cmake-3.31.10")

Write-Host ""
Write-Host "Workspace bootstrap finished."
Write-Host "Next steps:"
Write-Host "  1. Run .\\Run-Project-RAT.bat to create the GUI runtime if needed."
Write-Host "  2. Install Visual Studio Build Tools with C++ using tools\\vs_BuildTools.exe if you need local builds."
Write-Host "  3. Run scripts\\project_rat_manager.ps1 -Action bootstrap-vcpkg"
