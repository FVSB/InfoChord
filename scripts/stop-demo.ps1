$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    docker compose down --timeout 20
    if ($LASTEXITCODE -ne 0) { throw 'Could not stop the demo.' }
    Write-Host 'Demo stopped. Database volumes were preserved.'
} finally { Pop-Location }
