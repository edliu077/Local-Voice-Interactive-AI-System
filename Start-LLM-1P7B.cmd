@echo off
cd /d "%~dp0"
"%~dp0.venv-livetalking\Scripts\python.exe" -B -s "%~dp0scripts\rebuild-llm-profile.py" start --profile 1.7b
exit /b %errorlevel%
