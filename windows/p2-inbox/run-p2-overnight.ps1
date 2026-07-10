# MedRack P2 overnight book ingest (Windows orchestrator)
# Policy: if one book fails, log it and continue to the next.
# Usage:
#   powershell -ExecutionPolicy Bypass -File C:\Medrack\p2-inbox\run-p2-overnight.ps1

$ErrorActionPreference = 'Continue'
$Root = $PSScriptRoot
$OrderFile = Join-Path $Root 'ORDER.md'
if (-not (Test-Path $OrderFile)) { $OrderFile = Join-Path $Root 'ORDER.txt' }
$DoneDir = Join-Path $Root 'done'
$FailDir = Join-Path $Root 'failed'
$ReportMd = Join-Path $Root 'p2-report.md'
$ReportJson = Join-Path $Root 'p2-report.json'
$LogFile = Join-Path $Root 'p2-run.log'
New-Item -ItemType Directory -Force -Path $DoneDir, $FailDir | Out-Null

$Api = 'http://192.168.29.82:8010/api/v1'
$Hybrid = $true
$UseMarker = $true
$Replace = $true

function Write-Log([string]$msg) {
    $line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

# Prevent Windows sleep during the run (best-effort)
try {
    & powercfg /change standby-timeout-ac 0 2>$null
    & powercfg /change hibernate-timeout-ac 0 2>$null
    Write-Log 'Sleep/hibernate timeouts set to 0 for AC power (best-effort)'
} catch {
    Write-Log 'Could not change powercfg (non-fatal)'
}

if (-not (Test-Path $OrderFile)) {
    Write-Log "ERROR: ORDER.md / ORDER.txt not found in $Root"
    exit 1
}

# Preflight via API
try {
    $pf = Invoke-RestMethod -Uri "$Api/system/preflight" -TimeoutSec 30
    Write-Log ("Preflight ok={0} checks={1}" -f $pf.ok, (($pf.checks | ConvertTo-Json -Compress)))
    if (-not $pf.ok) {
        Write-Log 'ERROR: system preflight failed — fix disk/OCR/model before overnight run'
        exit 1
    }
} catch {
    Write-Log "ERROR: preflight request failed: $_"
    exit 1
}

$jobs = @()
Get-Content $OrderFile -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#') -or $line.StartsWith('//')) { return }
    $parts = $line -split '\|'
    if ($parts.Count -lt 4) {
        Write-Log "SKIP bad ORDER line: $line"
        return
    }
    $jobs += [pscustomobject]@{
        Order    = $parts[0].Trim()
        Subject  = $parts[1].Trim().ToLower()
        Title    = $parts[2].Trim()
        Filename = $parts[3].Trim()
    }
}

Write-Log ("P2 start — {0} book(s), skip-on-fail, hybrid={1} marker={2}" -f $jobs.Count, $Hybrid, $UseMarker)

$results = @()
foreach ($j in ($jobs | Sort-Object { [int]($_.Order -replace '\D','0') })) {
    $entry = [ordered]@{
        order    = $j.Order
        subject  = $j.Subject
        title    = $j.Title
        filename = $j.Filename
        status   = 'pending'
        book_id  = $null
        chunks   = $null
        pages    = $null
        error    = $null
        verification_ok = $null
        started  = (Get-Date).ToString('o')
        finished = $null
    }
    $pdf = Join-Path $Root $j.Filename
    Write-Log ("=== [{0}] {1} ({2}) ===" -f $j.Order, $j.Title, $j.Filename)

    if (-not (Test-Path -LiteralPath $pdf)) {
        $entry.status = 'skipped_missing_file'
        $entry.error = "File not found: $pdf"
        Write-Log $entry.error
        $entry.finished = (Get-Date).ToString('o')
        $results += [pscustomobject]$entry
        continue
    }

    try {
        # Disk preflight each book (disk can fill mid-run)
        try {
            $pf2 = Invoke-RestMethod -Uri "$Api/system/preflight" -TimeoutSec 30
            if (-not $pf2.ok) { throw "preflight failed mid-run" }
        } catch {
            throw "preflight: $_"
        }

        $tmpOut = Join-Path $env:TEMP ("p2-upload-{0}.json" -f $j.Order)
        $code = & curl.exe -sS -X POST "$Api/library/books/upload" `
            -F "file=@$pdf;type=application/pdf" `
            -F "subject=$($j.Subject)" `
            -F "title=$($j.Title)" `
            -F "replace=$($Replace.ToString().ToLower())" `
            -F "hybrid_ocr=$($Hybrid.ToString().ToLower())" `
            -F "use_marker=$($UseMarker.ToString().ToLower())" `
            -o $tmpOut -w '%{http_code}'
        if ($code -ne '200' -and $code -ne '201') {
            throw "upload HTTP $code : $((Get-Content $tmpOut -Raw -ErrorAction SilentlyContinue))"
        }
        $handle = Get-Content $tmpOut -Raw | ConvertFrom-Json
        $jobId = $handle.job_id
        if (-not $jobId) { throw "no job_id in upload response" }
        Write-Log "job_id=$jobId — polling…"

        $deadline = (Get-Date).AddHours(10)
        $final = $null
        while ((Get-Date) -lt $deadline) {
            Start-Sleep -Seconds 8
            $st = Invoke-RestMethod -Uri "$Api/jobs/$jobId" -TimeoutSec 90
            $msg = if ($st.message) { $st.message } else { $st.status }
            Write-Log ("  {0}% {1} {2}" -f $st.percent, $st.status, $msg)
            if ($st.status -in @('done', 'error', 'cancelled')) {
                $final = $st
                break
            }
        }
        if (-not $final) { throw "timeout waiting for job $jobId" }
        if ($final.status -ne 'done') {
            throw ("job {0}: {1}" -f $final.status, $final.error)
        }

        $r = $final.result
        $entry.book_id = $r.book_id
        $entry.chunks = $r.chunks
        $entry.pages = $r.pages
        $v = $r.verification
        if ($v) {
            $entry.verification_ok = [bool]$v.ok
            if (-not $v.ok) { throw ("verification failed: {0}" -f $v.message) }
        } else {
            $v2 = Invoke-RestMethod -Uri "$Api/library/books/$($r.book_id)/verify" -TimeoutSec 180
            $entry.verification_ok = [bool]$v2.ok
            if (-not $v2.ok) { throw ("verification failed: {0}" -f $v2.message) }
        }

        $entry.status = 'ok'
        Write-Log ("OK book_id={0} pages={1} chunks={2}" -f $r.book_id, $r.pages, $r.chunks)
        try { Move-Item -LiteralPath $pdf -Destination (Join-Path $DoneDir $j.Filename) -Force } catch {}
    } catch {
        $entry.status = 'failed_skipped'
        $entry.error = "$_"
        Write-Log ("FAIL (skip to next): {0}" -f $_)
        try {
            if (Test-Path -LiteralPath $pdf) {
                Copy-Item -LiteralPath $pdf -Destination (Join-Path $FailDir $j.Filename) -Force
            }
        } catch {}
    }

    $entry.finished = (Get-Date).ToString('o')
    $results += [pscustomobject]$entry
}

$results | ConvertTo-Json -Depth 6 | Set-Content $ReportJson -Encoding UTF8
$okN = @($results | Where-Object { $_.status -eq 'ok' }).Count
$failN = @($results | Where-Object { $_.status -ne 'ok' }).Count
$md = @('# P2 overnight report', '', "- Finished: $(Get-Date -Format o)", "- Total: $($results.Count)  OK: $okN  Failed/skipped: $failN", '- Policy: **skip on failure, continue**', '', '| Order | Subject | Title | Status | Pages | Chunks | Error |', '|------:|---------|-------|--------|------:|-------:|-------|')
foreach ($r in $results) {
    $err = ''
    if ($r.error) { $err = ($r.error -replace '\|', '/' -replace "[\r\n]+", ' '); if ($err.Length -gt 100) { $err = $err.Substring(0,100) } }
    $md += ("| {0} | {1} | {2} | {3} | {4} | {5} | {6} |" -f $r.order, $r.subject, $r.title, $r.status, $r.pages, $r.chunks, $err)
}
$md -join "`n" | Set-Content $ReportMd -Encoding UTF8
Write-Log ("P2 finished — OK={0} fail/skip={1}. See p2-report.md" -f $okN, $failN)
