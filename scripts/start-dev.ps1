$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$RunDir = Join-Path $Root ".codex-run"
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

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

function Test-PortListening([int]$Port) {
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return [bool]$conn
}

function Wait-Port([int]$Port, [string]$Name) {
    for ($i = 0; $i -lt 40; $i++) {
        if (Test-PortListening $Port) {
            Write-Host "[OK] $Name is listening on port $Port"
            return
        }
        Start-Sleep -Milliseconds 500
    }
    throw "$Name did not start on port $Port"
}

function Resolve-CommandPath([string]$Name, [string]$Fallback) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $Fallback
}

$LocalEnv = Read-LocalEnv
$FrontendPortValue = $LocalEnv["FRONTEND_PORT"]
if (-not $FrontendPortValue) { $FrontendPortValue = "5173" }
$BackendPortValue = $LocalEnv["BACKEND_PORT"]
if (-not $BackendPortValue) { $BackendPortValue = "8001" }
$FrontendPort = [int]$FrontendPortValue
$BackendPort = [int]$BackendPortValue
$TunnelHostname = $LocalEnv["TUNNEL_HOSTNAME"]

Write-Host "== AI Study Partner local dev startup =="

$ServerEnv = Join-Path $Root "server\.env"
$ServerEnvExample = Join-Path $Root "server\.env.example"
if (-not (Test-Path $ServerEnv) -and (Test-Path $ServerEnvExample)) {
    Copy-Item -Path $ServerEnvExample -Destination $ServerEnv
    Write-Host "[INFO] Created server\.env from server\.env.example."
}

if (-not (Test-PortListening 15432) -or -not (Test-PortListening 6379) -or -not (Test-PortListening 6333) -or -not (Test-PortListening 9000)) {
    Write-Host "[1/4] Starting infrastructure containers..."
    Push-Location $Root
    docker compose up -d postgres redis minio qdrant
    Pop-Location
} else {
    Write-Host "[1/4] Infrastructure ports are already listening."
}

Write-Host "[2/4] Starting backend..."
if (Test-PortListening $BackendPort) {
    Write-Host "[OK] Backend already listening on port $BackendPort"
} else {
    $uvicorn = Resolve-CommandPath "uvicorn.exe" "uvicorn"
    $backendOut = Join-Path $RunDir "backend.out.log"
    $backendErr = Join-Path $RunDir "backend.err.log"
    $backend = Start-Process -FilePath $uvicorn `
        -ArgumentList "app.main:app --host 127.0.0.1 --port $BackendPort" `
        -WorkingDirectory (Join-Path $Root "server") `
        -WindowStyle Hidden `
        -RedirectStandardOutput $backendOut `
        -RedirectStandardError $backendErr `
        -PassThru
    Set-Content -Path (Join-Path $RunDir "backend.pid") -Value $backend.Id -Encoding ASCII
    Wait-Port $BackendPort "Backend"
}

Write-Host "[3/4] Starting frontend..."
if (Test-PortListening $FrontendPort) {
    Write-Host "[OK] Frontend already listening on port $FrontendPort"
} else {
    $npm = Resolve-CommandPath "npm.cmd" "npm"
    $frontendOut = Join-Path $RunDir "frontend.out.log"
    $frontendErr = Join-Path $RunDir "frontend.err.log"
    $viteArgs = "run dev -- --host 127.0.0.1 --port $FrontendPort"
    $env:VITE_API_PROXY_TARGET = "http://127.0.0.1:$BackendPort"
    if ($TunnelHostname) {
        $env:VITE_ALLOWED_HOSTS = $TunnelHostname
    }
    $frontend = Start-Process -FilePath $npm `
        -ArgumentList $viteArgs `
        -WorkingDirectory (Join-Path $Root "web") `
        -WindowStyle Hidden `
        -RedirectStandardOutput $frontendOut `
        -RedirectStandardError $frontendErr `
        -PassThru
    Set-Content -Path (Join-Path $RunDir "frontend.pid") -Value $frontend.Id -Encoding ASCII
    Wait-Port $FrontendPort "Frontend"
}

Write-Host "[4/4] Local dev services are ready."
Write-Host "Frontend: http://127.0.0.1:$FrontendPort"
Write-Host "Backend:  http://127.0.0.1:$BackendPort/api/health"
if ($TunnelHostname) {
    Write-Host "Tunnel host configured for Vite: https://$TunnelHostname"
}
