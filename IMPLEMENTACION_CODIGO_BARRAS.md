# IMPLEMENTACIÓN DEL CÓDIGO DE BARRAS - GUÍA TÉCNICA

## 📋 FORMATO ESTÁNDAR DEFINIDO

**Estructura:** `YYYYMMDDHHMMSS-FFF-MMMM.CC`

### Ejemplo real: `20251013143025-001-0125.50`
- `20251013143025` = 13 de Octubre 2025, 14:30:25
- `001` = Folio número 1 del día
- `0125.50` = Monto $125.50

## 💻 CÓDIGO PARA DIFERENTES PLATAFORMAS

### JavaScript (Navegadores/Node.js)
```javascript
function generarCodigoTicket(folio, monto) {
    const now = new Date();
    
    // Formatear fecha y hora YYYYMMDDHHMMSS
    const fecha = now.getFullYear().toString() +
                  (now.getMonth() + 1).toString().padStart(2, '0') +
                  now.getDate().toString().padStart(2, '0') +
                  now.getHours().toString().padStart(2, '0') +
                  now.getMinutes().toString().padStart(2, '0') +
                  now.getSeconds().toString().padStart(2, '0');
    
    // Formatear folio (001-999)
    const folioStr = folio.toString().padStart(3, '0');
    
    // Formatear monto (0000.00)
    const montoStr = parseFloat(monto).toFixed(2).padStart(7, '0');
    
    return `${fecha}-${folioStr}-${montoStr}`;
}

// EJEMPLO DE USO:
let codigo1 = generarCodigoTicket(1, 125.50);   // "20251013143025-001-0125.50"
let codigo2 = generarCodigoTicket(45, 89.75);   // "20251013143026-045-0089.75"
```

### Python
```python
from datetime import datetime

def generar_codigo_ticket(folio, monto):
    now = datetime.now()
    
    # Formatear fecha y hora
    fecha = now.strftime("%Y%m%d%H%M%S")
    
    # Formatear folio (001-999)
    folio_str = str(folio).zfill(3)
    
    # Formatear monto (0000.00)
    monto_str = f"{float(monto):07.2f}"
    
    return f"{fecha}-{folio_str}-{monto_str}"

# EJEMPLO DE USO:
codigo1 = generar_codigo_ticket(1, 125.50)   # "20251013143025-001-0125.50"
codigo2 = generar_codigo_ticket(45, 89.75)   # "20251013143026-045-0089.75"
```

### C# (.NET)
```csharp
using System;

public class GeneradorCodigos 
{
    public static string GenerarCodigoTicket(int folio, decimal monto)
    {
        DateTime now = DateTime.Now;
        
        // Formatear fecha y hora
        string fecha = now.ToString("yyyyMMddHHmmss");
        
        // Formatear folio (001-999)
        string folioStr = folio.ToString("000");
        
        // Formatear monto (0000.00)
        string montoStr = monto.ToString("0000.00");
        
        return $"{fecha}-{folioStr}-{montoStr}";
    }
}

// EJEMPLO DE USO:
string codigo1 = GeneradorCodigos.GenerarCodigoTicket(1, 125.50m);   // "20251013143025-001-0125.50"
string codigo2 = GeneradorCodigos.GenerarCodigoTicket(45, 89.75m);   // "20251013143026-045-0089.75"
```

### PHP
```php
<?php
function generarCodigoTicket($folio, $monto) {
    // Formatear fecha y hora
    $fecha = date('YmdHis');
    
    // Formatear folio (001-999)
    $folioStr = str_pad($folio, 3, '0', STR_PAD_LEFT);
    
    // Formatear monto (0000.00)
    $montoStr = str_pad(number_format($monto, 2, '.', ''), 7, '0', STR_PAD_LEFT);
    
    return "{$fecha}-{$folioStr}-{$montoStr}";
}

// EJEMPLO DE USO:
$codigo1 = generarCodigoTicket(1, 125.50);   // "20251013143025-001-0125.50"
$codigo2 = generarCodigoTicket(45, 89.75);   // "20251013143026-045-0089.75"
?>
```

## 🔧 GESTIÓN DE FOLIOS CONSECUTIVOS

### JavaScript (LocalStorage para web)
```javascript
class ManejadorFolios {
    static obtenerProximoFolio() {
        const hoy = new Date().toDateString();
        const key = `folio_${hoy}`;
        let ultimoFolio = parseInt(localStorage.getItem(key) || '0');
        ultimoFolio++;
        localStorage.setItem(key, ultimoFolio.toString());
        return ultimoFolio;
    }
    
    static generarTicketCompleto(monto) {
        const folio = this.obtenerProximoFolio();
        return generarCodigoTicket(folio, monto);
    }
}

// EJEMPLO DE USO:
let ticket1 = ManejadorFolios.generarTicketCompleto(125.50);  // Folio automático
let ticket2 = ManejadorFolios.generarTicketCompleto(89.75);   // Folio siguiente
```

### Para bases de datos (SQL)
```sql
-- Tabla para control de folios diarios
CREATE TABLE folios_diarios (
    fecha DATE PRIMARY KEY,
    ultimo_folio INT DEFAULT 0
);

-- Función para obtener próximo folio
DELIMITER $$
CREATE FUNCTION obtener_proximo_folio() RETURNS INT
READS SQL DATA
BEGIN
    DECLARE nuevo_folio INT;
    DECLARE fecha_hoy DATE DEFAULT CURDATE();
    
    -- Obtener y actualizar folio
    INSERT INTO folios_diarios (fecha, ultimo_folio) 
    VALUES (fecha_hoy, 1) 
    ON DUPLICATE KEY UPDATE ultimo_folio = ultimo_folio + 1;
    
    SELECT ultimo_folio INTO nuevo_folio 
    FROM folios_diarios 
    WHERE fecha = fecha_hoy;
    
    RETURN nuevo_folio;
END$$
DELIMITER ;
```

## 📱 IMPLEMENTACIÓN PARA DIFERENTES SISTEMAS

### Para sistemas POS (Punto de Venta)
```javascript
// Integración típica con sistema POS
class TicketPOS {
    constructor() {
        this.impresoraTermica = new ImpresoraTermica();
    }
    
    imprimirTicket(productos, total) {
        // Generar código de barras
        const folio = ManejadorFolios.obtenerProximoFolio();
        const codigoBarras = generarCodigoTicket(folio, total);
        
        // Imprimir ticket con código
        this.impresoraTermica.texto(`Folio: ${folio.toString().padStart(3, '0')}`);
        this.impresoraTermica.texto(`Total: $${total.toFixed(2)}`);
        this.impresoraTermica.codigoBarras(codigoBarras, 'CODE128');
        this.impresoraTermica.texto(codigoBarras); // Texto legible
        this.impresoraTermica.cortar();
    }
}
```

### Para aplicaciones móviles (React Native)
```javascript
import { generateBarCode } from 'react-native-barcode-generator';

class TicketMovil {
    async generarTicketConCodigo(monto) {
        const folio = await this.obtenerProximoFolio();
        const codigo = generarCodigoTicket(folio, monto);
        
        // Generar imagen del código de barras
        const imagenCodigo = await generateBarCode({
            value: codigo,
            format: 'CODE128',
            width: 300,
            height: 100
        });
        
        return {
            folio,
            codigo,
            monto,
            imagenCodigo
        };
    }
}
```

## ✅ VALIDACIÓN Y PRUEBAS

### Casos de prueba recomendados:
```javascript
// CASOS DE PRUEBA
const casosPrueba = [
    { folio: 1, monto: 125.50, esperado: /^\d{14}-001-0125\.50$/ },
    { folio: 999, monto: 9999.99, esperado: /^\d{14}-999-9999\.99$/ },
    { folio: 45, monto: 0.01, esperado: /^\d{14}-045-0000\.01$/ }
];

casosPrueba.forEach(caso => {
    const codigo = generarCodigoTicket(caso.folio, caso.monto);
    console.assert(caso.esperado.test(codigo), `Falló: ${codigo}`);
});
```

### Validador de formato:
```javascript
function validarCodigoBarras(codigo) {
    const regex = /^(\d{14})-(\d{3})-(\d{4}\.\d{2})$/;
    const match = codigo.match(regex);
    
    if (!match) return { valido: false, error: "Formato incorrecto" };
    
    const [, fecha, folio, monto] = match;
    
    // Validar componentes
    if (parseInt(folio) < 1 || parseInt(folio) > 999) {
        return { valido: false, error: "Folio fuera de rango" };
    }
    
    if (parseFloat(monto) <= 0 || parseFloat(monto) > 9999.99) {
        return { valido: false, error: "Monto fuera de rango" };
    }
    
    return { valido: true, fecha, folio: parseInt(folio), monto: parseFloat(monto) };
}
```

## 🚀 PRÓXIMOS PASOS PARA IMPLEMENTAR

1. **Elegir el código según tu plataforma** (JavaScript, C#, Python, etc.)
2. **Integrar en tu app de impresión** existente
3. **Implementar control de folios** (base de datos o localStorage)
4. **Probar con códigos de ejemplo** antes de producción
5. **Configurar impresora** para códigos Code128
6. **Comenzar a usar** con el sistema de control de tickets

**¿En qué plataforma está desarrollada tu app de impresión?** Te ayudo con la implementación específica.