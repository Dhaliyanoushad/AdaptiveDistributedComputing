# Initialization checks

## Observed environment

The initial directory listing was empty. No existing files were overwritten.

| Command / check | Observed result |
| --- | --- |
| `python --version` | Python 3.13.2 |
| `py -0p` | No installed Pythons found by the launcher; `python` works |
| `node --version` | v22.14.0 |
| `npm.cmd --version` | 11.12.0 |
| `git --version` | git version 2.46.0.windows.1 |
| `python -m venv master/.venv` | Completed; isolated Python 3.13.2 verified |
| `python -m venv worker/.venv` | Completed; isolated Python 3.13.2 verified |
| Each environment's `python -m pip --version` | pip 24.3.1 in its own environment |
| Each environment's `python -m pip check` | No broken requirements found; requested packages are absent |
| Master module availability (`importlib.util.find_spec`) | Missing: fastapi, uvicorn, websockets; check exited 1 |
| Worker module availability (`importlib.util.find_spec`) | Missing: requests, psutil, cv2; check exited 1 |
| `git rev-parse --is-inside-work-tree` | Not a Git repository; no repository was initialized |

## Dependency installation attempts

Both environments ran their own Python executable with:

```text
-m pip install -r <component>/requirements.txt --only-binary=:all: --retries 0 --timeout 20
```

Both were retried with `--index-url https://pypi.org/simple`. All four attempts exited 1. Pip reported no available versions / no matching distribution for the first requirement (FastAPI for master, requests for worker). The cause was not established. `PIP_NO_INDEX` was unset and `PIP_CONFIG_FILE` was not set in the environment.

Dependency installation and runtime compatibility are **not verified**. Module availability was checked, but actual package imports and application tests could not run because dependencies are missing. No frontend packages were installed and no frontend build was run. No application behavior exists to test yet.

## Manual completion

From the repository root, in an environment with access to an appropriate package index:

```powershell
& .\master\.venv\Scripts\python.exe -m pip install -r master/requirements.txt
& .\worker\.venv\Scripts\python.exe -m pip install -r worker/requirements.txt
& .\master\.venv\Scripts\python.exe -m pip check
& .\worker\.venv\Scripts\python.exe -m pip check
& .\master\.venv\Scripts\python.exe -c "import fastapi, uvicorn, websockets; print('Master imports OK')"
& .\worker\.venv\Scripts\python.exe -c "import requests, psutil, cv2; print('Worker imports OK')"
```

Installation commands resolve and install the declared dependencies; `pip check` checks installed dependency consistency; the final commands verify real imports. The commands in this manual completion section have not been run successfully during initialization.

Virtual environments are local, ignored artifacts; recreate them after moving the project. Initialize Git separately with `git init` if desired. Frontend initialization belongs to a later development phase.
