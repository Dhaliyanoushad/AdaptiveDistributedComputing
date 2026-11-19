@echo off
setlocal DisableDelayedExpansion
pushd "%~dp0.." || exit /b 1
if not exist "master\.venv\Scripts\python.exe" (
  echo Missing Master environment. Run scripts\setup.cmd.
  popd
  exit /b 1
)
"master\.venv\Scripts\python.exe" scripts\verify.py %*
set "taskExit=%errorlevel%"
popd
exit /b %taskExit%
