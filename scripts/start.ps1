# Windows PowerShell 실행 스크립트: .\scripts\start.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}
& .venv\Scripts\python.exe -m pip install -q -r requirements.txt

$port = (Select-String -Path ".env" -Pattern "^PORT=(\d+)" | ForEach-Object { $_.Matches[0].Groups[1].Value })
if (-not $port) { $port = "8000" }
& .venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port $port
