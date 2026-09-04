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
pyinstaller --noconfirm --onefile --windowed --name SigView ^
  --icon "..\assets\icon.ico" ^
  --add-data "..\frontend;frontend" ^
  --add-data "scripts;scripts" ^
  --hidden-import app.geoutil ^
  --hidden-import app.campos_conhecidos ^
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
echo === Levando outros mapas (data\maps\*.mbtiles), se existirem ===
if exist data\maps (
    if not exist "..\data\maps" mkdir "..\data\maps"
    xcopy /Y /I data\maps\*.mbtiles "..\data\maps\" >nul 2>&1
    echo Pasta data\maps copiada - aparecem como opcoes em Configuracoes.
)

echo.
echo === Levando as fontes dos rotulos (data\fonts), se ja tiver baixado ===
if exist data\fonts (
    xcopy /Y /I /E data\fonts "..\data\fonts\" >nul 2>&1
    echo Pasta data\fonts copiada - nomes de rua/bairro aparecem no mapa.
) else (
    echo Nenhuma fonte encontrada ainda - veja o README ("Nomes de rua no
    echo mapa"^) se quiser que os rotulos apareçam no mapa.
)

echo.
echo ==================================================
echo  Pronto! O arquivo SigView.exe esta em:
echo  %~dp0SigView.exe
echo.
echo  Para instalar num outro computador, copie SO ISSO:
echo    - SigView.exe
echo    - a pasta "data" do lado dele (mapa.mbtiles / data\maps / data\fonts)
echo  NAO precisa levar GeoJSON nenhum - sem a pasta data\layers
echo  o SigView.exe abre normal, so sem camadas na lista. Depois
echo  de colocar os .geojson naquele computador (local ou pasta
echo  de rede), aponte o caminho em Configuracoes.
echo.
echo  Este .exe abre SEM a telinha de console/cmd atras da janela.
echo  Se algo der errado e a janela nao abrir, o log fica em
echo  data\sigview.log (do lado do .exe) - da pra ver o que
echo  aconteceu por la.
echo ==================================================
echo.
pause
