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
echo === Verificando se o Java esta disponivel ===
set "JAVA_CMD=java"
if exist "%~dp0jre\bin\java.exe" (
    REM Java "portatil": basta ter extraido o .zip do Adoptium numa
    REM pasta chamada "jre" aqui do lado, sem precisar instalar nada.
    set "JAVA_CMD=%~dp0jre\bin\java.exe"
    echo Usando Java de %~dp0jre\bin\java.exe
) else (
    "%JAVA_CMD%" -version >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [ERRO] Java nao encontrado.
        echo Duas opcoes:
        echo  1^) Baixe o instalador .msi do Java: https://adoptium.net/pt-BR/temurin/releases/
        echo     ^(Sistema Operacional=Windows, Pacote=JRE, e escolha o link ".msi"^)
        echo  2^) Ou, se ja baixou um .zip: extraia, renomeie a pasta de dentro pra
        echo     "jre" e coloque aqui dentro de sig-view, ao lado deste arquivo,
        echo     de forma que exista sig-view\jre\bin\java.exe
        echo Depois rode este arquivo de novo.
        echo.
        pause
        exit /b 1
    )
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

"%JAVA_CMD%" -Xmx2g -jar planetiler.jar ^
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
