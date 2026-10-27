param([string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot), [string]$ProjectName = '', [string]$ComposeOverride = '')
$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot '.env.interview')) -or
    -not (Test-Path -LiteralPath (Join-Path $ProjectRoot '.1022-five-question-updated'))) {
    throw 'Apply the five-question update first. Put this editor-update folder INSIDE that project.'
}
Set-Location -LiteralPath $ProjectRoot
$payload = Join-Path $PSScriptRoot 'payload'
$compose = @('compose', '--env-file', (Join-Path $ProjectRoot '.env.interview'), '-f', 'docker-compose.interview.yml')
if ($ProjectName) { $compose += @('--project-name', $ProjectName) }
if ($ComposeOverride) { $compose += @('-f', (Resolve-Path -LiteralPath $ComposeOverride).Path) }
function Invoke-Docker {
    param([string[]]$DockerArgs)
    & docker @DockerArgs
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed (exit $LASTEXITCODE)." }
}
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($entry in $manifest.files) {
    $path = Join-Path $payload $entry.path
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) { throw "Damaged package file: $($entry.path)" }
    if ($entry.install) {
        $dest = Join-Path $ProjectRoot $entry.path
        if (Test-Path -LiteralPath $dest) {
            $hash = (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($hash -ne $entry.sha256 -and $hash -ne $entry.previous_sha256) { throw "Locally edited file; refusing overwrite: $($entry.path)" }
        } elseif ($entry.previous_sha256) { throw "Original file missing: $($entry.path)" }
    }
}
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $ProjectRoot ('update-backups\editor-' + $stamp)
New-Item -ItemType Directory -Path $backup -Force | Out-Null
Invoke-Docker -DockerArgs @('tag','studypartner-1022-frontend:local',"studypartner-1022-frontend:before-editor-$stamp")
foreach ($entry in $manifest.files | Where-Object { $_.install }) {
    $dest = Join-Path $ProjectRoot $entry.path
    if (Test-Path -LiteralPath $dest) {
        $saved = Join-Path $backup $entry.path
        New-Item -ItemType Directory -Path (Split-Path -Parent $saved) -Force | Out-Null
        Copy-Item -LiteralPath $dest -Destination $saved
    }
}
Write-Host 'Installing prebuilt editor assets from local files; no npm, downloads or database changes.'
Invoke-Docker -DockerArgs @('build','--pull=false','--network=none','-f',(Join-Path $PSScriptRoot 'frontend.Dockerfile'),'-t','studypartner-1022-frontend:editor',$payload)
Invoke-Docker -DockerArgs @('tag','studypartner-1022-frontend:editor','studypartner-1022-frontend:local')
try {
    Invoke-Docker -DockerArgs ($compose + @('up','-d','--no-deps','--no-build','--pull','never','frontend'))
} catch {
    & docker tag "studypartner-1022-frontend:before-editor-$stamp" studypartner-1022-frontend:local
    & docker @compose up -d --no-deps --no-build --pull never frontend
    throw
}
foreach ($entry in $manifest.files | Where-Object { $_.install }) {
    $dest = Join-Path $ProjectRoot $entry.path
    New-Item -ItemType Directory -Path (Split-Path -Parent $dest) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $payload $entry.path) -Destination $dest -Force
}
Write-Host 'SUCCESS: code indentation and bracket completion installed. Refresh the student page after answers show saved.'
Write-Host "Only frontend restarted. Backup: $backup"
