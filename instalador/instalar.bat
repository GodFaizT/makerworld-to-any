@echo off
rem MakerWorld to Any - ZIP installer (copies the skill folders in this ZIP to the Claude Code skills folder)
set "BASE=%USERPROFILE%\.claude\skills"
echo MakerWorld to Any - made by Megatic (https://megatic.pt)
echo Installing in %BASE%
if not exist "%BASE%" mkdir "%BASE%"
if exist "%BASE%\makerworld-update\SKILL.md" rmdir /S /Q "%BASE%\makerworld-update"
for /D %%d in ("%~dp0*") do (
  if exist "%%d\SKILL.md" (
    if exist "%BASE%\%%~nxd" rmdir /S /Q "%BASE%\%%~nxd"
    xcopy /E /I /Y "%%d" "%BASE%\%%~nxd" >nul
    echo   installed: %%~nxd
  )
)
echo.
echo Done. Open a new Claude Code session and use:
echo   /kobrax "C:\...\model.3mf"        (or /kobra4 /kobras1 /kobras1max /kobra3 /kobra3max)
echo   /anycubic Kobra 2 Neo "C:\...\model.3mf"
echo   /any-plates, /any-colors        arrange plates and change colors of an adapted project
echo   /any-settings                   your profiles, folders and prices
echo   /any-undo                       go back
echo   /any-doctor test                check that everything works
echo   /any-update                     update
where python >nul 2>nul || where py >nul 2>nul || echo WARNING: Python 3 not found - install it from python.org (tick "Add to PATH").
if not exist "C:\Program Files\AnycubicSlicerNext\AnycubicSlicerNext.exe" echo WARNING: Anycubic Slicer Next not found in C:\Program Files\AnycubicSlicerNext.
pause
