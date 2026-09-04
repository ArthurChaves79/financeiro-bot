@echo off
REM ============================================================
REM  SIG View - gera o mapa de ruas de SP (.mbtiles)
REM  Requer Docker Desktop instalado e aberto (so pra gerar o
REM  arquivo - depois disso o proprio SIG View serve o mapa,
REM  sem precisar de Docker rodando no dia a dia).
REM  Rode de novo sempre que quiser atualizar o mapa.
REM ============================================================
title SIG View - Gerando mapa de ruas de SP...
cd /d "%~dp0"

echo.
echo === Verificando se o Docker esta rodando ===
docker version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERRO] Docker nao encontrado ou nao esta aberto.
    echo Instale o Docker Desktop: https://www.docker.com/products/docker-desktop/
    echo Abra o Docker Desktop e espere ele ficar pronto antes de rodar este arquivo de novo.
    echo.
    pause
    exit /b 1
)

if not exist tiles mkdir tiles
if not exist planetiler-data mkdir planetiler-data

echo.
echo === Baixando e processando os dados de ruas (OpenStreetMap) ===
echo Isso baixa a regiao Sudeste e recorta so o estado de Sao Paulo.
echo Pode demorar bastante na primeira vez (depende da sua internet).
echo.

docker run --rm -e JAVA_TOOL_OPTIONS="-Xmx2g" ^
  -v "%cd%\planetiler-data":/data ^
  -v "%cd%\tiles":/output ^
  ghcr.io/onthegomap/planetiler:latest ^
  --download ^
  --download-url=https://download.geofabrik.de/south-america/brazil/sudeste-latest.osm.pbf ^
  --bounds=-53.11,-25.31,-44.16,-19.78 ^
  --output=/output/ruas-sp.mbtiles

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
echo  Nao precisa de Docker rodando no dia a dia - o
echo  proprio SIG View serve esse arquivo (rota /tiles/*).
echo  So reabra o iniciar.bat (ou gere o SigView.exe de novo,
echo  copiando este arquivo pra perto dele) e o mapa ja
echo  aparece com as ruas.
echo ==================================================
echo.
pause
