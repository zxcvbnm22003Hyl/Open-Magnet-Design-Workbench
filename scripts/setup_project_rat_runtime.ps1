param(
    [string]$WorkspaceRoot = (Join-Path $PSScriptRoot ".."),
    [switch]$Launch
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

function Get-PythonCandidates {
    $candidates = @()

    $fromPath = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($fromPath) {
        $candidates += $fromPath.Source
    }

    $pyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        foreach ($version in @("-3.12", "-3.11", "-3")) {
            $resolved = & $pyLauncher.Source $version -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $resolved) {
                $candidates += $resolved.ToString().Trim()
                break
            }
        }
    }

    $commonRoots = @(
        (Join-Path $env:LocalAppData "Programs\Python"),
        "C:\Python312",
        "C:\Python311"
    ) | Where-Object { $_ -and (Test-Path $_) }

    foreach ($root in $commonRoots) {
        Get-ChildItem -Path $root -Directory -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending |
            ForEach-Object {
                $candidate = Join-Path $_.FullName "python.exe"
                if (Test-Path $candidate) {
                    $candidates += $candidate
                }
            }
    }

    return $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique
}

function Resolve-BasePython {
    $candidate = Get-PythonCandidates | Select-Object -First 1
    if ($candidate) {
        return $candidate
    }

    return $null
}

function Install-PythonWithWinget {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "Python was not found and winget is unavailable. Install Python 3.11+ and rerun this script."
    }

    Write-Step "Installing Python 3.12 with winget"
    & $winget.Source install --id Python.Python.3.12 -e --scope user --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "winget failed to install Python."
    }
}

$WorkspaceRoot = Get-AbsolutePath -PathString $WorkspaceRoot
$venvRoot = Join-Path $WorkspaceRoot ".qt-venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$requirementsPath = Join-Path $WorkspaceRoot "requirements-gui.txt"
$guiEntry = Join-Path $WorkspaceRoot "project_rat_gui.py"

if (-not (Test-Path $requirementsPath)) {
    throw "requirements-gui.txt was not found under $WorkspaceRoot"
}

if (-not (Test-Path $venvPython)) {
    $basePython = Resolve-BasePython
    if (-not $basePython) {
        Install-PythonWithWinget
        $basePython = Resolve-BasePython
    }
    if (-not $basePython) {
        throw "Python installation could not be resolved after installation."
    }

    Write-Step "Creating GUI runtime"
    & $basePython -m venv $venvRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create virtual environment under $venvRoot"
    }
}

Write-Step "Installing GUI dependencies"
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upgrade pip."
}

& $venvPython -m pip install -r $requirementsPath
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install GUI dependencies."
}

Write-Host ""
Write-Host "GUI runtime is ready:"
Write-Host ("  " + $venvPython)

if ($Launch) {
    Write-Step "Launching Project RAT"
    & $venvPython $guiEntry
    exit $LASTEXITCODE
}
