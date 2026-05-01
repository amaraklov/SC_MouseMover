param(
    [string]$ExePath = "dist\\MouseDriftHUD.exe",
    [string]$CertPath = "signing\\code-signing.pfx",
    [string]$PasswordFile = "signing\\password.txt",
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

if (-not (Test-Path $ExePath)) {
    throw "EXE not found: $ExePath"
}

if (-not (Test-Path $CertPath)) {
    throw "Certificate not found: $CertPath"
}

if (-not (Test-Path $PasswordFile)) {
    throw "Password file not found: $PasswordFile"
}

$password = (Get-Content -Path $PasswordFile -Raw).Trim()
if ([string]::IsNullOrWhiteSpace($password)) {
    throw "Password file is empty: $PasswordFile"
}

# Locate signtool from common Windows SDK install locations.
$signtool = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin" -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending |
    Select-Object -First 1

if (-not $signtool) {
    throw "signtool.exe not found. Install Windows SDK."
}

Write-Host "Using SignTool:" $signtool.FullName
Write-Host "Signing:" (Resolve-Path $ExePath)

& $signtool.FullName sign /fd SHA256 /tr $TimestampUrl /td SHA256 /f $CertPath /p $password $ExePath
if ($LASTEXITCODE -ne 0) {
    throw "SignTool sign failed with exit code $LASTEXITCODE"
}

& $signtool.FullName verify /pa /v $ExePath
if ($LASTEXITCODE -ne 0) {
    throw "SignTool verify failed with exit code $LASTEXITCODE"
}

Write-Host "Done: EXE signed and verified."
