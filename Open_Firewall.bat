@echo off
rem Lets other computers in your network open TDMS Web on port 8080. Run this ONCE as Administrator.
net session >nul 2>&1
if errorlevel 1 goto notadmin
netsh advfirewall firewall delete rule name="TDMS Web" >nul 2>&1
netsh advfirewall firewall add rule name="TDMS Web" dir=in action=allow protocol=TCP localport=8080 profile=private,domain
echo.
echo Done. Other computers can now open  http://THIS-PC-IP:8080
echo If your network is set to Public, change it to Private in the Windows network settings.
pause
exit /b 0

:notadmin
echo.
echo Please right-click this file and choose  Run as administrator.
echo.
pause
exit /b 1
