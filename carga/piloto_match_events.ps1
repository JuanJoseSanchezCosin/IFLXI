# IFLXI — Runbook piloto MATCH + MATCH_EVENT
# Ejecutar SOLO cuando fill_leagues haya terminado (Pendientes squads ~0).
# Uso:
#   .\piloto_match_events.ps1 -DryRunOnly
#   .\piloto_match_events.ps1 -ApplyFixtures
#   .\piloto_match_events.ps1 -ApplyEvents
#   .\piloto_match_events.ps1 -Validate

param(
    [string]$League = "laliga",
    [int]$Season = 2025,
    [int]$Limit = 5,
    [switch]$DryRunOnly,
    [switch]$ApplyFixtures,
    [switch]$ApplyEvents,
    [switch]$Validate,
    [switch]$BackupMaps
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Assert-Env {
    if (-not $env:API_FOOTBALL_KEY) { throw "Falta API_FOOTBALL_KEY" }
    if (-not $env:PGPASSWORD) { throw "Falta PGPASSWORD" }
    if (-not $env:PGDATABASE) { $env:PGDATABASE = "iflxi" }
}

# Events = ~1 req/partido; deja margen sobre Limit
$MaxRequests = [Math]::Max(80, $Limit + 40)

Write-Host "=== IFLXI piloto MATCH/EVENT ===" -ForegroundColor Cyan
Write-Host "League=$League Season=$Season Limit=$Limit MaxRequests=$MaxRequests"
Write-Host "Asegurate de que fill_leagues NO esta escribiendo mapas."

if ($BackupMaps) {
    $ts = Get-Date -Format "yyyyMMdd_HHmmss"
    Copy-Item ".api_football_map.json" ".api_football_map.json.bak_$ts"
    Copy-Item ".import_map.json" ".import_map.json.bak_$ts"
    Write-Host "Backup mapas: *.bak_$ts"
}

if ($DryRunOnly) {
    Assert-Env
    Write-Host "`n--- fixtures dry-run (no escribe) ---"
    py api_football_import.py --league $League --season $Season --dry-run --with-fixtures --limit $Limit --max-requests $MaxRequests
    Write-Host "`n--- events dry-run (requiere MATCH ya cargados; si fallan, ApplyFixtures antes) ---"
    py api_football_import_events.py --league $League --season $Season --limit $Limit --dry-run --max-requests $MaxRequests
    exit 0
}

if ($ApplyFixtures) {
    Assert-Env
    Write-Host "`n--- APPLY fixtures (MATCH) ---"
    py api_football_import.py --league $League --season $Season --apply --with-fixtures --limit $Limit --max-requests $MaxRequests
}

if ($ApplyEvents) {
    Assert-Env
    Write-Host "`n--- events dry-run previo ---"
    py api_football_import_events.py --league $League --season $Season --limit $Limit --dry-run --max-requests $MaxRequests
    Write-Host "`n--- APPLY events ---"
    py api_football_import_events.py --league $League --season $Season --limit $Limit --apply --max-requests $MaxRequests
}

if ($Validate) {
    $psql = "C:\Program Files\PostgreSQL\18\bin\psql.exe"
    if (-not (Test-Path $psql)) { throw "No encuentro psql en $psql" }
    & $psql -d iflxi -f "..\sql\IFLXI-validaciones-match-event.sql"
}

if (-not ($DryRunOnly -or $ApplyFixtures -or $ApplyEvents -or $Validate -or $BackupMaps)) {
    Write-Host @"

Sin flags: no se ejecuta nada (seguro).

Cuando el fill termine, orden recomendado:

  1) .\piloto_match_events.ps1 -BackupMaps
  2) .\piloto_match_events.ps1 -ApplyFixtures
  3) .\piloto_match_events.ps1 -ApplyEvents
  4) .\piloto_match_events.ps1 -Validate

O solo dry-run de events (si MATCH ya existe):

  .\piloto_match_events.ps1 -DryRunOnly

"@
}
