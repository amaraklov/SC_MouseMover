param(
    [string]$SpecPath = "MouseDriftHUD.spec",
    [string]$ExePath = "dist\\MouseDriftHUD.exe",
    [string]$CertPath = "signing\\code-signing.pfx",
    [string]$PasswordFile = "signing\\password.txt",
    [string]$TimestampUrl = "http://timestamp.digicert.com",
    [switch]$Clean,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

if ($Clean) {
    if (Test-Path "build") {
        Remove-Item -Recurse -Force "build"
    }
    if (Test-Path "dist") {
        Remove-Item -Recurse -Force "dist"
    }
}

if (-not $SkipBuild) {
    if (-not (Test-Path $SpecPath)) {
        throw "Spec file not found: $SpecPath"
    }

    Write-Host "Building EXE with PyInstaller..."
    python -m PyInstaller $SpecPath --noconfirm
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed with exit code $LASTEXITCODE"
    }
}

$signScript = Join-Path $repoRoot "sign-exe.ps1"
if (-not (Test-Path $signScript)) {
    throw "Signing script not found: $signScript"
}

Write-Host "Signing EXE..."
& $signScript -ExePath $ExePath -CertPath $CertPath -PasswordFile $PasswordFile -TimestampUrl $TimestampUrl
if ($LASTEXITCODE -ne 0) {
    throw "Signing step failed with exit code $LASTEXITCODE"
}

Write-Host "Done: build and sign complete."
