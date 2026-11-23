"""Lector de eleventa (Firebird). SOLO LECTURA, incremental por ID (CLAUDE.md regla 1 y 4)."""
import os
from datetime import datetime

import fdb

ARTICULOS = """
SELECT a.ID, a.TICKET_ID, TRIM(a.PRODUCTO_CODIGO), a.PRODUCTO_NOMBRE, a.CANTIDAD, a.TOTAL_ARTICULO,
       a.AGREGADO_EN, a.FUE_DEVUELTO, t.FOLIO, t.CAJA_ID, t.CAJERO_ID,
       COALESCE(t.PAGADO_EN, t.VENDIDO_EN), t.FORMA_PAGO, t.ESTA_CANCELADO
FROM VENTATICKETS_ARTICULOS a JOIN VENTATICKETS t ON t.ID = a.TICKET_ID
WHERE a.ID > ? ORDER BY a.ID"""
CAMPOS = ("id", "ticket_id", "codigo", "nombre", "cantidad", "importe", "agregado", "devuelto",
          "folio", "caja", "cajero", "cobrado", "forma_pago", "cancelado")


def conectar(dsn, fb_lib=None, usuario="SYSDBA", clave="masterkey"):
    """fb_lib: fbembed.dll (pruebas) o fbclient (producción). La transacción es de solo lectura."""
    if fb_lib:
        os.environ.setdefault("FIREBIRD", os.path.dirname(fb_lib))
    con = fdb.connect(dsn=dsn, user=usuario, password=clave, charset="WIN1252", fb_library_name=fb_lib)
    con.default_tpb = fdb.ISOLATION_LEVEL_READ_COMMITED_RO
    return con


def articulos(con, desde_id):
    """Renglones vendidos con ID > desde_id, con datos de su ticket. El llamador guarda el último ID visto."""
    cur = con.cursor()
    cur.execute(ARTICULOS, (desde_id,))
    for r in cur:
        d = dict(zip(CAMPOS, r))
        d["importe"] = round(d["importe"] or 0, 2)  # eleventa guarda float
        d["devuelto"] = d["devuelto"] == "t"
        d["cancelado"] = d["cancelado"] == "t"
        yield d


def primer_id_desde(con, fecha):
    """Último ID anterior a `fecha` (para usar como desde_id). AGREGADO_EN no tiene índice, pero crece con el ID:
    búsqueda binaria con ~50 lecturas por llave primaria, segura en horario de venta (barrer la tabla tarda 10 s).
    ponytail: si algún renglón quedó con hora desordenada, el error es de unos cuantos renglones; se cubre con margen."""
    cur = con.cursor()

    def siguiente(id_):  # (ID, AGREGADO_EN) del primer renglón con ID >= id_, o None. Hora vacía (2010) = antigua.
        cur.execute("SELECT FIRST 1 ID, AGREGADO_EN FROM VENTATICKETS_ARTICULOS WHERE ID >= ? ORDER BY ID", (id_,))
        r = cur.fetchone()
        return r and (r[0], r[1] or datetime.min)

    alto = 1
    while (r := siguiente(alto)) and r[1] < fecha:
        alto *= 2
    bajo = 0  # invariante: todo renglón con ID <= bajo es anterior a `fecha`
    while bajo + 1 < alto:
        medio = (bajo + alto) // 2
        r = siguiente(medio)
        if r and r[1] < fecha:
            bajo = r[0]
        else:
            alto = medio
    return bajo
