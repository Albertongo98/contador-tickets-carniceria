# Sistema de Control de Tickets para Carnicería

## Descripción
Sistema desarrollado en Python para controlar y organizar tickets de productos despachados en área de carnicería, con detección automática de tickets faltantes y gestión de turnos.

## Características principales
- ✅ Lectura automática de códigos de barras Code128
- ✅ Detección inteligente de tickets faltantes
- ✅ Sistema visual de confirmación (verde/amarillo)
- ✅ Gestión de turnos (mañana/tarde)
- ✅ Reportes de cierre de caja
- ✅ Sugerencias de horarios para revisar cámaras
- ✅ Interfaz simple y eficiente

## Formato de código de barras soportados
El sistema detecta automáticamente múltiples formatos:
- Fecha/hora: `2025-10-13T14:30:25`, `13/10/2025 14:30:25`, `20251013143025`
- Folio: 3 dígitos (001-999)
- Monto: formato decimal con 2 decimales

## Instalación

### Opción 1: Usar ejecutable (.exe)
1. Ejecutar `crear_exe.bat`
2. Usar el archivo `dist/SistemaTickets.exe`

### Opción 2: Ejecutar desde Python
1. Instalar dependencias: `pip install -r requirements.txt`
2. Ejecutar: `python gui_app.py`

## Uso del sistema

### Escaneo de tickets
1. Enfocar el campo de entrada
2. Escanear código de barras (se procesa automáticamente)
3. Observar pantalla de confirmación:
   - **Verde**: Ticket registrado correctamente
   - **Amarillo**: Advertencia de posible ticket faltante

### Botones principales
- **Ver Resumen**: Muestra tickets faltantes y horarios sugeridos para cámaras
- **Cierre de Caja**: Finaliza turno, genera reporte y resetea contador

### Lógica de detección de faltantes
- Monitorea secuencia de folios
- Muestra amarillo solo durante 3 tickets después de detectar faltante
- Si aparece el ticket faltante, vuelve a flujo normal
- Evita "ruido" excesivo al cajero

## Archivos generados
- `tickets_data.json`: Datos persistentes del sistema
- `cierre_mañana_YYYYMMDD.txt`: Reportes de cierre matutino
- `cierre_tarde_YYYYMMDD.txt`: Reportes de cierre vespertino

## Estructura del proyecto
```
Contador de Tickets/
├── ticket_manager.py    # Lógica principal de tickets
├── gui_app.py          # Interfaz gráfica
├── requirements.txt    # Dependencias
├── crear_exe.bat      # Script para crear ejecutable
├── README.md          # Esta documentación
└── .venv/            # Entorno virtual Python
```

## Consideraciones técnicas
- Desarrollado para Windows con PowerShell
- Interfaz optimizada para uso con lector de códigos de barras
- Persistencia automática de datos
- Manejo robusto de errores

## Contacto y soporte
Sistema desarrollado para optimizar el control de inventario y prevenir robos en área de carnicería.

---
*Fecha de creación: Octubre 2025*