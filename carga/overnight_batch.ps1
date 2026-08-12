# IFLXI overnight wrapper -> overnight_batch.py (ASCII only; avoids PS 5.1 UTF8 bugs)
# Usage:
#   cd C:\Users\juanj\OneDrive\Escritorio\IFLXI\carga
#   .\overnight_batch.ps1
#   .\overnight_batch.ps1 -SkipFixtures
param(
    [int]$Season = 2025,
    [int]$MinRemaining = 400,
    [int]$MaxRequestsPerLeague = 700,
    [switch]$SkipFixtures,
    [string]$Only = ""
)

$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

if (-not $env:API_FOOTBALL_KEY) { throw "Falta API_FOOTBALL_KEY" }
if (-not $env:PGPASSWORD) { throw "Falta PGPASSWORD" }
if (-not $env:PGDATABASE) { $env:PGDATABASE = "iflxi" }

$pyArgs = @(
    "overnight_batch.py",
    "--season", "$Season",
    "--min-remaining", "$MinRemaining",
    "--max-requests-per-league", "$MaxRequestsPerLeague"
)
if ($SkipFixtures) { $pyArgs += "--skip-fixtures" }
if ($Only) { $pyArgs += @("--only", $Only) }

Write-Host "Launching: py $($pyArgs -join ' ')"
& py @pyArgs
exit $LASTEXITCODE
