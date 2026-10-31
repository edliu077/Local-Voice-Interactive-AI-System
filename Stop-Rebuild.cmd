@echo off
cd /d "%~dp0"
"%~dp0.venv-livetalking\Scripts\python.exe" -B -s "%~dp0scripts\rebuild-system.py" stop
pause
