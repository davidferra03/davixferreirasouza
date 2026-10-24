$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv\Scripts\python.exe")) {
  py -3.11 -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e ".[windows]"
& .\.venv\Scripts\python.exe -m playwright install chromium
& .\.venv\Scripts\instagram-automacao.exe init
$Dashboard = Join-Path $PSScriptRoot ".venv\Scripts\instagram-automacao.exe"
Start-Process -FilePath $Dashboard -ArgumentList @("dashboard") -WorkingDirectory $PSScriptRoot
Write-Host "Ambiente preparado. Painel: http://127.0.0.1:8765"
Write-Host "O terminal está livre para iniciar o Codex nesta pasta."
