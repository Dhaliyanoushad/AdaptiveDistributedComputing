@echo off
setlocal DisableDelayedExpansion
pushd "%~dp0.." || exit /b 1
if not exist "worker\.venv\Scripts\python.exe" (
  echo Missing Worker environment. Run scripts\setup.cmd.
  popd
  exit /b 1
)
"worker\.venv\Scripts\python.exe" scripts\launch.py worker %*
set "taskExit=%errorlevel%"
popd
exit /b %taskExit%
