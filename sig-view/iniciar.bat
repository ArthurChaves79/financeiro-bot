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
echo Se abrir numa janela propria do programa, pode ignorar esta janela preta
echo (ela so precisa continuar aberta por baixo). Se abrir no navegador em vez
echo disso, ai sim precisa deixar esta janela aberta enquanto usa o mapa.
echo.

python run.py
