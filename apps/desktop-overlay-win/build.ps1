<#
.SYNOPSIS
    Builds Researchly for Windows (the overlay client) from source.

.DESCRIPTION
    Runs the core tests, then publishes the app for 64-bit Windows into
    .\publish\win-x64\. The result needs the .NET 8 Desktop Runtime (the SDK
    includes it). The build is unsigned: see README.md for the SmartScreen note.

.PARAMETER SingleFile
    Publish one Researchly.Overlay.exe (plus its rules folder) instead of a folder of DLLs.

.PARAMETER SkipTests
    Skip the core tests (not recommended).

.PARAMETER Configuration
    Release (default) or Debug.

.PARAMETER Run
    Start the app after building.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\build.ps1
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\build.ps1 -SingleFile -Run
#>
[CmdletBinding()]
param(
    [switch]$SingleFile,
    [switch]$SkipTests,
    [ValidateSet('Release', 'Debug')]
    [string]$Configuration = 'Release',
    [switch]$Run
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

function Fail([string]$message) {
    Write-Host ""
    Write-Host "Build stopped: $message" -ForegroundColor Red
    exit 1
}

# 1. The .NET SDK (8 or later; the app targets .NET 8).
if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
    Fail ".NET SDK not found. Install the .NET 8 SDK from https://dotnet.microsoft.com/download/dotnet/8.0, then open a new PowerShell window."
}
$sdks = & dotnet --list-sdks
$hasSdk = $false
foreach ($line in $sdks) {
    if ($line -match '^(\d+)\.') { if ([int]$Matches[1] -ge 8) { $hasSdk = $true } }
}
if (-not $hasSdk) {
    Fail "A .NET SDK of version 8 or later is needed (found: $($sdks -join '; ')). Install it from https://dotnet.microsoft.com/download/dotnet/8.0."
}

# 2. The shared rules (packages\desktop-rules) must be present: they are part of the repository.
$rules = Join-Path $PSScriptRoot '..\..\packages\desktop-rules'
foreach ($file in @('fields.json', 'apps-windows.json')) {
    if (-not (Test-Path (Join-Path $rules $file))) {
        Fail "packages\desktop-rules\$file is missing. Download or clone the whole repository, not only this folder."
    }
}

# 3. Core tests (platform-neutral logic: text diff, UTF-16 ranges, gate, states, engine client).
if (-not $SkipTests) {
    Write-Host "Running the core tests..." -ForegroundColor Cyan
    & dotnet test 'tests\Researchly.Overlay.Core.Tests\Researchly.Overlay.Core.Tests.csproj' -c $Configuration --nologo
    if ($LASTEXITCODE -ne 0) { Fail "core tests failed (see above)." }
}

# 4. Publish the app.
$out = Join-Path $PSScriptRoot 'publish\win-x64'
if (Test-Path $out) { Remove-Item -Recurse -Force $out }
$publishArgs = @(
    'publish', 'src\Researchly.Overlay\Researchly.Overlay.csproj',
    '-c', $Configuration,
    '-r', 'win-x64',
    '--self-contained', 'false',
    '-o', $out,
    '--nologo'
)
if ($SingleFile) { $publishArgs += '-p:PublishSingleFile=true' }
Write-Host "Publishing to $out ..." -ForegroundColor Cyan
& dotnet @publishArgs
if ($LASTEXITCODE -ne 0) { Fail "publish failed (see above)." }

$exe = Join-Path $out 'Researchly.Overlay.exe'
if (-not (Test-Path $exe)) { Fail "the build finished but $exe is missing." }
if (-not (Test-Path (Join-Path $out 'rules\fields.json'))) { Fail "the rules folder was not copied next to the program." }

Write-Host ""
Write-Host "Built: $exe" -ForegroundColor Green
Write-Host "Run it, then look for the Researchly icon in the notification area (you may need the ^ arrow)."

if ($Run) { Start-Process -FilePath $exe }
