# ============================================================
# start-dev.ps1 — Lance le backend ET le frontend en dev
# Usage: .\start-dev.ps1
# ============================================================

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   PM Assistant — Démarrage Dev Local     " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Vérifier que Docker tourne (pour Redmine, Redis, PostgreSQL)
Write-Host "[1/3] Verification Docker..." -ForegroundColor Yellow
$dockerRunning = docker ps 2>&1 | Select-String "redmine"
if ($dockerRunning) {
    Write-Host "      [OK] Redmine Docker detecte sur localhost:3000" -ForegroundColor Green
} else {
    Write-Host "      [WARNING] Redmine non detecte. Lance: docker-compose up -d redmine redmine-mysql db redis" -ForegroundColor Red
}

Write-Host ""
Write-Host "[2/3] Demarrage Backend FastAPI (localhost:8000)..." -ForegroundColor Yellow
# On lance uvicorn avec --host 0.0.0.0 pour écouter sur localhost ET 127.0.0.1
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$PSScriptRoot\backend'; ..\venv\Scripts\Activate.ps1; uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
)

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "[3/3] Demarrage Frontend Vite (localhost:5173)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$PSScriptRoot\frontend'; npm run dev"
)

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "   [OK] Tout est lance !                  " -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  - Frontend  : http://localhost:5173" -ForegroundColor White
Write-Host "  - Backend   : http://localhost:8000" -ForegroundColor White
Write-Host "  - Redmine   : http://localhost:3000" -ForegroundColor White
Write-Host "  - API Docs  : http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
