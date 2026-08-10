@echo off
REM ============================================================
REM  SIG View - iniciar o programa
REM  De um duplo-clique neste arquivo sempre que quiser usar o SIG View.
REM  Para fechar, feche esta janela preta (ou aperte Ctrl+C e confirme).
REM ============================================================
title SIG View - Rodando (nao feche esta janela)
cd /d "%~dp0backend"

if not exist .venv (
    echo.
    echo [ERRO] Ainda nao foi instalado. Rode "instalar.bat" primeiro.
    echo.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

echo.
echo Iniciando o SIG View...
echo Deixe esta janela aberta enquanto estiver usando o mapa.
echo.

start "" http://localhost:8000
uvicorn app.main:app --port 8000
