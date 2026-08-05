<#
.SYNOPSIS
    FleetPulse database rollover tool - backup, restore, verify.

.DESCRIPTION
    Handles the monthly Render free-PostgreSQL 30-day rollover:
      backup -> pg_dump -Fc into backups\ (verifies the dump)
      restore -> pg_restore into a brand-new Render Postgres (verifies with row counts)
      counts -> per-table row counts of any live database
      guide -> prints the full rollover runbook

    Credentials are passed as -DbUrl each run (the URL changes every rollover),
    so this file contains no secrets and is safe to commit.

    Backup policy: keeps every dump (-Keep N prunes to the N newest if given).

    Prerequisites: PostgreSQL client tools installed locally
    (auto-detected across "C:\Program Files\PostgreSQL\<ver>\bin", newest wins;
    falls back to PATH).

.EXAMPLE
    .\rollover.ps1 -Action backup -DbUrl "postgresql://user:pass@host/db"
    .\rollover.ps1 -Action restore -DbUrl "postgresql://user:pass@newhost/db"
    .\rollover.ps1 -Action counts -DbUrl "postgresql://user:pass@host/db"
    .\rollover.ps1 -Action restore -DbUrl "..." -DumpFile "backups\fleetpulse-backup-20260805-080548.dump" -Force
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('backup', 'restore', 'counts', 'guide')]
    [string]$Action,

    [string]$DbUrl,

    [string]$BackupDir = 'backups',

    [string]$DumpFile,

    [int]$Keep = 0,

    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$script:pgRoot = 'C:\Program Files\PostgreSQL'

function Get-PgExe {
    param([string]$name)
    if (Test-Path -LiteralPath $script:pgRoot -ErrorAction SilentlyContinue) {
        $dirs = Get-ChildItem -LiteralPath $script:pgRoot -Directory -ErrorAction SilentlyContinue |
            Sort-Object { try { [version]$_.Name } catch { [version]'0.0' } } -Descending
        foreach ($d in $dirs) {
            $p = Join-Path $d.FullName "bin\$name.exe"
            if (Test-Path -LiteralPath $p) { return $p }
        }
    }
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "PostgreSQL client '$name' not found. Install the PostgreSQL client tools or add them to PATH."
}

function Get-PublicTableCount {
    param([string]$url)
    $psql = Get-PgExe 'psql'
    $out = & $psql $url -t -A -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"
    $val = ($out | Where-Object { $_ -match '^\d+$' } | Select-Object -First 1)
    if ($null -eq $val) { throw 'Could not read table count from target database.' }
    return [int]$val
}

function Get-TableCounts {
    param([string]$url)
    $psql = Get-PgExe 'psql'
    $build = @'
SELECT 'SELECT ' || quote_literal(t.table_name) || ' AS tbl, count(*) AS cnt FROM public.' || quote_ident(t.table_name) || ';'
FROM information_schema.tables t
WHERE t.table_schema = 'public' AND t.table_type = 'BASE TABLE';
'@
    $statements = (& $psql $url -t -A -c $build | Where-Object { $_ })
    if (-not $statements) {
        Write-Host '  (no tables in public schema)'
        return
    }
    & $psql $url -t -A -c ([string]::Join("`n", $statements))
}

function Get-DumpTableCount {
    param([string]$file)
    $restx = Get-PgExe 'pg_restore'
    $list = & $restx -l $file 2>$null
    return (($list | Select-String -Pattern 'TABLE DATA').Count)
}

function Invoke-PgBackup {
    param([string]$url, [string]$dir)
    if (-not $url) { throw 'backup requires -DbUrl (the current database external URL).' }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $file = Join-Path $dir ("fleetpulse-backup-{0}.dump" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
    $dumpx = Get-PgExe 'pg_dump'
    Write-Host "Dumping $url -> $file" -ForegroundColor Cyan
    & $dumpx $url -Fc -f $file
    if ($LASTEXITCODE -ne 0) { throw "pg_dump failed (exit $LASTEXITCODE)." }
    $size = (Get-Item -LiteralPath $file).Length
    $tableCount = Get-DumpTableCount $file
    Write-Host "Backup OK: $file" -ForegroundColor Green
    Write-Host "  Size: $([math]::Round($size / 1KB, 1)) KB   Tables with data: $tableCount"
    if ($Keep -gt 0) {
        $old = Get-ChildItem -LiteralPath $dir -Filter 'fleetpulse-backup-*.dump' -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending | Select-Object -Skip $Keep
        foreach ($o in $old) {
            Remove-Item -LiteralPath $o.FullName -Force
            Write-Host "  Pruned: $($o.Name)"
        }
    }
}

function Invoke-PgRestore {
    param([string]$url, [string]$file)
    if (-not $url) { throw 'restore requires -DbUrl (the NEW database external URL).' }
    if (-not $file) {
        $newest = Get-ChildItem -LiteralPath $BackupDir -Filter 'fleetpulse-backup-*.dump' -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending | Select-Object -First 1
        if (-not $newest) { throw "No dump found in '$BackupDir'. Pass -DumpFile explicitly." }
        $file = $newest.FullName
    }
    if (-not (Test-Path -LiteralPath $file)) { throw "Dump file not found: $file" }
    $existing = Get-PublicTableCount $url
    if ($existing -gt 0 -and -not $Force) {
        throw "Target database already has $existing table(s). Refusing to restore (could duplicate data). Use -Force to override."
    }
    $restx = Get-PgExe 'pg_restore'
    Write-Host "Restoring $file -> $url" -ForegroundColor Cyan
    & $restx --no-owner --no-privileges -d $url $file
    if ($LASTEXITCODE -ne 0) { throw "pg_restore failed (exit $LASTEXITCODE)." }
    Write-Host "Restore OK from $file" -ForegroundColor Green
    Write-Host 'Row counts after restore:' -ForegroundColor Cyan
    Get-TableCounts $url
}

function Show-Guide {
    Write-Host @'

FLEETPULSE 30-DAY ROLLOVER RUNBOOK
==================================
The app keeps running; free Render Postgres expires every 30 days and its
data is deleted. Use this tool to back up before expiry and restore onto a
new instance afterward.

1. BEFORE EXPIRY (safety net)
     .\rollover.ps1 -Action backup -DbUrl "<current external URL>"
   Do this weekly if possible, and certainly when Render shows the expiry
   banner. The dump lands in backups\.

2. AT EXPIRY - new database (Render dashboard)
     a. Delete the expiring PostgreSQL instance.
     b. New -> PostgreSQL (free, same region as web service).
     c. Wait until status = Available.
     d. Copy the new instance's External Database URL.

3. RESTORE the data
     .\rollover.ps1 -Action restore -DbUrl "<NEW external URL>"
   It refuses to restore into a DB that already has tables (use -Force to
   override). Verify the row counts it prints before continuing.

4. POINT THE APP AT THE NEW DATABASE (Render dashboard)
     a. Web service -> Environment -> edit DATABASE_URL in place.
     b. Paste the new instance's INTERNAL Database URL (host ends .internal).
     c. Save -> Manual Deploy -> Deploy latest commit.

5. VERIFY
     .\rollover.ps1 -Action counts -DbUrl "<new external URL>"
   Log in and spot-check Trucks, PM Schedules, and a truck's Service History.

6. CLEANUP
     Delete the old database if you kept it. Keep backups (each ~150 KB);
     nothing is pruned unless you pass -Keep N to backup.
'@
}

switch ($Action) {
    'backup'  { Invoke-PgBackup -url $DbUrl -dir $BackupDir }
    'restore' { Invoke-PgRestore -url $DbUrl -file $DumpFile }
    'counts'  {
        if (-not $DbUrl) { throw 'counts requires -DbUrl.' }
        Get-TableCounts $DbUrl
    }
    'guide'   { Show-Guide }
}