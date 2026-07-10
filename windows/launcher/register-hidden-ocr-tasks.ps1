# Re-register OCR Agent + Tunnel as hidden background tasks (no admin required for own tasks).
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'medrack-config.ps1')
$cfg = $MedrackConfig
$user = "$env:USERDOMAIN\$env:USERNAME"

function Register-HiddenTask {
    param(
        [string]$Name,
        [string]$Ps1Path,
        [string]$WorkDir
    )
    if (-not (Test-Path -LiteralPath $Ps1Path)) { throw "Missing $Ps1Path" }

    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument (
        "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Ps1Path`""
    ) -WorkingDirectory $WorkDir

    $triggers = @(
        (New-ScheduledTaskTrigger -AtLogOn -User $user),
        (New-ScheduledTaskTrigger -AtStartup)
    )

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -RestartCount 999 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew `
        -DontStopOnIdleEnd `
        -Hidden

    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $triggers `
        -Principal $principal -Settings $settings -Force | Out-Null
    Write-Host "[OK] $Name -> hidden ($Ps1Path)"
}

$agentPs1 = Join-Path $cfg.OcrAgentDir 'start-ocr-agent-hidden.ps1'
$tunPs1 = Join-Path $PSScriptRoot 'start-ocr-tunnel-hidden.ps1'

# Stop old visible instances
Write-Host 'Stopping old OCR agent / tunnel consoles...'
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and (
        $_.CommandLine -match 'ocr_agent_server|START-OCR-AGENT|start-ocr-tunnel|start-ocr-agent-hidden|start-ocr-tunnel-hidden'
    )
} | ForEach-Object {
    Write-Host "  kill pid $($_.ProcessId)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Get-NetTCPConnection -LocalPort 8090 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}
Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match '-R 18090:'
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
try { Stop-ScheduledTask -TaskName 'MedRack OCR Agent' -ErrorAction SilentlyContinue } catch {}
try { Stop-ScheduledTask -TaskName 'MedRack OCR Tunnel' -ErrorAction SilentlyContinue } catch {}
Start-Sleep -Seconds 2

Register-HiddenTask -Name 'MedRack OCR Agent' -Ps1Path $agentPs1 -WorkDir $cfg.OcrAgentDir
Register-HiddenTask -Name 'MedRack OCR Tunnel' -Ps1Path $tunPs1 -WorkDir $PSScriptRoot

Start-ScheduledTask -TaskName 'MedRack OCR Agent'
Start-Sleep -Seconds 3
Start-ScheduledTask -TaskName 'MedRack OCR Tunnel'
Start-Sleep -Seconds 2

Write-Host ''
Write-Host 'Health check:'
try {
    $h = Invoke-WebRequest -Uri 'http://127.0.0.1:8090/v1/health' -UseBasicParsing -TimeoutSec 5
    Write-Host "  OCR agent: $($h.Content)"
} catch {
    Write-Host "  OCR agent: not up yet ($($_.Exception.Message))"
}

Get-ScheduledTask -TaskName 'MedRack OCR Agent','MedRack OCR Tunnel' | ForEach-Object {
    Write-Host ("  Task {0}: {1}  Hidden={2}" -f $_.TaskName, $_.State, $_.Settings.Hidden)
}
Write-Host 'Done. No OCR console windows should appear on the desktop.'
