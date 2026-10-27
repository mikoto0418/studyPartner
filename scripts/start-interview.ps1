param([switch]$Offline)
$ErrorActionPreference = 'Stop'
$examTimezone = [TimeZoneInfo]::FindSystemTimeZoneById('China Standard Time')
$examHostNow = [TimeZoneInfo]::ConvertTimeFromUtc([DateTime]::UtcNow, $examTimezone)
Write-Host ('Host clock (Beijing): ' + $examHostNow.ToString('yyyy-MM-dd HH:mm:ss'))
Write-Host 'Exam: 2026-10-22 14:50 - 15:50 Beijing time. Check host clock before exam.'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$envPath = Join-Path $projectRoot '.env.interview'
if (-not (Test-Path -LiteralPath $envPath)) {
    $config = @(
        'INTERVIEW_PORT=8080'
        ('POSTGRES_PASSWORD=' + [guid]::NewGuid().ToString('N'))
        ('MINIO_SECRET_KEY=' + [guid]::NewGuid().ToString('N'))
        ('JWT_SECRET_KEY=' + [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N'))
        'SILICONFLOW_API_KEY='
    )
    [IO.File]::WriteAllLines($envPath, $config, [Text.UTF8Encoding]::new($false))
}
$compose = @('compose', '--env-file', $envPath, '-f', 'docker-compose.interview.yml')
function Invoke-Compose {
    param([string[]]$CommandArgs)
    & docker @compose @CommandArgs
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed (exit $LASTEXITCODE)." }
}
if (-not $Offline) {
    Invoke-Compose -CommandArgs @('build', 'backend', 'frontend', 'judge')
}
Invoke-Compose -CommandArgs @('up', '-d', '--wait', '--wait-timeout', '120', '--pull', $(if ($Offline) { 'never' } else { 'missing' }), 'postgres', 'redis', 'minio', 'qdrant', 'judge')
$examContainerTime = & docker @compose run --rm --no-deps --pull never backend python -c 'import time; print(int(time.time()))'
if ($LASTEXITCODE -ne 0) { throw 'Cannot read container system clock.' }
$examClockDrift = [Math]::Abs([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - [long]($examContainerTime | Select-Object -Last 1))
if ($examClockDrift -gt 10) { throw 'Docker clock differs from Windows by more than 10 seconds. Restart Docker Desktop and rerun.' }
Invoke-Compose -CommandArgs @('run', '--rm', '--no-deps', '--pull', 'never', 'backend', 'python', '-m', 'app.interview_1022', '--init-db')
Invoke-Compose -CommandArgs @('up', '-d', '--no-build', '--pull', 'never')
Write-Host 'Ready: http://localhost:8080 (or INTERVIEW_PORT in .env.interview).'
Write-Host 'LAN clients: http://<server-LAN-IP>:8080'
Write-Host 'Teachers: tea10221 / tea10222 / tea10223. Initial passwords equal usernames.'
