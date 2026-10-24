$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    docker info --format '{{.OSType}}'
    if ($LASTEXITCODE -ne 0) { throw 'Docker is not available.' }
    if (-not (Test-Path -LiteralPath '.env')) {
        Copy-Item -LiteralPath '.env.example' -Destination '.env'
        Write-Host 'Created local .env. Configure your real embedding provider if defaults do not match.'
    }
    docker compose config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Invalid Compose configuration.' }
    docker compose build node1
    if ($LASTEXITCODE -ne 0) { throw 'Image build failed.' }
    docker compose run --rm --no-deps node1 python scripts/check-provider.py
    if ($LASTEXITCODE -ne 0) { throw 'Embedding provider is not ready. No cluster was started.' }
    docker compose up -d --wait --wait-timeout 300
    if ($LASTEXITCODE -ne 0) { throw 'Cluster did not become ready. Inspect docker compose ps and logs.' }
    Write-Host 'InfoChord: http://localhost:8501. Use only disposable sample documents.'
} finally { Pop-Location }
