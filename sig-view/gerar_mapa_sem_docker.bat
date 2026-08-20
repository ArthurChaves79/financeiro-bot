@echo off
REM ============================================================
REM  SIG View - gera o mapa de ruas de SP (.mbtiles), SEM Docker
REM  Alternativa ao gerar_e_subir_mapa.bat para quem tem problema
REM  com Docker/WSL - so precisa de Java instalado.
REM  Rode de novo sempre que quiser atualizar o mapa.
REM ============================================================
title SIG View - Gerando mapa de ruas de SP (sem Docker)...
cd /d "%~dp0"

echo.
echo === Verificando se o Java esta instalado ===
java -version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERRO] Java nao encontrado.
    echo Instale o Java (Temurin, gratuito): https://adoptium.net/pt-BR/temurin/releases/
    echo Baixe a versao "JRE" mais recente para Windows x64, instale, e rode este arquivo de novo.
    echo.
    pause
    exit /b 1
)

if not exist tiles mkdir tiles

if not exist planetiler.jar (
    echo.
    echo === Baixando o Planetiler (ferramenta que gera o mapa) ===
    echo Isso baixa uma vez so, uns 50 MB.
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/onthegomap/planetiler/releases/latest/download/planetiler.jar' -OutFile 'planetiler.jar'"
    if errorlevel 1 (
        echo.
        echo [ERRO] Falha ao baixar o planetiler.jar. Verifique sua internet.
        echo.
        pause
        exit /b 1
    )
)

echo.
echo === Baixando e processando os dados de ruas (OpenStreetMap) ===
echo Isso baixa a regiao Sudeste e recorta so o estado de Sao Paulo.
echo Pode demorar bastante na primeira vez (depende da sua internet e do computador).
echo.

java -Xmx2g -jar planetiler.jar ^
  --download ^
  --download-url=https://download.geofabrik.de/south-america/brazil/sudeste-latest.osm.pbf ^
  --bounds=-53.11,-25.31,-44.16,-19.78 ^
  --output=tiles\ruas-sp.mbtiles

if errorlevel 1 (
    echo.
    echo [ERRO] Algo deu errado ao gerar o mapa. Veja a mensagem acima.
    echo.
    pause
    exit /b 1
)

echo.
echo === Colocando o mapa no lugar que o SIG View le ===
if not exist backend\data mkdir backend\data
copy /Y tiles\ruas-sp.mbtiles backend\data\mapa.mbtiles >nul

echo.
echo ==================================================
echo  Pronto! O mapa foi salvo em backend\data\mapa.mbtiles
echo  So reabra o iniciar.bat (ou gere o SigView.exe de novo,
echo  copiando este arquivo pra perto dele) e o mapa ja
echo  aparece com as ruas.
echo ==================================================
echo.
pause
