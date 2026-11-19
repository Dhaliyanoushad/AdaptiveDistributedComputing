@echo off
setlocal DisableDelayedExpansion
pushd "%~dp0.." || exit /b 1
if not exist "worker\.venv\Scripts\python.exe" (
  echo Missing Worker environment.
  popd
  exit /b 1
)
"worker\.venv\Scripts\python.exe" -m benchmarks.report %*
set "taskExit=%errorlevel%"
popd
exit /b %taskExit%
