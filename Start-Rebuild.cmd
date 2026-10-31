@echo off
cd /d "%~dp0"
"%~dp0.venv-livetalking\Scripts\python.exe" -B -s "%~dp0scripts\manual-rebuild.py"
if errorlevel 1 goto failed
echo Supervisor ended. Read runtime\stack for the final service state.
pause
exit /b 0
:failed
echo Startup blocked. Read the printed runtime\manual-start log directory and runtime\stack.
pause
exit /b 1
