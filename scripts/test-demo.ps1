$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    # Python 3.11+ on the host orchestrates Docker; dependencies stay in the image.
    python scripts/check-demo.py
    if ($LASTEXITCODE -ne 0) { throw 'Integration gate failed.' }
} finally { Pop-Location }
