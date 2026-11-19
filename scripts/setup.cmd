@echo off
setlocal DisableDelayedExpansion
pushd "%~dp0.." || exit /b 1
python -c "import sys; assert sys.version_info[:2] == (3,13), 'Python 3.13 required; tested with 3.13.2'" || goto failed
node -e "const [a,b]=process.versions.node.split('.').map(Number); if(a<22 || (a===22 && b<14)) process.exit(1)" || goto failed
call npm.cmd --version || goto failed
git --version || goto failed
if not exist "master\.venv\Scripts\python.exe" python -m venv master\.venv
if not exist "worker\.venv\Scripts\python.exe" python -m venv worker\.venv
"master\.venv\Scripts\python.exe" -m pip install -r master\requirements.txt || goto failed
"worker\.venv\Scripts\python.exe" -m pip install -r worker\requirements.txt || goto failed
pushd frontend || goto failed
call npm.cmd ci
set "installExit=%errorlevel%"
popd
if not "%installExit%"=="0" goto failed
echo Setup complete. Run scripts\test_all.cmd. Local .env files were not overwritten.
popd
exit /b 0
:failed
echo Setup failed. Review the first failed command. Existing files were preserved.
popd
exit /b 1
