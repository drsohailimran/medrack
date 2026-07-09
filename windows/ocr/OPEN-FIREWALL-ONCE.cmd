@echo off
:: Run once as Administrator so Ubuntu can push OCR jobs to this PC.
netsh advfirewall firewall delete rule name="MedRack OCR Agent 8090" >nul 2>&1
netsh advfirewall firewall add rule name="MedRack OCR Agent 8090" dir=in action=allow protocol=TCP localport=8090
echo.
echo Firewall rule for port 8090 installed (or already present).
echo You can close this window.
pause
