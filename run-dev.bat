@echo off
rem Runs Forge Setup from source. pywebview lives in the Python 3.10 install on
rem this machine, so prefer that interpreter over whatever "python" resolves to.
setlocal
set "PY=%LOCALAPPDATA%\Programs\Python\Python310\pythonw.exe"
if not exist "%PY%" set "PY=pythonw.exe"
start "" "%PY%" "%~dp0app.py" %*
endlocal
