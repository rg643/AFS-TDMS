@echo off
rem Starts TDMS Web automatically when you sign in to Windows.
schtasks /create /tn "TDMS Web" /tr "\"%~dp0Run_Server.bat\"" /sc onlogon /f
echo.
echo Done. TDMS Web will start when this Windows user signs in.
echo To remove it run:  schtasks /delete /tn "TDMS Web" /f
pause
