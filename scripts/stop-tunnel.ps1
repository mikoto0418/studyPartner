$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$RunDir = Join-Path $Root ".codex-run"
$EnvFile = Join-Path $Root "local.tunnel.env"

function Read-LocalEnv {
    $envMap = @{}
    if (Test-Path $EnvFile) {
        Get-Content -Path $EnvFile -Encoding UTF8 | ForEach-Object {
            $line = $_.Trim()
            if (-not $line -or $line.StartsWith("#") -or $line -notmatch "=") { return }
            $parts = $line.Split("=", 2)
            $envMap[$parts[0].Trim()] = [Environment]::ExpandEnvironmentVariables($parts[1].Trim())
        }
    }
    return $envMap
}

function Get-TunnelId([string]$ConfigPath) {
    if (-not $ConfigPath -or -not (Test-Path $ConfigPath)) { return $null }
    $raw = Get-Content -Path $ConfigPath -Raw -Encoding UTF8
    if ($raw -match "tunnel:\s*([0-9a-fA-F-]+)") {
        return $matches[1]
    }
    return $null
}

$LocalEnv = Read-LocalEnv
$ConfigPath = $LocalEnv["CLOUDFLARED_CONFIG"]
$TunnelId = Get-TunnelId $ConfigPath
$Targets = @()

$pidFile = Join-Path $RunDir "tunnel.pid"
if (Test-Path $pidFile) {
    $pidValue = (Get-Content $pidFile -Raw).Trim()
    if ($pidValue -match "^\d+$") {
        $proc = Get-Process -Id ([int]$pidValue) -ErrorAction SilentlyContinue
        if ($proc) { $Targets += $proc }
    }
}

$matched = Get-CimInstance Win32_Process -Filter "name='cloudflared.exe'" | Where-Object {
    ($ConfigPath -and $_.CommandLine -like "*$ConfigPath*") -or ($TunnelId -and $_.CommandLine -like "*$TunnelId*")
}
foreach ($item in $matched) {
    $proc = Get-Process -Id $item.ProcessId -ErrorAction SilentlyContinue
    if ($proc) { $Targets += $proc }
}

$Targets = $Targets | Sort-Object Id -Unique
if (-not $Targets) {
    Write-Host "[OK] No matching tunnel process is running."
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    return
}

foreach ($proc in $Targets) {
    Write-Host "[STOP] cloudflared pid $($proc.Id)"
    Stop-Process -Id $proc.Id -Force
}
Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
Write-Host "[OK] Tunnel stopped."
