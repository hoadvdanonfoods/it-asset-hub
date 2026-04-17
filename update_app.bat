@echo off
set GIT_PATH="C:\Program Files\Git\bin\git.exe"
set APP_PATH="C:\Apps\ITAssetHub"
set VENV_PYTHON="%APP_PATH%\.venv\Scripts\python.exe"
set NSSM_PATH="%APP_PATH%\tools\nssm.exe"

echo [1/3] Pulling latest code from GitHub...
%GIT_PATH% -C %APP_PATH% pull origin main

echo [2/3] Updating dependencies...
%VENV_PYTHON% -m pip install -r %APP_PATH%\requirements.txt

echo [3/3] Restarting ITAssetHub Service...
%NSSM_PATH% restart ITAssetHub

echo Done!
pause
