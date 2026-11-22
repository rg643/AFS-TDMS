@echo off
cd /d "%~dp0"
python tdms_app.py
if errorlevel 1 pause
