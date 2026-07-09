# MedRack launcher - shared configuration.
# Edit these values if your network/paths ever change.
# Dot-sourced by medrack-launcher.ps1, medrack-stop.ps1 and setup-medrack-launcher.ps1.

$MedrackConfig = @{
    # --- Linux box that runs MedRack ---
    LinuxHost       = '192.168.29.82'
    LinuxUser       = 'sohail'
    FrontendPort    = 3010          # the web UI you open in the browser
    # Canonical Ubuntu stack (single workspace after 2026-07-09 consolidation)
    RemoteStart     = 'bash /home/sohail/medrack/start_stack.sh'
    RemoteStop      = 'bash /home/sohail/medrack/stop_stack.sh'

    # --- Qwopus model on THIS Windows PC ---
    ModelPort       = 8080
    ModelTaskName   = 'MedRack Qwopus Server'
    ModelBat        = 'C:\ai models\run-qwopus-medrack.bat'
    # Stop-flag file the model watchdog checks. "Stop MedRack" writes this
    # so the auto-restart watchdog exits instead of relaunching the model.
    # MUST match STOPFLAG in run-qwopus-medrack.bat (its own folder).
    ModelStopFlag   = 'C:\ai models\qwopus.stop'

    # --- SSH key used for passwordless login (created by setup) ---
    SshKey          = (Join-Path $env:USERPROFILE '.ssh\medrack_ed25519')

    # --- How long to wait (seconds) before giving up ---
    ModelWaitSec    = 300           # 21GB model can take a while to load
    FrontendWaitSec = 120

    # --- Windows OCR agent (P1 hybrid book ingest — started with MedRack) ---
    OcrAgentPort    = 8090
    OcrAgentDir     = 'C:\medrack-ocr'
    OcrAgentPython  = 'C:\medrack-ocr\venv\Scripts\python.exe'
    OcrAgentScript  = 'C:\medrack-ocr\ocr_agent_server.py'
    OcrAgentStopFlag = 'C:\medrack-ocr\ocr-agent.stop'
    # Ubuntu often cannot open Windows:8090 (firewall). Tunnel agent to Linux:
    #   Linux localhost:18090 -> this PC :8090
    OcrTunnelRemotePort = 18090
    # Ubuntu .env should use: MEDRACK_OCR_AGENT_URL=http://127.0.0.1:18090
}
