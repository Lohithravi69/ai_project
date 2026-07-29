param(
    [string]$OutputPath = "backups/ai-dev-os-backup.sql"
)

$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

$backupDir = Split-Path -Parent $OutputPath
if ($backupDir) {
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
}

docker compose exec -T postgres pg_dump -U ai_dev_os ai_dev_os | Set-Content -Encoding utf8 $OutputPath
Write-Host "Backup written to $OutputPath"
