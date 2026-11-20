@echo off
chcp 65001 >nul
cd /d "%~dp0"
pythonw gui_anonymizer.py
if errorlevel 1 (
    python gui_anonymizer.py
    pause
)
