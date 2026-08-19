@echo off
rem ---------------------------------------------------------------------------
rem Builds dist\ForgeSetup.exe -- one portable file, no install, no runtime deps
rem beyond the Edge WebView2 runtime that ships with Windows 11.
rem ---------------------------------------------------------------------------
setlocal
set "PY=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
if not exist "%PY%" set "PY=python"

echo Building ForgeSetup.exe ...
"%PY%" -m PyInstaller ForgeSetup.spec --noconfirm --clean
if errorlevel 1 ( echo. & echo BUILD FAILED & exit /b 1 )

echo.
echo Done -^> dist\ForgeSetup.exe
endlocal
