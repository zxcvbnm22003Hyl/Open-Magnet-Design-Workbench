param(
    [ValidateSet(
        "status",
        "bootstrap-vcpkg",
        "install-rat-models",
        "install-rat-models-no-nl",
        "build-example",
        "run-example",
        "build-run-example",
        "build-cct-project",
        "run-cct-project",
        "build-run-cct-project",
        "export-cct-opera",
        "build-export-cct-opera",
        "build-pyrat-wheel"
    )]
    [string]$Action = "status",
    [string]$WorkspaceRoot = (Join-Path $PSScriptRoot ".."),
    [string]$VcpkgRoot = "",
    [string]$Triplet = "x64-windows-release",
    [string]$Example = "dmshyoke1",
    [string]$ProjectDir = "",
    [string]$ExecutableName = ""
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

function Get-BuildEnvScript {
    if ($WorkspaceRoot) {
        $localVcVars = Join-Path $WorkspaceRoot "tools\msvc-local\VC\Auxiliary\Build\vcvars64.bat"
        if (Test-Path $localVcVars) {
            return [pscustomobject]@{
                Kind = "VcVars64"
                Path = $localVcVars
            }
        }
    }

    $vsWhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path $vsWhere) {
        $installationPathRaw = & $vsWhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | Select-Object -First 1
        if ($installationPathRaw) {
            $installationPath = $installationPathRaw.ToString().Trim()
            if (-not [string]::IsNullOrWhiteSpace($installationPath)) {
                $candidate = Join-Path $installationPath "Common7\Tools\VsDevCmd.bat"
                if (Test-Path $candidate) {
                    return [pscustomobject]@{
                        Kind = "VsDevCmd"
                        Path = $candidate
                    }
                }
            }
        }
    }

    $vsDevCmdFallbacks = @(
        "C:\Program\Common7\Tools\VsDevCmd.bat",
        "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat",
        "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat"
    )
    foreach ($candidate in $vsDevCmdFallbacks) {
        if (Test-Path $candidate) {
            return [pscustomobject]@{
                Kind = "VsDevCmd"
                Path = $candidate
            }
        }
    }

    $vcVarsFallbacks = @(
        "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat",
        "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat",
        "C:\Program\VC\Auxiliary\Build\vcvars64.bat"
    )
    foreach ($candidate in $vcVarsFallbacks) {
        if (Test-Path $candidate) {
            return [pscustomobject]@{
                Kind = "VcVars64"
                Path = $candidate
            }
        }
    }

    return $null
}

function Get-WorkspaceToolPath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Pattern
    )

    $matches = Get-ChildItem -Path $Root -Recurse -Filter $Pattern -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
    if ($matches) {
        return ($matches | Sort-Object | Select-Object -Last 1)
    }

    return $null
}

function Get-WindowsSdkBinDirectory {
    $sdkRoots = @(
        "C:\Program Files (x86)\Windows Kits\10\bin",
        "C:\Program Files\Windows Kits\10\bin"
    )

    foreach ($sdkRoot in $sdkRoots) {
        if (-not (Test-Path $sdkRoot)) {
            continue
        }

        $candidate = Get-ChildItem -Path $sdkRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object { Test-Path (Join-Path $_.FullName "x64\rc.exe") } |
            Sort-Object Name -Descending |
            Select-Object -First 1
        if ($candidate) {
            return (Join-Path $candidate.FullName "x64")
        }
    }

    return $null
}

function Get-WindowsSdkRoot {
    $sdkRoots = @(
        "C:\Program Files (x86)\Windows Kits\10",
        "C:\Program Files\Windows Kits\10"
    )

    foreach ($sdkRoot in $sdkRoots) {
        if (Test-Path $sdkRoot) {
            return $sdkRoot
        }
    }

    return $null
}

function Get-WindowsSdkVersion {
    $sdkRoot = Get-WindowsSdkRoot
    if (-not $sdkRoot) {
        return $null
    }

    $includeRoot = Join-Path $sdkRoot "Include"
    if (-not (Test-Path $includeRoot)) {
        return $null
    }

    $candidate = Get-ChildItem -Path $includeRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path (Join-Path $_.FullName "um\Windows.h") } |
        Sort-Object Name -Descending |
        Select-Object -First 1
    if ($candidate) {
        return $candidate.Name
    }

    return $null
}

function Get-WindowsSdkIncludeDirectories {
    $sdkRoot = Get-WindowsSdkRoot
    $sdkVersion = Get-WindowsSdkVersion
    if (-not $sdkRoot -or -not $sdkVersion) {
        return @()
    }

    $includeRoot = Join-Path (Join-Path $sdkRoot "Include") $sdkVersion
    return @("ucrt", "shared", "um", "winrt", "cppwinrt") |
        ForEach-Object { Join-Path $includeRoot $_ } |
        Where-Object { Test-Path $_ }
}

function Get-WindowsSdkLibraryDirectories {
    $sdkRoot = Get-WindowsSdkRoot
    $sdkVersion = Get-WindowsSdkVersion
    if (-not $sdkRoot -or -not $sdkVersion) {
        return @()
    }

    $libRoot = Join-Path (Join-Path $sdkRoot "Lib") $sdkVersion
    return @("ucrt\\x64", "um\\x64") |
        ForEach-Object { Join-Path $libRoot $_ } |
        Where-Object { Test-Path $_ }
}

function Get-WindowsSdkLibPathDirectories {
    $sdkRoot = Get-WindowsSdkRoot
    $sdkVersion = Get-WindowsSdkVersion
    if (-not $sdkRoot -or -not $sdkVersion) {
        return @()
    }

    $paths = @()
    $unionMetadata = Join-Path (Join-Path $sdkRoot "UnionMetadata") $sdkVersion
    if (Test-Path $unionMetadata) {
        $paths += $unionMetadata
    }
    $references = Join-Path $sdkRoot "References\CommonConfiguration\Neutral"
    if (Test-Path $references) {
        $paths += $references
    }
    return $paths
}

function Get-ClExecutable {
    $fromPath = Get-Command cl.exe -ErrorAction SilentlyContinue
    if ($fromPath) {
        return $fromPath.Source
    }

    if ($WorkspaceRoot) {
        $localRoot = Join-Path $WorkspaceRoot "tools\msvc-local\VC\Tools\MSVC"
        if (Test-Path $localRoot) {
            $candidate = Get-ChildItem -Path $localRoot -Directory -ErrorAction SilentlyContinue |
                Sort-Object Name -Descending |
                ForEach-Object { Join-Path $_.FullName "bin\Hostx64\x64\cl.exe" } |
                Where-Object { Test-Path $_ } |
                Select-Object -First 1
            if ($candidate) {
                return $candidate
            }
        }
    }

    $fallbackRoots = @(
        "C:\Program\VC\Tools\MSVC",
        "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC",
        "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC"
    )

    foreach ($fallbackRoot in $fallbackRoots) {
        if (-not (Test-Path $fallbackRoot)) {
            continue
        }

        $candidate = Get-ChildItem -Path $fallbackRoot -Directory -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending |
            ForEach-Object { Join-Path $_.FullName "bin\Hostx64\x64\cl.exe" } |
            Where-Object { Test-Path $_ } |
            Select-Object -First 1
        if ($candidate) {
            return $candidate
        }
    }

    return $null
}

function Get-MsvcToolsRoot {
    $cl = Get-ClExecutable
    if (-not $cl) {
        return $null
    }

    $binDir = Split-Path -Parent $cl
    return [System.IO.Path]::GetFullPath((Join-Path $binDir "..\..\.."))
}

function Get-RcExecutable {
    $fromPath = Get-Command rc.exe -ErrorAction SilentlyContinue
    if ($fromPath) {
        return $fromPath.Source
    }

    $windowsSdkBin = Get-WindowsSdkBinDirectory
    if ($windowsSdkBin) {
        $candidate = Join-Path $windowsSdkBin "rc.exe"
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
}

function Get-MtExecutable {
    $fromPath = Get-Command mt.exe -ErrorAction SilentlyContinue
    if ($fromPath) {
        return $fromPath.Source
    }

    $windowsSdkBin = Get-WindowsSdkBinDirectory
    if ($windowsSdkBin) {
        $candidate = Join-Path $windowsSdkBin "mt.exe"
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
}

function Get-ToolPathPrefix {
    param([Parameter(Mandatory = $true)][string]$Root)

    $paths = @()
    $cl = Get-ClExecutable
    if ($cl) {
        $paths += Split-Path -Parent $cl
    }

    $cmake = Get-WorkspaceToolPath -Root (Join-Path $Root "tools") -Pattern "cmake.exe"
    if ($cmake) {
        $paths += Split-Path -Parent $cmake
    }

    $ninja = Get-WorkspaceToolPath -Root (Join-Path $Root "tools") -Pattern "ninja.exe"
    if ($ninja) {
        $paths += Split-Path -Parent $ninja
    }

    $windowsSdkBin = Get-WindowsSdkBinDirectory
    if ($windowsSdkBin) {
        $paths += $windowsSdkBin
    }

    $runtimeBin = Join-Path $VcpkgRoot ("installed\" + $Triplet + "\bin")
    if (Test-Path $runtimeBin) {
        $paths += $runtimeBin
    }

    return ($paths | Select-Object -Unique) -join ";"
}

function Get-ExampleRoot {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Name
    )

    return (Join-Path (Join-Path $Root "rat-vcpkg\examples\rat\models") $Name)
}

function Get-ExampleExecutable {
    param(
        [Parameter(Mandatory = $true)][string]$ExampleRoot,
        [Parameter(Mandatory = $true)][string]$ExampleName
    )

    return Get-ProjectExecutable -ProjectRoot $ExampleRoot -ExecutableName $ExampleName
}

function Get-ProjectExecutable {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectRoot,
        [Parameter(Mandatory = $true)][string]$ExecutableName
    )

    $exeName = $ExecutableName + ".exe"
    $candidates = @(
        (Join-Path $ProjectRoot ("build\Release\bin\" + $exeName)),
        (Join-Path $ProjectRoot ("build\bin\" + $exeName)),
        (Join-Path $ProjectRoot ("build\Release\" + $exeName)),
        (Join-Path $ProjectRoot ("build\" + $exeName))
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
}

function Reset-BuildDir {
    param([Parameter(Mandatory = $true)][string]$ProjectRoot)

    $buildDir = Join-Path $ProjectRoot "build"
    if (Test-Path $buildDir) {
        Remove-Item -LiteralPath $buildDir -Recurse -Force
    }
}

function Invoke-InBuildEnv {
    param(
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$Command
    )

    $WorkingDirectory = Get-AbsolutePath $WorkingDirectory
    $toolPrefix = Get-ToolPathPrefix -Root $WorkspaceRoot
    $envSetup = @()
    if ($toolPrefix) {
        $envSetup += 'set "PATH=' + $toolPrefix + ';!PATH!"'
    }
    $envSetup += 'set "HTTP_PROXY=http://127.0.0.1:7897"'
    $envSetup += 'set "HTTPS_PROXY=http://127.0.0.1:7897"'
    $envSetup += 'set "ALL_PROXY=http://127.0.0.1:7897"'
    $envSetup += 'set "VCPKG_ROOT="'

    $msvcRoot = Get-MsvcToolsRoot
    if ($msvcRoot) {
        $msvcInclude = Join-Path $msvcRoot "include"
        $msvcLib = Join-Path $msvcRoot "lib\x64"
        if (Test-Path $msvcInclude) {
            $envSetup += 'set "INCLUDE=' + $msvcInclude + ';!INCLUDE!"'
        }
        if (Test-Path $msvcLib) {
            $envSetup += 'set "LIB=' + $msvcLib + ';!LIB!"'
            $envSetup += 'set "LIBPATH=' + $msvcLib + ';!LIBPATH!"'
        }
        $envSetup += 'set "VCToolsInstallDir=' + $msvcRoot + '"'
    }

    $sdkRoot = Get-WindowsSdkRoot
    $sdkVersion = Get-WindowsSdkVersion
    if ($sdkRoot -and $sdkVersion) {
        $envSetup += 'set "WindowsSdkDir=' + $sdkRoot + '"'
        $envSetup += 'set "WindowsSDKVersion=' + $sdkVersion + '"'
        $envSetup += 'set "UniversalCRTSdkDir=' + $sdkRoot + '"'
        foreach ($includePath in Get-WindowsSdkIncludeDirectories) {
            $envSetup += 'set "INCLUDE=' + $includePath + ';!INCLUDE!"'
        }
        foreach ($libPath in Get-WindowsSdkLibraryDirectories) {
            $envSetup += 'set "LIB=' + $libPath + ';!LIB!"'
        }
        foreach ($libPathEntry in Get-WindowsSdkLibPathDirectories) {
            $envSetup += 'set "LIBPATH=' + $libPathEntry + ';!LIBPATH!"'
        }
    }

    $envPrefix = [string]::Join(' && ', $envSetup)

    Write-Host ("PWD " + $WorkingDirectory)
    Write-Host ("CMD " + $Command)

    $buildEnvScript = Get-BuildEnvScript
    $scriptLines = @("@echo off")

    if ($buildEnvScript) {
        if ($buildEnvScript.Kind -eq "VcVars64") {
            $scriptLines += 'call "' + $buildEnvScript.Path + '" >nul'
        }
        else {
            $scriptLines += 'call "' + $buildEnvScript.Path + '" -arch=x64 -host_arch=x64 >nul'
        }
    }
    elseif (-not ((Get-Command cl.exe -ErrorAction SilentlyContinue) -and (Get-Command rc.exe -ErrorAction SilentlyContinue) -and (Get-Command mt.exe -ErrorAction SilentlyContinue))) {
        throw "MSVC Build Tools or Windows SDK tools were not found. Install Visual Studio Build Tools 2019 or 2022 with Desktop development with C++ and the Windows SDK."
    }

    $scriptLines += 'cd /d "' + $WorkingDirectory + '"'
    $scriptLines += 'setlocal EnableDelayedExpansion'
    $scriptLines += $envSetup
    $scriptLines += $Command

    $tempScript = Join-Path ([System.IO.Path]::GetTempPath()) ([System.IO.Path]::GetRandomFileName() + ".cmd")
    Set-Content -Path $tempScript -Value $scriptLines -Encoding ASCII
    try {
        cmd.exe /d /s /c ('"' + $tempScript + '"')
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Remove-Item -LiteralPath $tempScript -Force -ErrorAction SilentlyContinue
    }

    return
}

function Get-VcpkgExecutable {
    param([Parameter(Mandatory = $true)][string]$Root)

    $localExe = Join-Path $Root "vcpkg.exe"
    if (Test-Path $localExe) {
        return $localExe
    }

    $fromPath = Get-Command vcpkg.exe -ErrorAction SilentlyContinue
    if ($fromPath) {
        return $fromPath.Source
    }

    throw "vcpkg.exe was not found. Run the bootstrap-vcpkg action first."
}

function Get-CMakeToolchainPath {
    $toolchain = Join-Path $VcpkgRoot "scripts\buildsystems\vcpkg.cmake"
    if (-not (Test-Path $toolchain)) {
        throw "vcpkg toolchain file was not found under $toolchain"
    }
    return $toolchain
}

function Build-CMakeProject {
    param([Parameter(Mandatory = $true)][string]$ProjectRoot)

    $toolchain = Get-CMakeToolchainPath
    Reset-BuildDir -ProjectRoot $ProjectRoot
    $cl = Get-ClExecutable
    $rc = Get-RcExecutable
    $mt = Get-MtExecutable
    $msvcRoot = Get-MsvcToolsRoot
    if (-not $cl) {
        throw "cl.exe was not found."
    }
    if (-not $rc) {
        throw "rc.exe was not found."
    }
    if (-not $mt) {
        throw "mt.exe was not found."
    }

    $cl = (($cl -replace '\\', '/').ToString()).Trim()
    $rc = (($rc -replace '\\', '/').ToString()).Trim()
    $mt = (($mt -replace '\\', '/').ToString()).Trim()
    $toolchain = (($toolchain -replace '\\', '/').ToString()).Trim()
    $tripletValue = $Triplet.Trim()

    $configure = 'cmake -B build -S . -G "Ninja" -DCMAKE_BUILD_TYPE="Release" -DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY -DCMAKE_C_COMPILER="' + $cl + '" -DCMAKE_CXX_COMPILER="' + $cl + '" -DCMAKE_RC_COMPILER="' + $rc + '" -DCMAKE_MT="' + $mt + '" -DCMAKE_TOOLCHAIN_FILE="' + $toolchain + '" -DVCPKG_TARGET_TRIPLET="' + $tripletValue + '"'
    if ($msvcRoot) {
        $openMpLib = Join-Path $msvcRoot "lib\x64\vcomp.lib"
        if (Test-Path $openMpLib) {
            $openMpLib = (($openMpLib -replace '\\', '/').ToString()).Trim()
            $configure += ' -DOpenMP_C_FLAGS=/openmp -DOpenMP_C_LIB_NAMES=vcomp -DOpenMP_CXX_FLAGS=/openmp -DOpenMP_CXX_LIB_NAMES=vcomp -DOpenMP_vcomp_LIBRARY="' + $openMpLib + '"'
        }
    }
    $build = 'cmake --build build --config Release'
    Invoke-InBuildEnv -WorkingDirectory $ProjectRoot -Command ($configure + " && " + $build)
}

function Run-Executable {
    param(
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$ExecutablePath,
        [string[]]$Arguments = @()
    )

    $command = '"' + $ExecutablePath + '"'
    if ($Arguments.Count -gt 0) {
        $quotedArguments = foreach ($argument in $Arguments) {
            if ($argument -match '\s') {
                '"' + ($argument -replace '"', '\"') + '"'
            }
            else {
                $argument
            }
        }
        $command += ' ' + ($quotedArguments -join ' ')
    }
    Invoke-InBuildEnv -WorkingDirectory $WorkingDirectory -Command $command
}

function Update-CctOutputAliases {
    param([Parameter(Mandatory = $true)][string]$OutputDirectory)

    if (-not (Test-Path $OutputDirectory)) {
        return
    }

    $aliasMap = @{
        "coilmesh"  = "coil_field_mesh"
        "harmonics" = "field_harmonics"
        "grid"      = "space_field_slice"
    }

    foreach ($sourcePrefix in $aliasMap.Keys) {
        $targetPrefix = $aliasMap[$sourcePrefix]

        Get-ChildItem -Path $OutputDirectory -File -Filter ($sourcePrefix + "*") -ErrorAction SilentlyContinue |
            ForEach-Object {
                $targetName = $_.Name -replace ("^" + [regex]::Escape($sourcePrefix)), $targetPrefix
                $targetPath = Join-Path $OutputDirectory $targetName
                $preserveExistingGridAlias = $sourcePrefix -eq "grid" -and (Test-Path $targetPath)

                if ($preserveExistingGridAlias) {
                    return
                }

                if ($_.Extension -ieq ".pvd") {
                    $content = Get-Content $_.FullName -Raw -Encoding UTF8
                    $content = $content -replace [regex]::Escape($sourcePrefix), $targetPrefix
                    Set-Content -Path $targetPath -Value $content -Encoding UTF8
                }
                else {
                    Copy-Item -LiteralPath $_.FullName -Destination $targetPath -Force
                }
            }
    }
}

function Get-RequiredProjectRoot {
    if (-not $ProjectDir) {
        throw "ProjectDir is required for this action."
    }

    $projectRoot = Get-AbsolutePath $ProjectDir
    if (-not (Test-Path $projectRoot)) {
        throw "Project directory was not found under $projectRoot"
    }
    if (-not (Test-Path (Join-Path $projectRoot "CMakeLists.txt"))) {
        throw "CMakeLists.txt was not found under $projectRoot"
    }
    return $projectRoot
}

function Get-RequiredExecutableName {
    if (-not $ExecutableName) {
        throw "ExecutableName is required for this action."
    }
    return $ExecutableName
}

$WorkspaceRoot = Get-AbsolutePath $WorkspaceRoot
if (-not $VcpkgRoot) {
    $VcpkgRoot = Join-Path $WorkspaceRoot "vcpkg"
}
$VcpkgRoot = Get-AbsolutePath $VcpkgRoot

$OverlayPorts = Join-Path $WorkspaceRoot "rat-vcpkg\ports"
$PyRatRoot = Join-Path $WorkspaceRoot "pyrat"
$ExamplesRoot = Join-Path $WorkspaceRoot "rat-vcpkg\examples\rat\models"
$CctWorkbenchRoot = Join-Path $WorkspaceRoot "cct-workbench"

switch ($Action) {
    "status" {
        Write-Step "Workspace status"
        Write-Host ("WorkspaceRoot : " + $WorkspaceRoot)
        Write-Host ("VcpkgRoot     : " + $VcpkgRoot)
        Write-Host ("OverlayPorts  : " + $OverlayPorts)
        Write-Host ("ExamplesRoot  : " + $ExamplesRoot)
        Write-Host ("CCT Root      : " + $CctWorkbenchRoot)
        $buildEnv = Get-BuildEnvScript
        Write-Host ("Build Env     : " + [string]($buildEnv.Path))
        Write-Host ("cl.exe        : " + [string](Get-ClExecutable))
        Write-Host ("rc.exe        : " + [string](Get-RcExecutable))
        Write-Host ("mt.exe        : " + [string](Get-MtExecutable))
        Write-Host ("Windows SDK   : " + [string](Get-WindowsSdkBinDirectory))
        Write-Host ("cmake         : " + [string](Get-WorkspaceToolPath -Root (Join-Path $WorkspaceRoot "tools") -Pattern "cmake.exe"))
        Write-Host ("ninja         : " + [string](Get-WorkspaceToolPath -Root (Join-Path $WorkspaceRoot "tools") -Pattern "ninja.exe"))
        Write-Host ("python        : " + [string](Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source))
        if (Test-Path (Join-Path $VcpkgRoot "vcpkg.exe")) {
            Write-Host ("vcpkg.exe     : " + (Join-Path $VcpkgRoot "vcpkg.exe"))
        }
        else {
            Write-Host "vcpkg.exe     : missing"
        }
    }

    "bootstrap-vcpkg" {
        $bootstrapScript = Join-Path $VcpkgRoot "bootstrap-vcpkg.bat"
        if (-not (Test-Path $bootstrapScript)) {
            throw "bootstrap-vcpkg.bat was not found under $VcpkgRoot"
        }

        Write-Step "Bootstrapping vcpkg"
        Invoke-InBuildEnv -WorkingDirectory $VcpkgRoot -Command ".\bootstrap-vcpkg.bat -disableMetrics"
        Write-Host "vcpkg bootstrap finished."
    }

    "install-rat-models" {
        if (-not (Test-Path $OverlayPorts)) {
            throw "Overlay ports were not found under $OverlayPorts"
        }

        $vcpkgExe = Get-VcpkgExecutable -Root $VcpkgRoot
        $packageSpec = "rat-models:$Triplet"

        Write-Step "Installing Project-Rat libraries with NL solver"
        $command = '"' + $vcpkgExe + '" install ' + $packageSpec + ' --overlay-ports="' + $OverlayPorts + '" --clean-after-build'
        Invoke-InBuildEnv -WorkingDirectory $WorkspaceRoot -Command $command
        Write-Host "RAT installation completed."
    }

    "install-rat-models-no-nl" {
        if (-not (Test-Path $OverlayPorts)) {
            throw "Overlay ports were not found under $OverlayPorts"
        }

        $vcpkgExe = Get-VcpkgExecutable -Root $VcpkgRoot
        $packageSpec = "rat-models[-nl]:$Triplet"

        Write-Step "Installing Project-Rat libraries without NL solver"
        $command = '"' + $vcpkgExe + '" install ' + $packageSpec + ' --overlay-ports="' + $OverlayPorts + '" --clean-after-build'
        Invoke-InBuildEnv -WorkingDirectory $WorkspaceRoot -Command $command
        Write-Host "RAT installation completed."
    }

    "build-example" {
        $exampleRoot = Get-ExampleRoot -Root $WorkspaceRoot -Name $Example
        if (-not (Test-Path $exampleRoot)) {
            throw "Example '$Example' was not found under $ExamplesRoot"
        }

        Write-Step ("Building example " + $Example)
        Build-CMakeProject -ProjectRoot $exampleRoot
        Write-Host ("Example build completed for " + $Example + ".")
    }

    "run-example" {
        $exampleRoot = Get-ExampleRoot -Root $WorkspaceRoot -Name $Example
        if (-not (Test-Path $exampleRoot)) {
            throw "Example '$Example' was not found under $ExamplesRoot"
        }

        $exampleExe = Get-ExampleExecutable -ExampleRoot $exampleRoot -ExampleName $Example
        if (-not $exampleExe) {
            throw "Example executable for '$Example' was not found. Run the build-example action first."
        }

        Write-Step ("Running example " + $Example)
        Run-Executable -WorkingDirectory $exampleRoot -ExecutablePath $exampleExe
        Write-Host ("Example run completed for " + $Example + ".")
    }

    "build-run-example" {
        $exampleRoot = Get-ExampleRoot -Root $WorkspaceRoot -Name $Example
        if (-not (Test-Path $exampleRoot)) {
            throw "Example '$Example' was not found under $ExamplesRoot"
        }

        Write-Step ("Building example " + $Example)
        Build-CMakeProject -ProjectRoot $exampleRoot

        $exampleExe = Get-ExampleExecutable -ExampleRoot $exampleRoot -ExampleName $Example
        if (-not $exampleExe) {
            throw "Example executable for '$Example' was not found after build."
        }

        Write-Step ("Running example " + $Example)
        Run-Executable -WorkingDirectory $exampleRoot -ExecutablePath $exampleExe
        Write-Host ("Example build and run completed for " + $Example + ".")
    }

    "build-cct-project" {
        $projectRoot = Get-RequiredProjectRoot
        $projectExecutableName = Get-RequiredExecutableName

        Write-Step ("Building magnet project " + $projectExecutableName)
        Build-CMakeProject -ProjectRoot $projectRoot
        Write-Host ("Magnet project build completed for " + $projectExecutableName + ".")
    }

    "run-cct-project" {
        $projectRoot = Get-RequiredProjectRoot
        $projectExecutableName = Get-RequiredExecutableName
        $projectExe = Get-ProjectExecutable -ProjectRoot $projectRoot -ExecutableName $projectExecutableName
        if (-not $projectExe) {
            throw "Executable '$projectExecutableName' was not found. Run the build-cct-project action first."
        }

        Write-Step ("Running magnet project " + $projectExecutableName)
        Run-Executable -WorkingDirectory $projectRoot -ExecutablePath $projectExe
        Update-CctOutputAliases -OutputDirectory (Join-Path $projectRoot "output")
        Write-Host ("Magnet project run completed for " + $projectExecutableName + ".")
    }

    "build-run-cct-project" {
        $projectRoot = Get-RequiredProjectRoot
        $projectExecutableName = Get-RequiredExecutableName

        Write-Step ("Building magnet project " + $projectExecutableName)
        Build-CMakeProject -ProjectRoot $projectRoot

        $projectExe = Get-ProjectExecutable -ProjectRoot $projectRoot -ExecutableName $projectExecutableName
        if (-not $projectExe) {
            throw "Executable '$projectExecutableName' was not found after build."
        }

        Write-Step ("Running magnet project " + $projectExecutableName)
        Run-Executable -WorkingDirectory $projectRoot -ExecutablePath $projectExe
        Update-CctOutputAliases -OutputDirectory (Join-Path $projectRoot "output")
        Write-Host ("Magnet project build and run completed for " + $projectExecutableName + ".")
    }

    "export-cct-opera" {
        $projectRoot = Get-RequiredProjectRoot
        $projectExecutableName = Get-RequiredExecutableName
        $projectExe = Get-ProjectExecutable -ProjectRoot $projectRoot -ExecutableName $projectExecutableName
        if (-not $projectExe) {
            throw "Executable '$projectExecutableName' was not found. Run the build-cct-project action first."
        }

        Write-Step ("Exporting OPERA conductor file for " + $projectExecutableName)
        Run-Executable -WorkingDirectory $projectRoot -ExecutablePath $projectExe -Arguments @("--export-opera")
        Update-CctOutputAliases -OutputDirectory (Join-Path $projectRoot "output")
        Write-Host ("OPERA conductor export completed for " + $projectExecutableName + ".")
    }

    "build-export-cct-opera" {
        $projectRoot = Get-RequiredProjectRoot
        $projectExecutableName = Get-RequiredExecutableName

        Write-Step ("Building magnet project " + $projectExecutableName)
        Build-CMakeProject -ProjectRoot $projectRoot

        $projectExe = Get-ProjectExecutable -ProjectRoot $projectRoot -ExecutableName $projectExecutableName
        if (-not $projectExe) {
            throw "Executable '$projectExecutableName' was not found after build."
        }

        Write-Step ("Exporting OPERA conductor file for " + $projectExecutableName)
        Run-Executable -WorkingDirectory $projectRoot -ExecutablePath $projectExe -Arguments @("--export-opera")
        Update-CctOutputAliases -OutputDirectory (Join-Path $projectRoot "output")
        Write-Host ("Magnet project build and OPERA export completed for " + $projectExecutableName + ".")
    }

    "build-pyrat-wheel" {
        if (-not (Test-Path $PyRatRoot)) {
            throw "pyrat repository was not found under $PyRatRoot"
        }

        $pythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue
        if (-not $pythonCmd) {
            throw "python.exe was not found in PATH."
        }

        Write-Step "Building pyRat wheel"
        $command = 'set "VCPKG_ROOT=' + $VcpkgRoot + '" && python .\scripts\py\make_wheel_vcpkg.py'
        Invoke-InBuildEnv -WorkingDirectory $PyRatRoot -Command $command
        Write-Host "pyRat wheel build completed."
    }
}
