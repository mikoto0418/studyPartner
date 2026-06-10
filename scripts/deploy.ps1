$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $Root
try {
    Write-Host "== AI Study Partner Docker deployment =="
    if (-not (Test-Path ".env")) {
        Copy-Item ".env.example" ".env"
        Write-Host "[WARN] Created .env from .env.example. Please fill production secrets before exposing the service."
    }

    docker compose -f docker-compose.prod.yml down --remove-orphans
    docker compose -f docker-compose.prod.yml build
    docker compose -f docker-compose.prod.yml up -d

    Write-Host "[WAIT] PostgreSQL health check..."
    for ($i = 0; $i -lt 60; $i++) {
        docker compose -f docker-compose.prod.yml exec -T postgres pg_isready -U postgres -d studypartner *> $null
        if ($LASTEXITCODE -eq 0) { break }
        Start-Sleep -Seconds 3
    }
    if ($LASTEXITCODE -ne 0) { throw "PostgreSQL did not become ready." }

    docker compose -f docker-compose.prod.yml exec -T backend alembic upgrade head
    docker compose -f docker-compose.prod.yml exec -T backend python -m app.seed
    Write-Host "[OK] Deployment finished: http://localhost"
}
finally {
    Pop-Location
}
