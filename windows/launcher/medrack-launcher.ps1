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

    # ===== 1b. OCR agent on this PC (hybrid book ingest) =====
    # Runs in background so Books → Hybrid OCR can stop the model, OCR,
    # validate, and restart the model without a separate manual window.
    if ($cfg.OcrAgentPort -and (Test-Port '127.0.0.1' $cfg.OcrAgentPort 800)) {
        Set-Status 'OCR agent already running.'
    } elseif ($cfg.OcrAgentPython -and (Test-Path $cfg.OcrAgentPython) -and (Test-Path $cfg.OcrAgentScript)) {
        Set-Status 'Starting OCR agent (for hybrid book ingest)...'
        if ($cfg.OcrAgentStopFlag -and (Test-Path $cfg.OcrAgentStopFlag)) {
            try { Remove-Item $cfg.OcrAgentStopFlag -Force } catch {}
        }
        # Detached console window so the agent survives after this script exits
        $startCmd = Join-Path $cfg.OcrAgentDir 'START-OCR-AGENT.cmd'
        if (Test-Path $startCmd) {
            Start-Process 'cmd.exe' -ArgumentList '/c', "start `"MedRack OCR Agent`" /MIN `"$startCmd`"" -WindowStyle Hidden
        } else {
            $ocrCmd = 'set PYTHONPATH={0}& set MEDRACK_API_BASE=http://{1}:8010/api/v1& set MEDRACK_OCR_TOKEN=medrack-ocr& set MEDRACK_OCR_PULL=1& "{2}" "{3}"' -f `
                $cfg.OcrAgentDir, $cfg.LinuxHost, $cfg.OcrAgentPython, $cfg.OcrAgentScript
            Start-Process 'cmd.exe' -ArgumentList '/c', $ocrCmd -WorkingDirectory $cfg.OcrAgentDir -WindowStyle Minimized
        }
        $null = Wait-Until { Test-Port '127.0.0.1' $cfg.OcrAgentPort 800 } 30 'Starting OCR agent...'
        if (Test-Port '127.0.0.1' $cfg.OcrAgentPort 800) {
            Set-Status 'OCR agent ready.'
        } else {
            Set-Status 'OCR agent still starting (hybrid ingest may need a moment)...'
        }
    }

    # ===== 1c. SSH reverse tunnel: Linux:18090 -> this PC:8090 =====
    # Windows Firewall often blocks Ubuntu→Windows:8090 even with an allow rule.
    # Tunneling through the existing SSH path (Windows→Ubuntu) always works.
    if ($cfg.OcrTunnelRemotePort -and (Test-Path $cfg.SshKey)) {
        Set-Status 'Opening OCR tunnel to the server...'
        # Kill any old tunnel on the same remote port (best effort)
        Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -and $_.CommandLine -like "*$($cfg.OcrTunnelRemotePort):127.0.0.1:$($cfg.OcrAgentPort)*" } |
            ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {} }
        $tunArgs = '-i "{0}" -N -o BatchMode=yes -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -R {1}:127.0.0.1:{2} {3}@{4}' -f `
            $cfg.SshKey, $cfg.OcrTunnelRemotePort, $cfg.OcrAgentPort, $cfg.LinuxUser, $cfg.LinuxHost
        Start-Process 'ssh' -ArgumentList $tunArgs -WindowStyle Hidden
        Start-Sleep -Milliseconds 800
        Set-Status 'OCR tunnel ready.'
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
