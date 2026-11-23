"""Detección de tickets de carnicería faltantes: cruza tres testigos del mismo ticket.

  tablet (PalmApp/Firestore)  → qué tickets se imprimieron, a qué hora exacta y cuáles se anularon
  este Contador               → qué control (HHmmss-folio) se escaneó en la caja
  eleventa (solo lectura)     → si sus productos se cobraron

Si falta internet o eleventa, se usa lo que haya. `conciliar.py` y `eleventa.py` son copia de PalmaBridge
(Desktop\\PalmaBridge): cambiarlos allá y copiarlos aquí.
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta

from conciliar import ANULADO, NO_COBRADO, PENDIENTE, ZONA_TIENDA, a_hora_tienda, conciliar

GRACIA = timedelta(minutes=3)        # Tablero en rojo. Imprimir → cobrar (8,159 tickets sep–nov 2026): mediana 1.2 min,
                                     # p90 2.8, p95 3.6: ~11 al día pasan de 3 min, se quitan solos al cobrarse.
AVISO_DUENA = timedelta(minutes=8)   # notificación a la dueña (no se retira): >8 min solo 0.6 % (<1 falsa al día).
CAMARAS_ANTES, CAMARAS_DESPUES = timedelta(minutes=1), timedelta(minutes=15)

OK = "OK"                            # control escaneado (y cobrado, si se pudo revisar eleventa)
COBRADO_SIN_CONTROL = "COBRADO"      # se cobró en eleventa pero no escanearon el control: sin alarma
ANULADO_TABLET = "ANULADO"
EN_CAMINO = "EN CAMINO"              # recién impreso, aún no llega a la caja
FALTANTE = "FALTANTE"                # ni escaneado ni cobrado: revisar cámaras
SIN_COBRO = "SIN COBRO"              # escanearon el control pero sus productos no se cobraron: revisar cámaras
REVISADO = "REVISADO"                # fue alarma y ya se resolvió (Revisado / Corregido / Cancelado)
RESOLUCIONES = ("Revisado", "Corregido", "Cancelado")
ALARMAS = (FALTANTE, SIN_COBRO)


def ahora_juarez():
    return datetime.now(ZONA_TIENDA).replace(tzinfo=None)


def de_firestore(t):
    """Ticket tal como lo sube CarniceriaApp → formato de conciliar()."""
    return {"id": t.get("id"), "folio": int(t["folio"]), "hora": a_hora_tienda(t["hora"]),
            "total": round(t.get("total") or 0, 2), "anulado": bool(t.get("anulado")),
            "motivo": t.get("motivoAnulado") or "",
            "items": [{"codigo": (r.get("codigo") or "").strip(), "nombre": r.get("nombre") or "",
                       "unidad": r.get("unidad"), "cantidad": r.get("cantidad"),
                       "importe": round(r.get("importe") or 0, 2)} for r in t.get("renglones", [])]}


def _fila(folio, estado, hora="", total=None, productos="", detalle="", camaras=""):
    return {"folio": folio, "estado": estado, "hora": hora, "total": total, "productos": productos,
            "detalle": detalle, "camaras": camaras, "resolucion": ""}


def revisar(tablet, escaneados, renglones, ahora, ahora_caja, revisados=None):
    """tablet: tickets de de_firestore() del día (None sin internet). escaneados: folios con control escaneado.
    renglones: de eleventa.articulos (None sin eleventa). ahora: hora de Juárez; ahora_caja: reloj de la caja.
    revisados: {folio: (resolución, hora)}. Devuelve filas ordenadas por folio, del más reciente al más viejo."""
    revisados = revisados or {}
    filas = {}
    if tablet is None:
        # Sin internet: como el Contador de siempre, los huecos en la secuencia de folios escaneados.
        for f in escaneados:
            filas[f] = _fila(f, OK)
        if escaneados:
            for f in range(min(escaneados) + 1, max(escaneados)):
                if f not in escaneados:
                    filas[f] = _fila(f, FALTANTE, detalle="hueco en la secuencia (sin datos de la tablet)")
    else:
        conc = {}
        if renglones is not None:
            codigos = {it["codigo"] for t in tablet for it in t["items"]}
            res, _ = conciliar(tablet, [r for r in renglones if r["codigo"] in codigos], fin_datos=ahora_caja)
            conc = {r["folio"]: r for r in res}
        for t in tablet:
            f, c = t["folio"], conc.get(t["folio"])
            cobrado = c is not None and c["estado"] not in (NO_COBRADO, PENDIENTE, ANULADO)
            viejo = ahora - t["hora"] > GRACIA
            fila = _fila(f, "", t["hora"].strftime("%H:%M:%S"), t["total"],
                         ", ".join(it["nombre"] for it in t["items"]))
            if t["anulado"]:
                fila["estado"] = ANULADO_TABLET
                fila["detalle"] = t["motivo"] + (" (pero escanearon su control)" if f in escaneados else "")
            elif f in escaneados:
                fila["estado"] = SIN_COBRO if (c is not None and not cobrado and viejo) else OK
                if fila["estado"] == SIN_COBRO:
                    fila["detalle"] = "control escaneado, productos NO cobrados en eleventa"
            elif cobrado:
                fila["estado"] = COBRADO_SIN_CONTROL
                cobro = next(x for x in c["cobros"] if x)
                fila["detalle"] = f"cobrado en caja {cobro['caja']} sin escanear el control"
            elif viejo:
                fila["estado"] = FALTANTE
                fila["detalle"] = "no se escaneó el control" + ("" if renglones is None else " ni se cobró")
            else:
                fila["estado"] = EN_CAMINO
            if fila["estado"] in ALARMAS:
                ini, fin = t["hora"] - CAMARAS_ANTES, t["hora"] + CAMARAS_DESPUES
                fila["camaras"] = f"{ini:%H:%M} – {fin:%H:%M}"
            filas[f] = fila
        for f in escaneados:
            filas.setdefault(f, _fila(f, OK, detalle="no aparece en la tablet"))
    for f, (resolucion, hora) in revisados.items():
        if f in filas and filas[f]["estado"] in ALARMAS:
            filas[f]["estado"], filas[f]["resolucion"] = REVISADO, resolucion
            filas[f]["detalle"] = f"{resolucion} a las {hora} · antes: {filas[f]['detalle']}"
    return [filas[f] for f in sorted(filas, reverse=True)]


# --- Lectura de las fuentes (todo con try: nada de esto debe tumbar al Contador) ---------------------------------

def programa():
    """Donde está el programa (exe, firebird\\, config.json de fábrica). Instalado: Archivos de programa, solo lectura."""
    return os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))


def carpeta():
    """Datos de esta caja (config.json, contador.db, sesión de PalmApp). Instalado: %APPDATA%\\ContadorTickets,
    así reinstalar o actualizar no borra nada. Sin instalar (desarrollo): la carpeta del código."""
    if not getattr(sys, "frozen", False):
        return programa()
    d = os.path.join(os.environ.get("APPDATA", programa()), "ContadorTickets")
    os.makedirs(d, exist_ok=True)
    return d


def config():
    ruta = os.path.join(carpeta(), "config.json")
    if not os.path.exists(ruta) and os.path.exists(os.path.join(programa(), "config.json")):
        import shutil
        shutil.copy(os.path.join(programa(), "config.json"), ruta)  # primera vez: la de fábrica
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def guardar_config(cfg):
    with open(os.path.join(carpeta(), "config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


_desde_id = {}  # fecha → último ID de eleventa antes de ese día (la búsqueda tarda ~3 s: una vez al día)


SERVIDOR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-]*(/\d{1,5})?$")  # IP o nombre de la PC, puerto opcional: 192.168.1.10/3050


def dsn_eleventa(servidor, ruta):
    """Pantalla Configuración → valor de config.json 'eleventa'. ValueError con el mensaje para la pantalla."""
    servidor, ruta = servidor.strip(), ruta.strip()
    if not SERVIDOR.match(servidor) or len(servidor) == 1:  # una letra sola sería un disco (C:): archivo directo
        raise ValueError("Escribe la IP o el nombre de la PC donde está eleventa (ej. 127.0.0.1 o 192.168.1.10)")
    if not re.match(r"^[A-Za-z]:\\.+\.FDB$", ruta, re.I):
        raise ValueError("La ruta debe ser la de la base en esa PC, ej. C:\\...\\PDVDATA.FDB")
    return f"{servidor}:{ruta}"


def conectar_eleventa(cfg):
    import eleventa  # aquí: sin fdb el Contador sigue funcionando
    dsn = cfg["eleventa"]
    # Nunca abrir el archivo directo (modo embebido = acceso exclusivo: bloquearía la caja). Siempre por el servidor.
    if len(dsn.split(":", 1)[0]) <= 1 and not cfg.get("solo_pruebas_archivo_directo"):
        raise ValueError("config.json: 'eleventa' debe ser 127.0.0.1:C:\\...\\PDVDATA.FDB (por el servidor)")
    return eleventa.conectar(dsn, os.path.join(programa(), cfg.get("fbclient", r"firebird\fbembed.dll")))


def leer_eleventa(cfg, dia):
    import eleventa
    con = conectar_eleventa(cfg)
    try:
        if dia not in _desde_id:  # margen de 3 h: el reloj de la caja puede ir desfasado
            _desde_id[dia] = eleventa.primer_id_desde(con, datetime.combine(dia, datetime.min.time()) - timedelta(hours=3))
        return list(eleventa.articulos(con, _desde_id[dia]))
    finally:
        con.close()


def cargar(cfg, palmapp, escaneados, revisados, dia=None):
    """Lee tablet y eleventa del día y revisa. Devuelve (filas, fuentes, tablet).
    fuentes = {"tablet": True | mensaje de error, "eleventa": True | mensaje | None (no se intentó)}."""
    ahora = ahora_juarez()
    dia = dia or ahora.date()
    fuentes = {"tablet": "PalmApp no conectado", "eleventa": None}
    tablet = renglones = None
    if palmapp and palmapp.conectado:
        try:
            tablet = [de_firestore(t) for t in palmapp.tickets_del_dia(dia.isoformat())]
            fuentes["tablet"] = True
        except Exception as e:
            fuentes["tablet"] = str(e)
    if tablet is not None and cfg.get("eleventa"):
        try:
            renglones = leer_eleventa(cfg, dia)
            fuentes["eleventa"] = True
        except Exception as e:
            fuentes["eleventa"] = str(e)
    # datetime.now() = reloj de esta PC = el de eleventa (corren en la misma caja).
    filas = revisar(tablet, escaneados, renglones, ahora, datetime.now(), revisados)
    return filas, fuentes, tablet
