@echo off
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
 echo Please install uv from https://docs.astral.sh/uv/getting-started/installation/ then reopen this launcher.
 pause
 exit /b 1
)
uv sync --frozen --no-dev
if errorlevel 1 (
 pause
 exit /b 1
)
uv run --no-sync streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
pause
