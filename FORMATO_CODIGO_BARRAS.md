# Especificación del Formato de Código de Barras - Sistema de Control de Tickets

## Formato Compacto Recomendado (Code128)

### Estructura Compacta:
```
HHMMSS-FFF-MMMM.CC
```

### Componentes:
- **HHMMSS**: Hora, minutos y segundos (6 dígitos)
  - HH = Hora (00-23)
  - MM = Minutos (00-59)
  - SS = Segundos (00-59)
- **FFF**: Folio consecutivo (3 dígitos, 001-999)
- **MMMM.CC**: Monto en pesos (hasta 9999.99)

### Ejemplos de códigos válidos:
```
143025-001-0125.50
143127-002-0089.75
143230-003-0067.80
143445-004-0156.90
```

## Implementación en tu App de Impresión

### Código ejemplo (JavaScript/Python):
```javascript
// JavaScript
function generarCodigoBarras(folio, monto) {
    const now = new Date();
    const hora = now.getHours().toString().padStart(2, '0') +
                now.getMinutes().toString().padStart(2, '0') +
                now.getSeconds().toString().padStart(2, '0');
    const folioStr = folio.toString().padStart(3, '0');
    const montoStr = parseFloat(monto).toFixed(2).padStart(7, '0');
    return `${hora}-${folioStr}-${montoStr}`;
}
```

```python
# Python
from datetime import datetime

def generar_codigo_barras(folio, monto):
    now = datetime.now()
    hora = now.strftime("%H%M%S")
    folio_str = str(folio).zfill(3)
    monto_str = f"{float(monto):07.2f}"
    return f"{hora}-{folio_str}-{monto_str}"
```

### Código ejemplo (C#):
```csharp
// C#
public static string GenerarCodigoBarras(int folio, decimal monto)
{
    string hora = DateTime.Now.ToString("HHmmss");
    string folioStr = folio.ToString("000");
    string montoStr = monto.ToString("0000.00");
    return $"{hora}-{folioStr}-{montoStr}";
}
```

## Ventajas de este formato:

✅ **Muy compacto**: Solo 18 caracteres
✅ **Legible y rápido de imprimir**
✅ **Compatible con Code128 y lectores POS**
✅ **Suficiente para control interno**

## Configuración del Sistema

El sistema debe actualizarse para este formato:
- Hora: `(\d{6})` (6 dígitos consecutivos)
- Folio: `-(\d{3})-` (3 dígitos entre guiones)
- Monto: `-(\d{4}\.\d{2})` (formato XXXX.XX)

## Implementación para diferentes plataformas:

### Para impresoras térmicas (ESC/POS):
```
[Código de barras Code128]: 143025-001-0125.50
[Texto legible]: Folio: 001 - $125.50 - 14:30
```

### Para sistemas web:
```html
<!-- Usando librerías como JsBarcode -->
<canvas id="barcode"></canvas>
<script>
JsBarcode("#barcode", "143025-001-0125.50", {
    format: "CODE128",
    width: 2,
    height: 100
});
</script>
```

## Gestión de folios consecutivos:

Recomendación para tu app:
1. **Mantener contador diario**: Reiniciar folio cada día (001-999)
2. **Backup del contador**: Guardar último folio usado
3. **Validación**: Verificar que no se salte ningún número

### Ejemplo de contador:
```javascript
// Obtener próximo folio del día
function obtenerProximoFolio() {
    const hoy = new Date().toDateString();
    let ultimoFolio = localStorage.getItem(`folio_${hoy}`) || 0;
    ultimoFolio++;
    localStorage.setItem(`folio_${hoy}`, ultimoFolio);
    return ultimoFolio;
}
```

## Pruebas recomendadas:

Antes de implementar en producción, prueba estos códigos:
```
120000-001-0050.00
120100-002-0075.25
120200-003-0100.50
120300-005-0125.75  // Omitir 004 intencionalmente
120400-006-0150.00
120500-004-0080.00  // 004 llegando tarde
```

¿Te parece bien este formato? ¿Necesitas el código para otra plataforma?