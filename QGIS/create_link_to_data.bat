@echo off
setlocal enabledelayedexpansion

REM Get the current user's username
for /f "tokens=*" %%a in ('echo %USERNAME%') do set "username=%%a"

REM Set the target directory for the symbolic link
set "targetDirectory=C:\Users\!username!\Sync\QGIS\data"

REM Check if the target directory exists
if not exist "!targetDirectory!" (
    echo Target directory does not exist. Make sure you have prepared the synch directory with the layers data and its path is "!targetDirectory!"
    pause
	exit /b 1
)

REM Set the current working directory to the location of the batch script
cd %~dp0

REM Create the symbolic link
mklink /d "data" "!targetDirectory!"

if !errorlevel! equ 0 (
    echo Symbolic link "data" created successfully.
) else (
    echo Failed to create the symbolic link.
	pause
    exit /b 1
)

pause
endlocal