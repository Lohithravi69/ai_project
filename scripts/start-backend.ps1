param()

$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..\backend')
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
