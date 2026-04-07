@echo off
cd /d "%~dp0"
set PYTHONHOME=
set PYTHONPATH=
if not exist .venv\Scripts\python.exe (
  python -m venv .venv
)
call .venv\Scripts\python -m pip install -r requirements.txt
set PYTHONPATH=.
call .venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8011 --reload
