@echo off
rem ============================================================
rem Open Matrix Publisher - Windows double-click launcher
rem Calls start_ui.ps1 with ExecutionPolicy Bypass.
rem First run auto-detects the SAU engine; if missing, it will
rem guide you through a one-click install.
rem Optional arg: -Check  (environment check only, no server)
rem ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_ui.ps1" %*
if errorlevel 1 (
  echo.
  echo Startup failed - see the messages above. Press any key to close...
  pause >nul
)
