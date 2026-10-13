@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==============================================
echo   Investigador local - instalacion
echo ==============================================
where python >nul 2>nul
if errorlevel 1 (
  echo No encontre Python. Instalalo desde https://www.python.org/downloads/
  echo y marca la casilla "Add python.exe to PATH". Luego vuelve a ejecutar este archivo.
  pause
  exit /b 1
)
if not exist ".venv" (
  echo Creando entorno...
  python -m venv .venv
)
echo Instalando dependencias...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 ( echo Fallo la instalacion de dependencias. & pause & exit /b 1 )
if not exist "biblioteca" mkdir biblioteca

echo.
echo Programando la busqueda diaria (7:00 a. m.)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0programar_tarea.ps1"
if errorlevel 1 (
  echo No se pudo crear la tarea programada. Puedes buscar manualmente desde la app.
) else (
  echo Listo: se buscara automaticamente cada dia a las 7:00 a. m.
  echo Si el PC esta apagado a esa hora, la busqueda corre apenas lo enciendas.
)
echo.
echo Instalacion terminada. Abre la app con iniciar.bat
pause
