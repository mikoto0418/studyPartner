$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$RunDir = Join-Path $Root ".codex-run"
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

function Read-LocalEnv {
    $path = Join-Path $Root "local.tunnel.env"
    if (-not (Test-Path $path)) {
        throw "Missing local.tunnel.env. Copy local.tunnel.env.example to local.tunnel.env and fill your tunnel config."
    }
    $envMap = @{}
    Get-Content -Path $path -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or $line -notmatch "=") { return }
        $parts = $line.Split("=", 2)
        $envMap[$parts[0].Trim()] = [Environment]::ExpandEnvironmentVariables($parts[1].Trim())
    }
    return $envMap
}

function Get-TunnelId([string]$ConfigPath) {
    $raw = Get-Content -Path $ConfigPath -Raw -Encoding UTF8
    if ($raw -match "tunnel:\s*([0-9a-fA-F-]+)") {
        return $matches[1]
    }
    return $null
}

$LocalEnv = Read-LocalEnv
$ConfigPath = $LocalEnv["CLOUDFLARED_CONFIG"]
if (-not $ConfigPath) { throw "CLOUDFLARED_CONFIG is required in local.tunnel.env" }
if (-not (Test-Path $ConfigPath)) { throw "Cloudflared config not found: $ConfigPath" }

$FrontendPort = $LocalEnv["FRONTEND_PORT"]
if (-not $FrontendPort) { $FrontendPort = "5173" }
$frontendListening = Get-NetTCPConnection -LocalPort ([int]$FrontendPort) -State Listen -ErrorAction SilentlyContinue
if (-not $frontendListening) {
    Write-Host "[INFO] Frontend is not running. Starting local dev services first..."
    & (Join-Path $PSScriptRoot "start-dev.ps1")
}

$Cloudflared = $LocalEnv["CLOUDFLARED_EXE"]
if (-not $Cloudflared) { $Cloudflared = "cloudflared" }

$TunnelId = Get-TunnelId $ConfigPath
$existing = Get-CimInstance Win32_Process -Filter "name='cloudflared.exe'" | Where-Object {
    $_.CommandLine -like "*$ConfigPath*" -or ($TunnelId -and $_.CommandLine -like "*$TunnelId*")
}
if ($existing) {
    $pids = ($existing | Select-Object -ExpandProperty ProcessId) -join ", "
    Write-Host "[OK] Tunnel already running. PID(s): $pids"
    return
}

$out = Join-Path $RunDir "tunnel.out.log"
$err = Join-Path $RunDir "tunnel.err.log"
$args = "tunnel --protocol http2 --config `"$ConfigPath`" run"
$proc = Start-Process -FilePath $Cloudflared `
    -ArgumentList $args `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $out `
    -RedirectStandardError $err `
    -PassThru
Set-Content -Path (Join-Path $RunDir "tunnel.pid") -Value $proc.Id -Encoding ASCII

Write-Host "[OK] Tunnel started. PID: $($proc.Id)"
if ($LocalEnv["TUNNEL_HOSTNAME"]) {
    Write-Host "Public URL: https://$($LocalEnv["TUNNEL_HOSTNAME"])"
}
