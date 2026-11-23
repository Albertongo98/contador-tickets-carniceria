# Contador de Tickets 2.0 · Carnicería La Palma

Programa de la **caja** que vigila que cada ticket de la carnicería llegue a la caja y se cobre. Cruza tres testigos
del mismo ticket:

| Testigo | Qué sabe |
|---|---|
| **CarniceriaApp** (tablet, vía PalmApp/Firestore) | qué tickets se imprimieron, a qué hora exacta, cuáles se anularon |
| **Este Contador** | qué control (`HHmmss-folio`, al pie del ticket) se escaneó en la caja |
| **eleventa** (punto de venta, solo lectura) | si los productos de ese ticket se cobraron |

Si algo no cuadra, sale una alarma con la **ventana de cámaras** (hora real de impresión), una luz roja en el widget
y una **notificación urgente a la dueña** en PalmApp.

> Cómo se conecta con los demás programas de La Palma: `Desktop\PalmaBridge\CONEXIONES.md`.

## Ventanas
- **Widget** (abre al iniciar Windows): tarjeta flotante, siempre encima, translúcida en reposo. La cajera le da clic,
  escanea el ticket y el programa le **regresa el foco a eleventa solo** (el mismo lector sirve para los dos).
  Muestra los tickets en camino y una **luz roja** si hay algo por revisar (clic → Tablero). No suena.
- **Ventana completa** (⤢ en el widget):
  - *Escáner*: barra de escaneo, **pendientes por escanear** y **en qué ticket vamos**.
  - *Tablero*: por revisar en cámaras, lista del día, estado de las fuentes, imprimir reporte, abrir con Windows.
  Cerrarla regresa al widget; "Cerrar programa" (con confirmación) lo cierra de verdad.

## Estados de un ticket
| Estado | Significa | ¿Alarma? |
|---|---|---|
| OK | control escaneado (y cobrado) | no |
| COBRADO | cobrado en eleventa sin escanear el control | no |
| ANULADO | anulado en la tablet | no |
| EN CAMINO | impreso hace menos de 15 min | no |
| **FALTANTE** | ni escaneado ni cobrado | **sí** |
| **SIN COBRO** | escanearon el control pero no se cobró | **sí** |
| REVISADO | la alarma se resolvió: *Revisado*, *Corregido* o *Cancelado* (un clic en el Tablero) | no |

Sin internet funciona como el Contador de siempre (huecos en la secuencia de folios). Sin eleventa, lo no escaneado
sale FALTANTE y **no** se avisa a la dueña (serían avisos falsos).

## Instalar en la caja (portable, sin instalador)
1. Copiar la carpeta `SistemaTickets` (o descomprimir `ContadorTickets_2.0_portable.zip`) a, por ejemplo,
   `C:\ContadorTickets`, y abrir `SistemaTickets.exe`. La primera vez se registra para **abrir con Windows** (se puede
   apagar en el Tablero). Solo abre una vez aunque lo abran dos veces.
2. Tablero → **🔗 Conectar con PalmApp** → nombre y PIN de administración o de la dueña (una sola vez).
3. Listo. Los datos de la caja viven en `%APPDATA%\ContadorTickets\` (`config.json`, `contador.db`, sesión de PalmApp):
   mover o reemplazar el programa no los borra.

Requisitos: Windows 10/11 de 64 bits con **WebView2** (Windows 11 ya lo trae) y el servidor Firebird de eleventa en la
misma PC.

## `config.json`
Ver `config.ejemplo.json`. El de la caja tiene la API key de Firebase y **no se sube** (este repo es público).

| Campo | Para qué |
|---|---|
| `api_key` | API key de Firebase (`google-services.json` de PalmApp o CarniceriaApp) |
| `eleventa` | `127.0.0.1:C:\...\PDVDATA.FDB` — **siempre por el servidor**; abrir el archivo directo bloquearía la caja |
| `fbclient` | cliente de Firebird, relativo al programa (`firebird\fbembed.dll`) |
| `transparencia_widget` | 0.3 (muy transparente) a 1.0 (opaco). Por omisión 0.82 |
| `regresar_foco` | `false` para no regresar a eleventa después de escanear |
| `vista_inicial` | ventana completa: `escaner` o `tablero` |

## Desarrollo
```
pip install -r requirements.txt
python test_verificar.py          # pruebas sin internet ni eleventa
python app.py [--completa]        # widget (o ventana completa)
pyinstaller SistemaTickets.spec   # → dist\SistemaTickets\ (portable)
```
- La carpeta `firebird\` (cliente Firebird 2.5 x64: `fbembed.dll`, `firebird.msg`, `icu*`, `msvc*80`, `intl\`) no
  está en el repo: copiarla de `eleventa-pruebas\fb25`.
- `conciliar.py` y `eleventa.py` son copia de **PalmaBridge** (fuente de verdad): se cambian allá y se copian aquí.
- Interfaz: `ui/index.html` (HTML/CSS/JS, paleta de PalmApp y abarroteslapalma.com) en ventana nativa con pywebview +
  WebView2. Lógica: `app.py` (API para la página, ventanas, foco), `verificar.py` (cruce), `registro.py` (SQLite),
  `palmapp.py` (Firestore REST, solo librería estándar).

Historia: v1 (oct-2025 → feb-2026) en Tkinter, solo con la secuencia de folios escaneados; ver el historial de git.
