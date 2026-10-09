@echo off
cd /d "%~dp0"
echo Instalando dependencias (so demora na primeira vez)...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo ERRO na instalacao. Tire um print desta janela e me envie.
  pause
  exit /b 1
)
set /p APP_PASSWORD=Defina uma senha para esta sessao (ou Enter para acesso aberto): 
echo.
echo Servidor iniciando... o navegador abre sozinho em alguns segundos.
echo NAO feche esta janela enquanto estiver usando o sistema.
start /b cmd /c "timeout /t 5 >nul & start http://127.0.0.1:5000"
python app.py
echo.
echo O servidor parou. Veja a mensagem acima.
pause
