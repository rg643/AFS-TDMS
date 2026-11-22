@echo off
title Build TDMS
cd /d "%~dp0"
echo ============================================
echo   Building TDMS.exe  (one time)
echo ============================================
python -m pip install --upgrade pip
python -m pip install pillow pyinstaller
echo Optional add-on (PDF viewer) - skipped quietly if it cannot be installed:
python -m pip install pymupdf
set EXTRA=
python -c "import fitz" >nul 2>nul && set EXTRA=%EXTRA% --hidden-import fitz
python -m PyInstaller --noconfirm --clean --onefile --windowed --hidden-import PIL._tkinter_finder --hidden-import tdms_admin --hidden-import tdms_core --hidden-import tdms_graphics --hidden-import tdms_widgets --hidden-import tdms_native --hidden-import tdms_viewers %EXTRA% --name TDMS --icon app_icon.ico --add-data "app_icon.ico;." --add-data "app_icon.png;." --add-data "logo.png;." tdms_app.py
if exist dist\TDMS.exe (
    copy /Y dist\TDMS.exe "%~dp0TDMS.exe" >nul
    rmdir /S /Q build
    rmdir /S /Q dist
    del /Q TDMS.spec
    echo.
    echo DONE!  TDMS.exe is ready in this folder.
    echo Double-click it, then right-click its taskbar icon and choose "Pin to taskbar".
) else (
    echo.
    echo Build failed - please send me the message shown above.
)
pause
