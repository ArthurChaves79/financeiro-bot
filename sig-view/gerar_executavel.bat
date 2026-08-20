@echo off
REM ============================================================
REM  SIG View - gera o SigView.exe
REM  Rode isto UMA VEZ (numa maquina com Python e internet, ex: a
REM  mesma onde voce rodou instalar.bat). O .exe gerado pode depois
REM  ser copiado para qualquer PC Windows, sem precisar instalar
REM  Python nem nada - e um arquivo so.
REM ============================================================
title SIG View - Gerando executavel...
cd /d "%~dp0backend"

echo.
echo === Verificando se o Python esta instalado ===
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERRO] Python nao encontrado. Rode instalar.bat primeiro.
    echo.
    pause
    exit /b 1
)

if not exist .venv (
    echo.
    echo [ERRO] Ainda nao foi instalado. Rode instalar.bat primeiro.
    echo.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

echo.
echo === Instalando o PyInstaller (ferramenta que gera o .exe) ===
pip install -r requirements-build.txt

echo.
echo === Gerando o executavel (pode demorar alguns minutos) ===
pyinstaller --noconfirm --onefile --name SigView ^
  --icon "..\assets\icon.ico" ^
  --add-data "..\frontend;frontend" ^
  --collect-submodules uvicorn ^
  --collect-all webview ^
  --collect-all clr_loader ^
  --collect-all pythonnet ^
  run.py

if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao gerar o executavel. Veja a mensagem acima.
    echo.
    pause
    exit /b 1
)

echo.
echo === Copiando o SigView.exe para a pasta principal ===
copy /Y dist\SigView.exe "..\SigView.exe" >nul

echo.
echo === Levando o mapa (.mbtiles) junto, se ja tiver sido gerado ===
if exist data\mapa.mbtiles (
    if not exist "..\data" mkdir "..\data"
    copy /Y data\mapa.mbtiles "..\data\mapa.mbtiles" >nul
    echo Mapa copiado - o .exe ja sai com as ruas prontas.
) else (
    echo Nenhum mapa.mbtiles encontrado ainda - rode gerar_e_subir_mapa.bat
    echo antes, se quiser que o .exe ja saia com o mapa de ruas.
)

echo.
echo ==================================================
echo  Pronto! O arquivo SigView.exe esta em:
echo  %~dp0SigView.exe
echo.
echo  Para distribuir com o mapa embutido, copie SigView.exe
echo  JUNTO com a pasta "data" (que fica do lado dele) para
echo  o outro computador. Sem a pasta data, o programa ainda
echo  funciona, so que sem o mapa de ruas ate voce configurar
echo  um em Configuracoes.
echo ==================================================
echo.
pause
