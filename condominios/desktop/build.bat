@echo off
setlocal
cd /d %~dp0

echo === Instalando dependencias ===
pip install -r requirements.txt
if errorlevel 1 goto :erro

echo.
echo === Gerando o executavel (PyInstaller) ===
pyinstaller --onefile --windowed --noconfirm --name "SIG Condominios" ^
  --add-data "..\index.html;." ^
  --add-data "..\styles.css;." ^
  --add-data "..\app.js;." ^
  app.py
if errorlevel 1 goto :erro

echo.
echo === Pronto ===
echo Executavel gerado em: %~dp0dist\SIG Condominios.exe
pause
goto :fim

:erro
echo.
echo Ocorreu um erro durante o build. Veja a mensagem acima.
pause

:fim
