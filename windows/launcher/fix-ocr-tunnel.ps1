# One-shot repair: free Ubuntu :18090 and restart a single OCR tunnel.
$ErrorActionPreference = 'Continue'
. (Join-Path $PSScriptRoot 'medrack-config.ps1')
$cfg = $MedrackConfig

Write-Host 'Stopping duplicate Windows tunnels...'
Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -and (
            $_.CommandLine -like "*$($cfg.OcrTunnelRemotePort):127.0.0.1:$($cfg.OcrAgentPort)*" -or
            $_.CommandLine -like "*-R $($cfg.OcrTunnelRemotePort):*"
        )
    } |
    ForEach-Object {
        Write-Host "  kill PID $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

try { Stop-ScheduledTask -TaskName $cfg.OcrTunnelTaskName -ErrorAction SilentlyContinue } catch {}
Start-Sleep -Seconds 2

Write-Host "Freeing remote port $($cfg.OcrTunnelRemotePort) on $($cfg.LinuxHost)..."
if (Test-Path $cfg.SshKey) {
    $remote = '{0}@{1}' -f $cfg.LinuxUser, $cfg.LinuxHost
    $cmd = "fuser -k $($cfg.OcrTunnelRemotePort)/tcp 2>/dev/null; pkill -u $($cfg.LinuxUser) -f 'sshd-session: $($cfg.LinuxUser)@notty' 2>/dev/null; true; ss -tln | grep $($cfg.OcrTunnelRemotePort) || echo port_free"
    & ssh.exe -i $cfg.SshKey -o BatchMode=yes -o ConnectTimeout=10 $remote $cmd
}

Start-Sleep -Seconds 2
Write-Host 'Starting MedRack OCR Tunnel task...'
try {
    Start-ScheduledTask -TaskName $cfg.OcrTunnelTaskName
} catch {
    $hiddenTun = Join-Path $PSScriptRoot 'start-ocr-tunnel-hidden.ps1'
    Start-Process 'powershell.exe' -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden',
        '-File', $hiddenTun
    ) -WindowStyle Hidden
}

Start-Sleep -Seconds 5
Write-Host 'Verify from Ubuntu...'
$remote = '{0}@{1}' -f $cfg.LinuxUser, $cfg.LinuxHost
& ssh.exe -i $cfg.SshKey -o BatchMode=yes $remote "echo TUN:; curl -sS --max-time 4 http://127.0.0.1:$($cfg.OcrTunnelRemotePort)/v1/health; echo; echo LAN:; curl -sS --max-time 4 http://$($cfg.WindowsLanHost):$($cfg.OcrAgentPort)/v1/health; echo"
Write-Host 'Done. If TUN shows ok, the spam should stop.'
pause
