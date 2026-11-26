@echo off
rem MakerWorld to Any - instalador do ZIP (copia as pastas de skills deste ZIP para a pasta de skills do Claude Code)
set "BASE=%USERPROFILE%\.claude\skills"
echo MakerWorld to Any - feito pela Megatic (https://megatic.pt)
echo A instalar em %BASE%
if not exist "%BASE%" mkdir "%BASE%"
if exist "%BASE%\makerworld-update\SKILL.md" rmdir /S /Q "%BASE%\makerworld-update"
for /D %%d in ("%~dp0*") do (
  if exist "%%d\SKILL.md" (
    if exist "%BASE%\%%~nxd" rmdir /S /Q "%BASE%\%%~nxd"
    xcopy /E /I /Y "%%d" "%BASE%\%%~nxd" >nul
    echo   instalado: %%~nxd
  )
)
echo.
echo Feito. Abre uma sessao nova do Claude Code e usa:
echo   /kobrax "C:\...\modelo.3mf"       (ou /kobra4 /kobras1 /kobras1max /kobra3 /kobra3max)
echo   /anycubic Kobra 2 Neo "C:\...\modelo.3mf"
echo   /any-plates, /any-colors        arrumar pratos e mudar cores de um projeto ja adaptado
echo   /any-settings                   os teus perfis, pastas e precos
echo   /any-undo                       voltar atras
echo   /any-doctor teste               confirmar que esta tudo a funcionar
echo   /any-update                     atualizar
where python >nul 2>nul || where py >nul 2>nul || echo AVISO: nao encontrei o Python 3 - instala-o de python.org (marca "Add to PATH").
if not exist "C:\Program Files\AnycubicSlicerNext\AnycubicSlicerNext.exe" echo AVISO: nao encontrei o Anycubic Slicer Next em C:\Program Files\AnycubicSlicerNext.
pause
