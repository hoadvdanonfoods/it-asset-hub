@echo off
echo Starting IT Asset Hub service...
net start ITAssetHub
echo.
sc query ITAssetHub
pause
