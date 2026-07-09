# ============================================================
#  MedRack - one-click start (daily use)
#  Double-click the "Start MedRack" desktop shortcut.
#
#  What it does, in order:
#    1. Starts the Qwopus model on this PC (silent, elevated task)
#    2. Waits until the model is listening on :8080
#    3. Starts MedRack on the Linux box over SSH (passwordless)
#    4. Waits until the web UI on :3010 is actually reachable
#    5. Opens the browser to the web UI
#
#  A small "Starting MedRack" splash shows progress the whole time.
#  Run setup-medrack-launcher.ps1 ONCE before first use.
# ============================================================

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'medrack-config.ps1')
$cfg = $MedrackConfig

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# ---------- Splash window ----------
$form = New-Object System.Windows.Forms.Form
$form.FormBorderStyle = 'None'
$form.StartPosition   = 'CenterScreen'
$form.Size            = New-Object System.Drawing.Size(440, 170)
$form.BackColor       = [System.Drawing.Color]::FromArgb(24, 28, 38)
$form.TopMost         = $true
$form.ShowInTaskbar   = $true
$form.Text            = 'MedRack'

$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Text      = 'Starting MedRack...'
$lblTitle.ForeColor = [System.Drawing.Color]::White
$lblTitle.Font      = New-Object System.Drawing.Font('Segoe UI', 16, [System.Drawing.FontStyle]::Bold)
$lblTitle.AutoSize  = $false
$lblTitle.TextAlign = 'MiddleCenter'
$lblTitle.Dock      = 'Top'
$lblTitle.Height    = 70
$form.Controls.Add($lblTitle)

$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.Text      = 'Please wait...'
$lblStatus.ForeColor = [System.Drawing.Color]::FromArgb(150, 200, 255)
$lblStatus.Font      = New-Object System.Drawing.Font('Segoe UI', 10)
$lblStatus.AutoSize  = $false
$lblStatus.TextAlign = 'MiddleCenter'
$lblStatus.Dock      = 'Fill'
$form.Controls.Add($lblStatus)

$form.Show()
[System.Windows.Forms.Application]::DoEvents()

function Set-Status([string]$t) {
    $lblStatus.Text = $t
    [System.Windows.Forms.Application]::DoEvents()
}

# ---------- Helpers ----------
function Test-Port([string]$h, [int]$p, [int]$timeoutMs = 1000) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect($h, $p, $null, $null)
        if ($iar.AsyncWaitHandle.WaitOne($timeoutMs)) {
            $client.EndConnect($iar); return $true
        }
        return $false
    } catch { return $false } finally { $client.Close() }
}

# Polls until $test returns $true or timeout. Keeps the splash responsive.
function Wait-Until([scriptblock]$test, [int]$timeoutSec, [string]$msg) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $timeoutSec) {
        if (& $test) { return $true }
        Set-Status ("{0}   ({1}s)" -f $msg, [int]$sw.Elapsed.TotalSeconds)
        Start-Sleep -Milliseconds 400
        [System.Windows.Forms.Application]::DoEvents()
    }
    return $false
}

function Show-Error([string]$msg) {
    $form.Hide()
    [System.Windows.Forms.MessageBox]::Show($msg, 'MedRack - could not start',
        'OK', 'Error') | Out-Null
}

try {
    # ===== 1. Model on this PC =====
    if (Test-Port '127.0.0.1' $cfg.ModelPort) {
        Set-Status 'Model already running.'
    } else {
        Set-Status 'Starting the AI model on this PC...'
        # Prefer the elevated scheduled task (no UAC popup). Fall back to the
        # .bat directly if the task isn't registered yet.
        $task = Get-ScheduledTask -TaskName $cfg.ModelTaskName -ErrorAction SilentlyContinue
        if ($task) {
            Start-ScheduledTask -TaskName $cfg.ModelTaskName
        } elseif (Test-Path $cfg.ModelBat) {
            Start-Process 'cmd.exe' -ArgumentList '/c', "`"$($cfg.ModelBat)`"" -WindowStyle Minimized
        } else {
            throw "Model task '$($cfg.ModelTaskName)' is not registered and the .bat was not found.`n`nRun setup-medrack-launcher.ps1 once first."
        }
        if (-not (Wait-Until { Test-Port '127.0.0.1' $cfg.ModelPort } $cfg.ModelWaitSec 'Loading the AI model...')) {
            throw "The AI model did not come up on port $($cfg.ModelPort) within $($cfg.ModelWaitSec)s.`n`nCheck the 'MedRack Qwopus Server' window for errors."
        }
        Set-Status 'Model ready.'
    }

    # ===== 1b. Permanent LAN link (OCR agent + tunnel backup) =====
    # Prefer scheduled tasks (INSTALL-PERMANENT-LINK.cmd). Fallback to direct start.
    Set-Status 'Ensuring permanent Ubuntu link (OCR)...'
    if ($cfg.OcrAgentStopFlag -and (Test-Path $cfg.OcrAgentStopFlag)) {
        try { Remove-Item $cfg.OcrAgentStopFlag -Force } catch {}
    }
    $agentTask = $cfg.OcrAgentTaskName
    if ($agentTask) {
        try { Start-ScheduledTask -TaskName $agentTask -ErrorAction SilentlyContinue } catch {}
    }
    if (-not (Test-Port '127.0.0.1' $cfg.OcrAgentPort 800)) {
        $startCmd = Join-Path $cfg.OcrAgentDir 'START-OCR-AGENT.cmd'
        if (Test-Path $startCmd) {
            Start-Process 'cmd.exe' -ArgumentList '/c', "start `"MedRack OCR Agent`" /MIN `"$startCmd`"" -WindowStyle Hidden
        }
        $null = Wait-Until { Test-Port '127.0.0.1' $cfg.OcrAgentPort 800 } 30 'Starting OCR agent...'
    }
    if (Test-Port '127.0.0.1' $cfg.OcrAgentPort 800) {
        Set-Status 'OCR agent ready (LAN).'
    } else {
        Set-Status 'OCR agent still starting...'
    }

    # Tunnel backup (Ubuntu 127.0.0.1:18090 → this PC :8090)
    if ($cfg.OcrTunnelRemotePort -and (Test-Path $cfg.SshKey)) {
        $tunTask = $cfg.OcrTunnelTaskName
        if ($tunTask) {
            try { Start-ScheduledTask -TaskName $tunTask -ErrorAction SilentlyContinue } catch {}
        }
        $tunAlive = $false
        Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -and $_.CommandLine -like "*$($cfg.OcrTunnelRemotePort):127.0.0.1:$($cfg.OcrAgentPort)*" } |
            ForEach-Object { $tunAlive = $true }
        if (-not $tunAlive) {
            $tunCmd = Join-Path $PSScriptRoot 'start-ocr-tunnel.cmd'
            if (Test-Path $tunCmd) {
                Start-Process 'cmd.exe' -ArgumentList '/c', "start `"MedRack OCR Tunnel`" /MIN `"$tunCmd`"" -WindowStyle Hidden
            } else {
                $tunArgs = '-i "{0}" -N -o BatchMode=yes -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -R {1}:127.0.0.1:{2} {3}@{4}' -f `
                    $cfg.SshKey, $cfg.OcrTunnelRemotePort, $cfg.OcrAgentPort, $cfg.LinuxUser, $cfg.LinuxHost
                Start-Process 'ssh' -ArgumentList $tunArgs -WindowStyle Hidden
            }
            Start-Sleep -Milliseconds 1200
        }
        Set-Status 'LAN link ready (direct + tunnel backup).'
    }

    # ===== 2. MedRack on the Linux box =====
    $sshProc = $null
    if (Test-Port $cfg.LinuxHost $cfg.FrontendPort) {
        Set-Status 'MedRack already running.'
    } else {
        Set-Status 'Starting MedRack on the server...'
        # NOTE: the key path can contain spaces (e.g. "C:\Users\Sohail Imran\...").
        # Start-Process does NOT auto-quote array args, so we build a single
        # argument string and quote the key path explicitly.
        $sshCmd = '-i "{0}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 {1}@{2} {3}' -f `
            $cfg.SshKey, $cfg.LinuxUser, $cfg.LinuxHost, $cfg.RemoteStart
        $sshProc = Start-Process 'ssh' -ArgumentList $sshCmd -WindowStyle Hidden -PassThru

        # Wait for the web UI, but bail out FAST if the SSH session dies before
        # the UI is up (that means auth/connection failed - no point waiting).
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $ready = $false
        while ($sw.Elapsed.TotalSeconds -lt $cfg.FrontendWaitSec) {
            if (Test-Port $cfg.LinuxHost $cfg.FrontendPort) { $ready = $true; break }
            if ($sshProc.HasExited -and $sshProc.ExitCode -ne 0) {
                throw "The SSH connection to $($cfg.LinuxHost) ended unexpectedly (code $($sshProc.ExitCode)) before MedRack came up.`n`nIf this keeps happening, double-click AUTHORIZE-SERVER.cmd in C:\Medrack\launcher to re-check passwordless login, then try again."
            }
            Set-Status ("Waiting for MedRack to be ready...   ({0}s)" -f [int]$sw.Elapsed.TotalSeconds)
            Start-Sleep -Milliseconds 400
            [System.Windows.Forms.Application]::DoEvents()
        }
        if (-not $ready) {
            throw "MedRack did not open port $($cfg.FrontendPort) within $($cfg.FrontendWaitSec)s.`n`nThe server may still be starting - try again in a minute."
        }
        # MedRack backgrounds its own services, so the SSH session is no longer
        # needed. Close it so it doesn't linger.
        if ($sshProc -and -not $sshProc.HasExited) {
            Start-Sleep -Milliseconds 500
            try { $sshProc.Kill() } catch {}
        }
        Set-Status 'MedRack ready.'
    }

    # ===== 3. Open the browser =====
    $url = "http://$($cfg.LinuxHost):$($cfg.FrontendPort)"
    Set-Status 'Opening MedRack in your browser...'
    Start-Process $url
    $lblTitle.Text = 'MedRack is ready!'
    Set-Status $url
    Start-Sleep -Milliseconds 1600
}
catch {
    Show-Error $_.Exception.Message
}
finally {
    $form.Close()
    $form.Dispose()
}

