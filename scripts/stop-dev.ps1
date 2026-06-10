$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$RunDir = Join-Path $Root ".codex-run"

function Read-LocalEnv {
    $path = Join-Path $Root "local.tunnel.env"
    $envMap = @{}
    if (Test-Path $path) {
        Get-Content -Path $path -Encoding UTF8 | ForEach-Object {
            $line = $_.Trim()
            if (-not $line -or $line.StartsWith("#") -or $line -notmatch "=") { return }
            $parts = $line.Split("=", 2)
            $envMap[$parts[0].Trim()] = $parts[1].Trim()
        }
    }
    return $envMap
}

function Stop-PidFile([string]$Name) {
    $pidFile = Join-Path $RunDir "$Name.pid"
    if (-not (Test-Path $pidFile)) {
        Write-Host "[SKIP] No $Name pid file."
        return
    }
    $pidValue = (Get-Content $pidFile -Raw).Trim()
    if ($pidValue -match "^\d+$") {
        $proc = Get-Process -Id ([int]$pidValue) -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "[STOP] $Name pid $pidValue"
            Stop-Process -Id ([int]$pidValue) -Force
        } else {
            Write-Host "[OK] $Name pid $pidValue is not running."
        }
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

function Stop-PortOwner([int]$Port, [string]$Name) {
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $connections) {
        Write-Host "[OK] No listener on $Name port $Port."
        return
    }
    $processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($processId in $processIds) {
        if (-not $processId) { continue }
        $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "[STOP] $Name listener pid $processId on port $Port"
            Stop-Process -Id $processId -Force
        }
    }
}

$LocalEnv = Read-LocalEnv
$FrontendPortValue = $LocalEnv["FRONTEND_PORT"]
if (-not $FrontendPortValue) { $FrontendPortValue = "5173" }
$BackendPortValue = $LocalEnv["BACKEND_PORT"]
if (-not $BackendPortValue) { $BackendPortValue = "8001" }
$FrontendPort = [int]$FrontendPortValue
$BackendPort = [int]$BackendPortValue

Write-Host "== AI Study Partner local dev shutdown =="
Stop-PidFile "frontend"
Stop-PidFile "backend"
Stop-PortOwner $FrontendPort "Frontend"
Stop-PortOwner $BackendPort "Backend"
Write-Host "Local frontend/backend stopped. Infrastructure containers are kept running."
Write-Host "To stop containers too, run: docker compose stop postgres redis minio qdrant"
