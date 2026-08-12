$ErrorActionPreference = "Continue"
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

$targets = @(
  @{ Path="C:\Users\juanj\OneDrive\Escritorio\IFLXI"; Repo="IFLXI" },
  @{ Path="C:\Users\juanj\OneDrive\Escritorio\pintorsagunto"; Repo="pintorsagunto" },
  @{ Path="C:\Users\juanj\OneDrive\Escritorio\albanilsagunto-work"; Repo="albanilsagunto" },
  @{ Path="C:\Users\juanj\OneDrive\Escritorio\ComeCerca"; Repo="ComeCerca" },
  @{ Path="C:\Users\juanj\OneDrive\Escritorio\electricistasagunto"; Repo="electricistasagunto" },
  @{ Path="C:\Users\juanj\OneDrive\Escritorio\Multiservicios Sagunto"; Repo="multiservicios-sagunto" },
  @{ Path="C:\Users\juanj\OneDrive\Escritorio\reformabanosagunto-work"; Repo="reformabanosagunto" },
  @{ Path="C:\Users\juanj\OneDrive\Escritorio\reformacocinasagunto-work"; Repo="reformacocinasagunto" },
  @{ Path="C:\Users\juanj\OneDrive\Escritorio\fontanero-sagunto-work"; Repo="fontanero-sagunto" },
  @{ Path="C:\Users\juanj\OneDrive\Escritorio\limpiezasagunto-work"; Repo="limpiezasagunto" },
  @{ Path="C:\Users\juanj\OneDrive\Escritorio\gestionvacacionalsagunto-work"; Repo="gestionvacacionalsagunto" },
  @{ Path="C:\Users\juanj\OneDrive\Escritorio\oficioactivo-work"; Repo="oficioactivo" }
)

function Ensure-Commit($path, $repo) {
  Push-Location $path
  try {
    if (-not (Test-Path .git)) { git init -b main | Out-Null }
    if (-not (Test-Path .gitignore)) {
      @(
        ".env",
        ".env.*",
        "*.pem",
        "node_modules/",
        ".DS_Store",
        "Thumbs.db",
        "__pycache__/",
        ".venv/",
        "site-info.json",
        "*-tmp.json",
        "_tmp_*"
      ) | Set-Content .gitignore -Encoding UTF8
    }
    $head = git rev-parse HEAD 2>$null
    if (-not $head) {
      git add -A
      git commit --trailer "Co-authored-by: Cursor <cursoragent@cursor.com>" -m "Initial snapshot $repo"
    }
  } finally { Pop-Location }
}

Write-Host "Auth check..."
gh auth status
if ($LASTEXITCODE -ne 0) { throw "Run: gh auth login" }

foreach ($t in $targets) {
  if (-not (Test-Path $t.Path)) { Write-Host "SKIP missing $($t.Repo)"; continue }
  Ensure-Commit $t.Path $t.Repo
  Push-Location $t.Path
  try {
    $origin = git remote get-url origin 2>$null
    if ($origin) {
      Write-Host "OK already $($t.Repo) -> $origin"
      continue
    }
    Write-Host "CREATE+PUSH $($t.Repo) ..."
    gh repo create $t.Repo --private --source=. --remote=origin --push
    if ($LASTEXITCODE -eq 0) { Write-Host "DONE $($t.Repo)" }
    else { Write-Host "FAIL $($t.Repo) exit=$LASTEXITCODE" }
  } finally { Pop-Location }
}

Write-Host "===== SUMMARY ====="
foreach ($t in $targets) {
  if (-not (Test-Path $t.Path)) { continue }
  Push-Location $t.Path
  $o = git remote get-url origin 2>$null
  Write-Host "$($t.Repo): $(if($o){$o}else{'NO ORIGIN'})"
  Pop-Location
}
