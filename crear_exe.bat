@echo off
echo Creando ejecutable del Sistema de Tickets...

REM Activar entorno virtual
call .venv\Scripts\activate.bat

REM Instalar PyInstaller si no está instalado
pip install pyinstaller

REM Crear el ejecutable
pyinstaller --onefile --windowed --name "SistemaTickets" --icon=ticket.ico gui_app.py

echo.
echo ¡Ejecutable creado exitosamente!
echo Ubicación: dist\SistemaTickets.exe
echo.
pause