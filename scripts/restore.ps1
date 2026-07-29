param(
    [string]$InputPath = "backups/ai-dev-os-backup.sql"
)

$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

if (-not (Test-Path $InputPath)) {
    throw "Backup file not found: $InputPath"
}

Get-Content -Raw $InputPath | docker compose exec -T postgres psql -U ai_dev_os -d ai_dev_os
Write-Host "Backup restored from $InputPath"
