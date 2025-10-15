# Manual de Usuario - Sistema de Control de Tickets

## ¿Qué hace este sistema?

Este sistema te ayuda a controlar los tickets de productos despachados en tu carnicería, detectando automáticamente cuando falta algún ticket para prevenir robos.

## Cómo usar el sistema

### 1. Iniciar el programa
- Ejecuta `SistemaTickets.exe` (está en la carpeta `dist`)
- Se abrirá la ventana principal del sistema

### 2. Escanear tickets
- Conecta tu lector de códigos de barras
- Enfoca el campo de entrada (donde dice "Escanear código de barras")
- Escanea cada ticket con el lector
- El sistema procesa automáticamente cada código

### 3. Pantallas de confirmación
- **Verde fosforescente**: Ticket registrado correctamente
- **Amarilla**: Advertencia - posible ticket faltante detectado

### 4. Lógica de advertencias
- Si falta un ticket, aparece pantalla amarilla
- La advertencia se mantiene solo por los siguientes 3 tickets
- Si aparece el ticket faltante, vuelve a verde normal

### 5. Botones principales

#### Ver Resumen
- Muestra si faltan tickets
- Si faltan, indica los folios y horarios sugeridos para revisar cámaras
- Ejemplo: "Folio 045: Revisar cámaras entre 14:20 y 14:35"

#### Cierre de Caja
- Finaliza el turno actual
- Genera reporte automático
- Resetea el contador para el siguiente cajero
- Cambia de turno (mañana ↔ tarde)

## Formatos de código soportados

El sistema reconoce automáticamente estos formatos:
```
2025-10-13T14:30:25_123_99.99     (ISO con separadores)
13/10/2025 14:30:25_124_149.50    (Fecha española)
20251013143025125199.75           (Formato compacto)
```

Donde:
- Fecha y hora del ticket
- Folio de 3 dígitos (001-999)
- Monto con 2 decimales

## Archivos que genera

- `tickets_data.json`: Datos del sistema (no borrar)
- `cierre_mañana_YYYYMMDD.txt`: Reportes de cierre matutino
- `cierre_tarde_YYYYMMDD.txt`: Reportes de cierre vespertino

## Flujo de trabajo diario

### Turno Mañana
1. Abrir sistema
2. Escanear tickets conforme se generen
3. Al finalizar turno, hacer "Cierre de Caja"
4. Revisar reporte generado

### Turno Tarde
1. Sistema automáticamente en turno tarde
2. Contador de tickets reiniciado
3. Repetir proceso de escaneo
4. Cierre de caja al final del día

## Qué hacer si aparece advertencia amarilla

1. **No entrar en pánico** - es solo una advertencia
2. Revisar área de carnicería por tickets sueltos
3. Verificar si algún cliente cambió su pedido
4. Continuar escaneando - si aparece el ticket faltante, vuelve a normal
5. Si persiste, usar "Ver Resumen" para horarios de cámaras

## Instalación en otra computadora

Si necesitas instalar en otra PC:
1. Copia la carpeta completa del proyecto
2. Ejecuta `SistemaTickets.exe` desde la carpeta `dist`
3. No requiere instalar Python ni librerías adicionales

## Respaldo de datos

Recomendado hacer copia de:
- `tickets_data.json` (datos actuales)
- Archivos `cierre_*.txt` (reportes históricos)

---
*Sistema desarrollado para optimizar control de inventario y prevenir pérdidas*