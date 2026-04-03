param(
    [string]$WorkspaceRoot = (Join-Path $PSScriptRoot ".."),
    [ValidateSet("AppOnly", "WorkspaceFull")]
    [string]$BundleProfile = "WorkspaceFull",
    [string]$OutputRoot = "",
    [string]$PythonExe = "",
    [switch]$Clean
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

function Remove-IfExists {
    param([Parameter(Mandatory = $true)][string]$TargetPath)

    if (Test-Path $TargetPath) {
        Remove-Item -LiteralPath $TargetPath -Recurse -Force
    }
}

function Ensure-Directory {
    param([Parameter(Mandatory = $true)][string]$TargetPath)

    if (-not (Test-Path $TargetPath)) {
        New-Item -ItemType Directory -Path $TargetPath | Out-Null
    }
}

function Copy-IntoStage {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$StageRoot
    )

    if (-not (Test-Path $SourcePath)) {
        return
    }

    $name = Split-Path -Path $SourcePath -Leaf
    $destination = Join-Path $StageRoot $name
    Copy-Item -LiteralPath $SourcePath -Destination $destination -Recurse -Force
}

$WorkspaceRoot = Get-AbsolutePath -PathString $WorkspaceRoot
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $WorkspaceRoot "artifacts"
}
$OutputRoot = Get-AbsolutePath -PathString $OutputRoot

$qtEnvPython = Join-Path $WorkspaceRoot ".qt-conda-env\python.exe"
$venvPython = Join-Path $WorkspaceRoot ".qt-venv\Scripts\python.exe"
if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    if (Test-Path $qtEnvPython) {
        $PythonExe = $qtEnvPython
    }
    elseif (Test-Path $venvPython) {
        $PythonExe = $venvPython
    }
    else {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonCommand) {
            throw "No usable Python interpreter was found. Provide -PythonExe explicitly."
        }
        $PythonExe = $pythonCommand.Source
    }
}
$PythonExe = Get-AbsolutePath -PathString $PythonExe
if (-not (Test-Path $PythonExe)) {
    throw "Python interpreter was not found: $PythonExe"
}

$buildRoot = Join-Path $OutputRoot "pyinstaller-build"
$distRoot = Join-Path $OutputRoot "dist"
$stageRoot = Join-Path $OutputRoot ("ProjectRAT-" + $BundleProfile)
$zipPath = Join-Path $OutputRoot ("ProjectRAT-" + $BundleProfile + ".zip")

if ($Clean) {
    Write-Step "Cleaning previous artifacts"
    Remove-IfExists -TargetPath $buildRoot
    Remove-IfExists -TargetPath $distRoot
    Remove-IfExists -TargetPath $stageRoot
    Remove-IfExists -TargetPath $zipPath
}

Ensure-Directory -TargetPath $OutputRoot
Ensure-Directory -TargetPath $buildRoot
Ensure-Directory -TargetPath $distRoot

Write-Step "Preparing PyInstaller build"
$pythonHome = Split-Path -Path $PythonExe -Parent
$pythonPathEntries = @(
    $pythonHome,
    (Join-Path $pythonHome "Scripts"),
    (Join-Path $pythonHome "Library\bin"),
    $env:PATH
) | Where-Object { $_ -and $_.Length -gt 0 }
$env:PATH = ($pythonPathEntries -join [System.IO.Path]::PathSeparator)

$pyinstallerCheck = & $PythonExe -m PyInstaller --version 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is not available in $PythonExe. Install it first with 'python -m pip install pyinstaller'."
}

$pyinstallerArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--windowed",
    "--onedir",
    "--name", "ProjectRAT",
    "--specpath", $buildRoot,
    "--workpath", (Join-Path $buildRoot "work"),
    "--distpath", $distRoot,
    "--paths", $WorkspaceRoot,
    "--hidden-import", "project_rat_gui_qt",
    "--hidden-import", "project_rat_cct",
    "--hidden-import", "vtkmodules.qt.QVTKRenderWindowInteractor",
    "--collect-all", "PySide6",
    "--collect-all", "vtkmodules",
    "--add-data", ((Join-Path $WorkspaceRoot "scripts") + ";scripts"),
    "--add-data", ((Join-Path $WorkspaceRoot "README.md") + ";."),
    "--add-data", ((Join-Path $WorkspaceRoot "project_rat_gui.py") + ";."),
    "--add-data", ((Join-Path $WorkspaceRoot "project_rat_cct.py") + ";."),
    "--add-data", ((Join-Path $WorkspaceRoot "project_rat_gui_qt.py") + ";."),
    (Join-Path $WorkspaceRoot "project_rat_gui.py")
)

Write-Step "Running PyInstaller"
& $PythonExe @pyinstallerArgs
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

$builtAppRoot = Join-Path $distRoot "ProjectRAT"
if (-not (Test-Path $builtAppRoot)) {
    throw "PyInstaller did not produce the expected output directory: $builtAppRoot"
}

Write-Step "Assembling portable layout"
Remove-IfExists -TargetPath $stageRoot
Copy-Item -LiteralPath $builtAppRoot -Destination $stageRoot -Recurse -Force

$commonPaths = @(
    (Join-Path $WorkspaceRoot "scripts"),
    (Join-Path $WorkspaceRoot "workspace-overlays"),
    (Join-Path $WorkspaceRoot "README.md"),
    (Join-Path $WorkspaceRoot "project_rat_gui.py"),
    (Join-Path $WorkspaceRoot "project_rat_gui_qt.py"),
    (Join-Path $WorkspaceRoot "project_rat_cct.py")
)
foreach ($path in $commonPaths) {
    Copy-IntoStage -SourcePath $path -StageRoot $stageRoot
}

if ($BundleProfile -eq "WorkspaceFull") {
    $workspacePaths = @(
        "cct-workbench",
        "materials-cpp",
        "pyrat",
        "rat-common",
        "rat-distmesh-cpp",
        "rat-documentation",
        "rat-math",
        "rat-mlfmm",
        "rat-models",
        "rat-nl",
        "rat-vcpkg",
        "tools",
        "vcpkg"
    )
    foreach ($relativePath in $workspacePaths) {
        Copy-IntoStage -SourcePath (Join-Path $WorkspaceRoot $relativePath) -StageRoot $stageRoot
    }
}

$launchScript = @"
@echo off
setlocal
cd /d "%~dp0"
start "" "%~dp0ProjectRAT.exe" %*
"@
[System.IO.File]::WriteAllText((Join-Path $stageRoot "Launch-Project-RAT.bat"), $launchScript, [System.Text.Encoding]::ASCII)

$bootstrapScript = @"
@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap_project_rat_workspace.ps1" -WorkspaceRoot "%~dp0"
if errorlevel 1 pause
"@
[System.IO.File]::WriteAllText((Join-Path $stageRoot "Bootstrap-Project-RAT.bat"), $bootstrapScript, [System.Text.Encoding]::ASCII)

$quickStart = @"
Project RAT Portable
====================

1. Double-click Launch-Project-RAT.bat to start the GUI.
2. If this is an AppOnly package, run Bootstrap-Project-RAT.bat first.
3. For compilation features on a new machine, install Microsoft Visual Studio Build Tools with C++.

Bundle profile: $BundleProfile
Workspace root inside package: $stageRoot
"@
[System.IO.File]::WriteAllText((Join-Path $stageRoot "PORTABLE-README.txt"), $quickStart, [System.Text.Encoding]::UTF8)

Write-Step "Creating zip archive"
if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $stageRoot "*") -DestinationPath $zipPath -CompressionLevel Optimal

Write-Host ""
Write-Host "Portable bundle created:"
Write-Host ("  Folder: " + $stageRoot)
Write-Host ("  Zip:    " + $zipPath)
