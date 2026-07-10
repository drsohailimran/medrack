# ============================================================
#  Authorize this PC's SSH key on the MedRack server.
#  Run this ONCE. You'll type the server password a single time.
#  (No admin rights needed for this step.)
# ============================================================

. (Join-Path $PSScriptRoot 'medrack-config.ps1')
$cfg = $MedrackConfig
$target = "$($cfg.LinuxUser)@$($cfg.LinuxHost)"

Write-Host ''
Write-Host '=== Authorize SSH key on the MedRack server ===' -ForegroundColor Cyan
Write-Host "Server: $target" -ForegroundColor Cyan
Write-Host ''

# Make sure the key exists (create it if setup didn't).
if (-not (Test-Path $cfg.SshKey)) {
    Write-Host 'No SSH key found - creating one...' -ForegroundColor Yellow
    cmd /c "ssh-keygen -t ed25519 -f `"$($cfg.SshKey)`" -N `"`" -C medrack-launcher" | Out-Null
}
if (-not (Test-Path "$($cfg.SshKey).pub")) {
    Write-Host 'ERROR: public key missing.' -ForegroundColor Red
    Read-Host 'Press Enter to close'; exit 1
}

# Already working?
$pre = & ssh -i $cfg.SshKey -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 $target 'echo ok' 2>$null
if ($pre -eq 'ok') {
    Write-Host '[OK] Passwordless login already works. Nothing to do.' -ForegroundColor Green
    Read-Host 'Press Enter to close'; exit 0
}

$pub = (Get-Content "$($cfg.SshKey).pub" -Raw).Trim()
$remoteCmd = "umask 077; mkdir -p ~/.ssh && echo '$pub' >> ~/.ssh/authorized_keys && sort -u ~/.ssh/authorized_keys -o ~/.ssh/authorized_keys && echo medrack-authorized"

Write-Host 'You will now be asked for the server password ONE time.' -ForegroundColor Yellow
Write-Host '(Typing is invisible - no dots or stars will show. Just type it and press Enter.)' -ForegroundColor Yellow
Write-Host ''

# Pubkey passed as an argument (NOT stdin) so ssh can read the password.
$res = & ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 $target $remoteCmd

Write-Host ''
if ($res -contains 'medrack-authorized') {
    $verify = & ssh -i $cfg.SshKey -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 $target 'echo ok' 2>$null
    if ($verify -eq 'ok') {
        Write-Host '[SUCCESS] Passwordless login is working!' -ForegroundColor Green
        Write-Host 'You can now use the "Start MedRack" shortcut.' -ForegroundColor Green
    } else {
        Write-Host '[PARTIAL] Key was added but verification failed. Try running this again.' -ForegroundColor Yellow
    }
} else {
    Write-Host '[FAILED] Could not authorize the key.' -ForegroundColor Red
    Write-Host 'Common causes: wrong password, or the server was unreachable.' -ForegroundColor Red
    Write-Host 'Just run this file again to retry.' -ForegroundColor Red
}
Write-Host ''
Read-Host 'Press Enter to close'
