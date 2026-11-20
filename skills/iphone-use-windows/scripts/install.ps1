[CmdletBinding()]
param(
    [string]$Python,
    [string]$Codex,
    [string]$MirrorPath,
    [string]$DependencyDirectory = (Join-Path $env:LOCALAPPDATA 'iphone-use-windows'),
    [switch]$SkipDrivers,
    [switch]$ConfigureOnly
)

$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
    throw 'iPhone Use for Windows requires Windows 10 or 11 x64. Run it from 64-bit PowerShell.'
}

$revision = 'c792fec205ad055d11f12b035c0c331102c9c72c'
$source = Join-Path $DependencyDirectory "iPhone-mcp-$revision"
$bootstrap = Join-Path $source 'scripts\bootstrap.ps1'
$runtimeVersion = 'v0.2.1'
$runtimeName = "iPhoneMirror-mcp-runtime-$runtimeVersion-win-x64.zip"
$baselineVersion = 'v1.8.5-pre6'
$setupName = "iPhoneMirror-Setup-$baselineVersion-x64.exe"

function Get-VerifiedDownload([string]$Uri, [string]$Name, [string]$ExpectedHash) {
    New-Item -ItemType Directory -Path $DependencyDirectory -Force | Out-Null
    $destination = Join-Path $DependencyDirectory $Name
    if (-not (Test-Path -LiteralPath $destination)) {
        $partial = "$destination.part"
        Write-Host "Downloading $Name from GitHub."
        & curl.exe --fail --silent --show-error --location --retry 2 --connect-timeout 15 --max-time 1800 --output $partial $Uri
        if ($LASTEXITCODE -ne 0) { throw "Download failed for $Name (curl exit $LASTEXITCODE)." }
        if ((Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash -ne $ExpectedHash) {
            throw "SHA-256 mismatch for $partial."
        }
        Move-Item -LiteralPath $partial -Destination $destination
    }
    if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -ne $ExpectedHash) {
        throw "SHA-256 mismatch for cached file $destination."
    }
    return $destination
}

if (-not $Codex) {
    $Codex = (Get-Command codex -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty Source)
}
if (-not $Codex) {
    $desktopBin = Join-Path $env:LOCALAPPDATA 'OpenAI\Codex\bin'
    if (Test-Path -LiteralPath $desktopBin) {
        $Codex = (Get-ChildItem -LiteralPath $desktopBin -Filter 'codex.exe' -File -Recurse |
            Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1 -ExpandProperty FullName)
    }
}
if (-not $Codex) {
    throw 'Codex was not found. Install Codex or specify its executable with -Codex.'
}
$codexPath = (Get-Command $Codex -CommandType Application | Select-Object -First 1).Source

if (-not (Test-Path -LiteralPath $bootstrap)) {
    $archive = Get-VerifiedDownload "https://codeload.github.com/RayrenSX/iPhone-mcp/zip/$revision" `
        "iPhone-mcp-$revision.zip" 'C4008B0641DDDA4268CB2F3CC6794FB8AD57F9137D658419F8365A5C18A839B4'
    Expand-Archive -LiteralPath $archive -DestinationPath $DependencyDirectory -Force
}
if (-not (Test-Path -LiteralPath $bootstrap)) {
    throw "Could not locate the verified iPhone-mcp bootstrap at $bootstrap."
}

$running = @(Get-Process -Name iPhoneMirror -ErrorAction SilentlyContinue)
if ($running.Count -gt 1) { throw 'Close the extra iPhoneMirror instances and rerun.' }
if ($running.Count -eq 1) {
    $activePath = $running[0].Path
    if (-not $activePath -or -not (Test-Path -LiteralPath (Join-Path (Split-Path -Parent $activePath) 'mcp-runtime.json'))) {
        throw 'Exit the running iPhoneMirror from its tray menu and rerun to prepare the MCP runtime.'
    }
    if ($MirrorPath -and (Resolve-Path -LiteralPath $MirrorPath).Path -ne $activePath) {
        throw 'Exit the other running iPhoneMirror instance before switching runtimes.'
    }
    $MirrorPath = $activePath
}
if (-not $MirrorPath) {
    $runtimeRoot = Join-Path $DependencyDirectory "runtime-$runtimeVersion"
    $MirrorPath = Join-Path $runtimeRoot 'app\iPhoneMirror.exe'
    if (-not (Test-Path -LiteralPath $MirrorPath)) {
        $runtimeUri = "https://github.com/RayrenSX/iPhone-mcp/releases/download/runtime-$runtimeVersion/$runtimeName"
        $archive = Get-VerifiedDownload $runtimeUri $runtimeName '60A8640B39274810CE94DFE868275A259E080EE7C06931A498928EB3C2F6D99D'
        Expand-Archive -LiteralPath $archive -DestinationPath $runtimeRoot -Force
    }
}
$MirrorPath = (Resolve-Path -LiteralPath $MirrorPath).Path
$runtimeDirectory = Split-Path -Parent $MirrorPath
$markerPath = Join-Path $runtimeDirectory 'mcp-runtime.json'
if (-not (Test-Path -LiteralPath $markerPath)) { throw 'Choose an iPhoneMirror MCP-compatible runtime.' }
$marker = Get-Content -LiteralPath $markerPath -Raw | ConvertFrom-Json
if ($marker.managementVersion -ne 1) { throw 'This iPhoneMirror runtime lacks the required MCP management API.' }

# The v0.2.1 archive omits native files required by its own startup check.
$requiredFiles = @(
    'iPhoneMirror.Core.dll', 'iPhoneMirror.UsbConfigurationSwitch.exe',
    'libusb-1.0.dll', 'libusb0.dll', 'msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll'
)
$missing = @($requiredFiles | Where-Object { -not (Test-Path -LiteralPath (Join-Path $runtimeDirectory $_)) })
if ($missing.Count) {
    $userInstall = Join-Path $env:LOCALAPPDATA 'Programs\iPhoneMirror'
    $programInstall = Join-Path $env:ProgramFiles 'iPhoneMirror'
    $baseInstall = @($userInstall, $programInstall) | Where-Object {
        $candidate = Join-Path $_ 'iPhoneMirror.exe'
        (Test-Path -LiteralPath $candidate) -and
        ((Get-Item -LiteralPath $candidate).VersionInfo.ProductVersion -like '1.8.5-pre6*')
    } | Select-Object -First 1
    if (-not $baseInstall) {
        $otherInstall = @($userInstall, $programInstall) | Where-Object {
            Test-Path -LiteralPath (Join-Path $_ 'iPhoneMirror.exe')
        } | Select-Object -First 1
        $release = "https://github.com/RayrenSX/iPhoneMirror/releases/download/$baselineVersion"
        if ($otherInstall) {
            $portableName = "iPhoneMirror-$baselineVersion-win-x64.zip"
            $archive = Get-VerifiedDownload "$release/$portableName" $portableName 'D68BBA0EFB2936089A10A68B7192466BF0A03F9F18C82C668831A332820F486D'
            $baselineFolder = Join-Path $DependencyDirectory "native-$baselineVersion"
            Expand-Archive -LiteralPath $archive -DestinationPath $baselineFolder -Force
            $component = Get-ChildItem -LiteralPath $baselineFolder -Filter 'iPhoneMirror.Core.dll' -File -Recurse |
                Select-Object -First 1
            if (-not $component) { throw 'The verified portable archive is missing iPhoneMirror.Core.dll.' }
            $baseInstall = $component.DirectoryName
        } else {
            $installer = Get-VerifiedDownload "$release/$setupName" $setupName '820EB23551DA475E4013C84233D8D2A523C924C263FB2F8D6BFBF93AC55C5290'
            Write-Host 'Installing official iPhoneMirror components for the current Windows user.'
            $setupProcess = Start-Process -FilePath $installer -ArgumentList @('/CURRENTUSER', '/VERYSILENT', '/NORESTART', '/NOICONS') -WindowStyle Hidden -Wait -PassThru
            if ($setupProcess.ExitCode -ne 0) { throw "iPhoneMirror setup failed (exit $($setupProcess.ExitCode))." }
            $baseInstall = $userInstall
        }
    }
    foreach ($file in $missing) {
        Copy-Item -LiteralPath (Join-Path $baseInstall $file) -Destination $runtimeDirectory -ErrorAction Stop
    }
}

$bootstrapOptions = @{ CaptureMode = 'continuous'; MirrorPath = $MirrorPath; SkipDoctor = $true }
if ($Python) { $bootstrapOptions.Python = $Python }
if ($SkipDrivers -or $ConfigureOnly) { $bootstrapOptions.SkipDrivers = $true }

$previousPath = $env:Path
try {
    $env:Path = "$(Split-Path -Parent $codexPath)$([IO.Path]::PathSeparator)$previousPath"
    & $bootstrap @bootstrapOptions
} finally {
    $env:Path = $previousPath
}

if (-not $ConfigureOnly) {
    $venv = Join-Path $source '.venv\Scripts\python.exe'
    & $venv (Join-Path $source 'scripts\start-runtime.py') --mode continuous
    if ($LASTEXITCODE -ne 0) {
        throw 'MCP is registered. Complete the device action reported above, then rerun the installer.'
    }
    # Capture may report ready before the first decoded frame is available.
    $verified = $false
    foreach ($delay in @(0, 2, 4)) {
        if ($delay) { Start-Sleep -Seconds $delay }
        & $venv (Join-Path $source 'scripts\doctor.py')
        if ($LASTEXITCODE -eq 0) {
            $verified = $true
            break
        }
    }
    if (-not $verified) {
        throw 'MCP is registered. Keep the iPhone connected and unlocked, then rerun the installer to verify capture.'
    }
}

Write-Host 'Open a new Codex chat to load iphone-mcp. Connect, unlock, and trust your iPhone if prompted.'
