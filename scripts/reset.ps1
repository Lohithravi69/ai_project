param(
    [switch]$KeepData
)

$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

docker compose down --volumes --remove-orphans

if (-not $KeepData) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue .\vector_store\chroma
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue .\logs
}
