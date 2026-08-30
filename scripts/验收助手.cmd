@echo off
setlocal
set "SCRIPT=%~dp0验收助手.ps1"
if not exist "%SCRIPT%" (
  echo 未找到验收助手.ps1
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -Launch
endlocal
