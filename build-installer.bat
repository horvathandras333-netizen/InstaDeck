@echo off
rem Builds the portable app, then wraps it in a conventional Windows setup wizard.
setlocal

call "%~dp0build.bat"
if errorlevel 1 exit /b 1

set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
  echo Inno Setup 6 was not found. Install it, then run this file again.
  exit /b 1
)

"%ISCC%" "%~dp0InstaDeck.iss"
if errorlevel 1 ( echo. & echo INSTALLER BUILD FAILED & exit /b 1 )

echo.
echo Done -^> installer\InstaDeck-Setup.exe
endlocal
