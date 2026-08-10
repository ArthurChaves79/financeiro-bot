@echo off
REM ============================================================
REM  SIG View - instalacao (rodar 1 vez so)
REM  De um duplo-clique neste arquivo.
REM ============================================================
title SIG View - Instalando...
cd /d "%~dp0backend"

echo.
echo === Verificando se o Python esta instalado ===
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERRO] Python nao foi encontrado.
    echo Instale o Python primeiro: https://www.python.org/downloads/windows
    echo IMPORTANTE: na tela de instalacao, marque a caixa "Add python.exe to PATH"
    echo antes de clicar em "Install Now".
    echo.
    pause
    exit /b 1
)

echo.
echo === Criando ambiente isolado (.venv) ===
python -m venv .venv

echo.
echo === Instalando dependencias ===
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo === Criando arquivo de configuracao (.env) ===
if not exist .env (
    copy .env.example .env >nul
    echo Criado backend\.env - ajuste os enderecos da rede quando tiver o servidor de mapas pronto.
) else (
    echo .env ja existia, mantido como estava.
)

echo.
echo === Gerando dados de exemplo (para testar) ===
python scripts\seed_sample_data.py

echo.
echo ==================================================
echo  Instalacao concluida!
echo  Agora use o arquivo "iniciar.bat" para abrir o SIG View.
echo ==================================================
echo.
pause
