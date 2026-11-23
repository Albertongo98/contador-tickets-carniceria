"""python test_verificar.py — sin internet, sin eleventa, sin ventana."""
from datetime import date, datetime

from conciliar import ZONA_TIENDA
from registro import Registro
from verificar import (ANULADO_TABLET, COBRADO_SIN_CONTROL, EN_CAMINO, FALTANTE, OK, REVISADO, SIN_COBRO,
                       de_firestore, revisar)

J = lambda hhmm: datetime(2026, 11, 22, *map(int, hhmm.split(":")))         # hora de Juárez
ms = lambda hhmm: int(J(hhmm).replace(tzinfo=ZONA_TIENDA).timestamp() * 1000)
_id = iter(range(1, 999))


def fs(folio, hhmm, *items, anulado=False):  # como lo sube CarniceriaApp
    return {"id": folio, "folio": f"{folio:03d}", "hora": ms(hhmm), "control": "x", "total": sum(m for _, m in items),
            "anulado": anulado, "motivoAnulado": "error de peso" if anulado else None,
            "renglones": [{"codigo": c, "nombre": c, "unidad": "GRANEL", "cantidad": 1, "importe": m} for c, m in items]}


def caja(ticket, hhmm_caja, codigo, importe):  # renglón de eleventa (reloj de la caja: 1 h atrás de Juárez)
    return {"id": next(_id), "ticket_id": ticket, "folio": 2100000 + ticket, "caja": 1, "cajero": 52, "forma_pago": "e",
            "codigo": codigo, "importe": importe, "agregado": J(hhmm_caja), "cancelado": False}


tablet = [de_firestore(t) for t in [
    fs(1, "09:00", ("1098", 71.0)),                 # escaneado y cobrado
    fs(2, "09:10", ("1091", 50.0)),                 # cobrado, faltó escanear el control
    fs(3, "09:20", ("1056", 120.0)),                # ni escaneado ni cobrado → FALTANTE
    fs(4, "09:25", ("1078", 85.0)),                 # escaneado, pero no se cobró → SIN COBRO
    fs(5, "09:30", ("1019", 10.0), anulado=True),   # anulado en la tablet
    fs(6, "09:35", ("1090", 60.0)),                 # faltante ya revisado por el gerente
    fs(7, "09:50", ("1072", 20.0)),                 # recién impreso → EN CAMINO
]]
assert tablet[0]["folio"] == 1 and tablet[0]["hora"] == J("09:00")
renglones = [caja(1, "08:01", "1098", 71.0), caja(2, "08:12", "1091", 50.0), caja(9, "08:40", "1099", 9.0)]
escaneados = {1, 4}
revisados = {6: ("Corregido", "10:05")}

filas = revisar(tablet, escaneados, renglones, J("10:00"), J("09:00"), revisados)
estado = {f["folio"]: f["estado"] for f in filas}
assert estado == {1: OK, 2: COBRADO_SIN_CONTROL, 3: FALTANTE, 4: SIN_COBRO, 5: ANULADO_TABLET, 6: REVISADO,
                  7: EN_CAMINO}, estado
assert [f["folio"] for f in filas] == [7, 6, 5, 4, 3, 2, 1]                      # lo más reciente arriba
f3 = next(f for f in filas if f["folio"] == 3)
assert f3["camaras"] == "09:19 – 09:35" and f3["hora"] == "09:20:00", f3      # hora real (Juárez), no la de la caja
assert "caja 1" in next(f for f in filas if f["folio"] == 2)["detalle"]
f6 = next(f for f in filas if f["folio"] == 6)
assert f6["resolucion"] == "Corregido" and f6["detalle"].startswith("Corregido a las 10:05"), f6

# Sin eleventa: lo no escaneado y viejo es FALTANTE (no se puede saber si se cobró).
estado = {f["folio"]: f["estado"] for f in revisar(tablet, escaneados, None, J("10:00"), J("09:00"))}
assert estado[2] == FALTANTE and estado[4] == OK and estado[7] == EN_CAMINO

# Sin internet: huecos en la secuencia de lo escaneado, como el Contador de siempre.
filas = revisar(None, {1, 2, 5}, None, J("10:00"), J("09:00"))
assert [(f["folio"], f["estado"]) for f in filas] == [(5, OK), (4, FALTANTE), (3, FALTANTE), (2, OK), (1, OK)]

# Registro: un control no cuenta dos veces; revisiones y avisos por día.
r = Registro(":memory:")
hoy = date(2026, 11, 22)
assert r.escanear(hoy, 46, J("10:00"), "100000-046") and not r.escanear(hoy, 46, J("10:01"), "100000-046")
assert r.escaneados(hoy) == {46} and r.escaneados(date(2026, 11, 23)) == set()
r.revisar(J("10:05"), 3, "Cancelado")
assert r.revisados(hoy) == {3: ("Cancelado", "10:05")}
r.avisado(hoy, 3)
assert r.avisados(hoy) == {3}
print("ok")
