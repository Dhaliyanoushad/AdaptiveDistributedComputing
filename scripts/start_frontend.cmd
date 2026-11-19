@echo off
setlocal DisableDelayedExpansion
pushd "%~dp0.." || exit /b 1
python scripts\launch.py frontend %*
set "taskExit=%errorlevel%"
popd
exit /b %taskExit%
