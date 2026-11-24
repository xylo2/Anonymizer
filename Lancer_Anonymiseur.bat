@echo off
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" (
    set "PYW_EXE=.venv\Scripts\pythonw.exe"
) else if exist "venv\Scripts\pythonw.exe" (
    set "PYW_EXE=venv\Scripts\pythonw.exe"
) else (
    set "PYW_EXE=pythonw.exe"
)

start "" "%PYW_EXE%" gui_anonymizer.py --gui-errors %*
