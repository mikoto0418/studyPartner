param([string]$Output = '1022-roster.csv')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$rows = & docker compose --env-file .env.interview -f docker-compose.interview.yml exec -T backend python -m app.interview_1022 --roster-only --export -
if ($LASTEXITCODE -ne 0) { throw 'Roster export failed.' }
[IO.File]::WriteAllLines([IO.Path]::GetFullPath($Output), [string[]]$rows, [Text.UTF8Encoding]::new($true))
Write-Host "Exported: $Output"
