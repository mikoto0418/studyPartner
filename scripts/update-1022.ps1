param([string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot), [string]$ProjectName = '', [string]$ComposeOverride = '')
$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$payload = Join-Path $PSScriptRoot 'payload'
if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot '.env.interview'))) {
    throw 'Put the update folder INSIDE the original project, and start the original deployment once first.'
}
Set-Location -LiteralPath $ProjectRoot
$compose = @('compose', '--env-file', (Join-Path $ProjectRoot '.env.interview'), '-f', 'docker-compose.interview.yml')
if ($ProjectName) { $compose += @('--project-name', $ProjectName) }
if ($ComposeOverride) { $compose += @('-f', (Resolve-Path -LiteralPath $ComposeOverride).Path) }
function Invoke-Docker {
    param([string[]]$DockerArgs)
    & docker @DockerArgs
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed: $($DockerArgs[0]) (exit $LASTEXITCODE)" }
}
function Invoke-Compose {
    param([string[]]$CommandArgs)
    Invoke-Docker -DockerArgs ($compose + $CommandArgs)
}
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($entry in $manifest.files) {
    $source = Join-Path $payload $entry.path
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) { throw "Damaged update file: $($entry.path)" }
    $dest = Join-Path $ProjectRoot $entry.path
    if (Test-Path -LiteralPath $dest) {
        $actual = (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $entry.sha256 -and $actual -ne $entry.previous_sha256) { throw "Locally edited file; refusing overwrite: $($entry.path)" }
    } elseif ($entry.previous_sha256) { throw "Original file missing: $($entry.path)" }
}
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $ProjectRoot ('update-backups\' + $stamp)
New-Item -ItemType Directory -Path $backup -Force | Out-Null
Write-Host 'Building the small overlay from existing local images. No download is required.'
Invoke-Docker -DockerArgs @('build', '--pull=false', '--network=none', '-f', (Join-Path $PSScriptRoot 'backend.Dockerfile'), '-t', 'studypartner-1022-backend:five-question', $payload)
Invoke-Docker -DockerArgs @('build', '--pull=false', '--network=none', '-f', (Join-Path $PSScriptRoot 'frontend.Dockerfile'), '-t', 'studypartner-1022-frontend:five-question', $payload)
# Mount the updater and data for a preflight using the currently running deployment's environment.
$moduleMount = $payload.Replace('\','/') + '/server/app/update_exam_1022.py:/code/app/update_exam_1022.py:ro'
$dataMount = $payload.Replace('\','/') + '/server/app/data/exam_1022.json:/code/app/data/exam_1022.json:ro'
$updateRun = @('run','--rm','--no-deps','--pull','never','-v',$moduleMount,'-v',$dataMount,'backend','python','-m','app.update_exam_1022')
Invoke-Compose -CommandArgs ($updateRun + @('--check'))
Write-Host 'Backing up database and original files before applying the update.'
Invoke-Compose -CommandArgs @('exec','-T','postgres','pg_dump','-U','postgres','-d','studypartner_1022','-Fc','-f',"/tmp/1022-$stamp.dump")
Invoke-Compose -CommandArgs @('cp',"postgres:/tmp/1022-$stamp.dump",(Join-Path $backup 'database.dump'))
Invoke-Docker -DockerArgs @('tag','studypartner-1022-backend:local',"studypartner-1022-backend:before-$stamp")
Invoke-Docker -DockerArgs @('tag','studypartner-1022-frontend:local',"studypartner-1022-frontend:before-$stamp")
foreach ($entry in $manifest.files) {
    $dest = Join-Path $ProjectRoot $entry.path
    if (Test-Path -LiteralPath $dest) {
        $saved = Join-Path $backup $entry.path
        New-Item -ItemType Directory -Path (Split-Path -Parent $saved) -Force | Out-Null
        Copy-Item -LiteralPath $dest -Destination $saved
    }
}
$stopped = $false
try {
    Invoke-Compose -CommandArgs @('stop','backend','worker','beat','frontend')
    $stopped = $true
    # Recheck under the DB transaction after stopping API and schedulers; then add exactly two rows.
    Invoke-Compose -CommandArgs $updateRun
    foreach ($entry in $manifest.files) {
        $dest = Join-Path $ProjectRoot $entry.path
        New-Item -ItemType Directory -Path (Split-Path -Parent $dest) -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $payload $entry.path) -Destination $dest -Force
    }
    Invoke-Docker -DockerArgs @('tag','studypartner-1022-backend:five-question','studypartner-1022-backend:local')
    Invoke-Docker -DockerArgs @('tag','studypartner-1022-frontend:five-question','studypartner-1022-frontend:local')
    [IO.File]::WriteAllText((Join-Path $ProjectRoot '.1022-five-question-updated'), $stamp)
    Invoke-Compose -CommandArgs @('up','-d','--no-build','--pull','never','backend','worker','beat','frontend')
    $stopped = $false
    Invoke-Compose -CommandArgs @('run','--rm','--no-deps','--pull','never','backend','python','-m','app.update_exam_1022','--check')
    Write-Host 'SUCCESS: 5 questions, 140 points. Original accounts, question IDs, timing and fullscreen options preserved.'
    Write-Host "Backup: $backup"
    Write-Host 'Refresh the teacher page and verify the five questions. Future starts: start-offline.bat (old image archive is skipped).'
} catch {
    if ($stopped) { & docker @compose up -d --no-build --pull never backend worker beat frontend }
    Write-Host "UPDATE FAILED. Backup: $backup. Read the error; do not reset or delete database volumes."
    throw
}
