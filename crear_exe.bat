@echo off
echo Creando ejecutable del Sistema de Tickets...

REM Activar entorno virtual
call .venv\Scripts\activate.bat

REM Instalar PyInstaller si no está instalado
pip install pyinstaller

REM Usar icono solo si existe para evitar fallos
set ICON_OPTS=
if exist "ticket.ico" (
	set ICON_OPTS=--icon=ticket.ico
) else (
	echo (Sin ticket.ico, se generará sin icono)
)

REM Crear el ejecutable
pyinstaller --onefile --windowed --name "SistemaTickets" %ICON_OPTS% gui_app.py

echo.
echo ¡Ejecutable creado exitosamente!
echo Ubicación: dist\SistemaTickets.exe
echo.
pause