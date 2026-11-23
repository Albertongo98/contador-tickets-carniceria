"""Conciliación carnicería ↔ caja (SDD §4.1).

Por cada ticket despachado en CarniceriaApp busca sus renglones cobrados en eleventa
(mismo código + mismo importe en centavos, dentro de una ventana de tiempo después de imprimir).

Uso:
  python conciliar.py --tablet respaldo.db --eleventa PDVDATA.FDB --fb-lib fbembed.dll --desde 2026-11-01 [--hasta 2026-11-23] [--csv salida.csv]
"""
import argparse
import csv
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from itertools import combinations
from zoneinfo import ZoneInfo

# La tienda está en Cd. Juárez. En Windows necesita el paquete `tzdata`; en Linux/Pi viene con el sistema.
ZONA_TIENDA = ZoneInfo("America/Ciudad_Juarez")
# El reloj de la caja puede no coincidir con Juárez (sep–nov 2026 iba 1 h atrás: tablet 09:17:00 ↔ eleventa
# 08:17:45). El desfase se mide cada día con los datos (estimar_desfase), así un ajuste de reloj no rompe nada.
DESFASES_POSIBLES = [timedelta(hours=h) for h in (0, -1, 1, -2, 2)]  # en orden de preferencia si empatan
VENTANA = timedelta(hours=2)        # máximo entre imprimir en carnicería y escanear en caja
TOLERANCIA = timedelta(minutes=3)   # relojes tablet/caja desfasados
VENTANA_DISTINTO = timedelta(minutes=10)  # mismo producto con otro importe (p99 imprimir→escanear: 6.5 min)
REDONDEO = 0.05                     # eleventa recalcula cantidad×precio en float: $100 → $100.01
MAX_JUNTOS = 4                     # renglones de tablet que eleventa pudo juntar en uno
MAX_CANDIDATOS = 12                 # ponytail: tope para que las combinaciones no exploten (C(12,4)=495)

COBRADO, DISTINTO, PARCIAL, NO_COBRADO, PENDIENTE, ANULADO = (
    "cobrado", "distinto", "parcial", "NO_COBRADO", "pendiente", "anulado")


def a_hora_tienda(ms):
    """Epoch de la tablet → hora de Juárez (la real; la de la caja puede ir desfasada)."""
    return datetime.fromtimestamp(ms / 1000, ZONA_TIENDA).replace(tzinfo=None)


def estimar_desfase(tickets, renglones):
    """Horas enteras que hay que sumar a la hora de la tablet para llegar a la del reloj de la caja: la que más
    renglones (mismo código e importe) deja cobrados entre 3 min antes y 10 min después de imprimir."""
    por_clave = defaultdict(list)
    for r in renglones:
        por_clave[(r["codigo"], centavos(r["importe"]))].append(r["agregado"])
    items = [(t["hora"], por_clave.get((it["codigo"], centavos(it["importe"])), ()))
             for t in tickets if not t["anulado"] for it in t["items"]]

    def aciertos(d):
        return sum(any(h + d - TOLERANCIA <= a <= h + d + VENTANA_DISTINTO for a in horas) for h, horas in items)
    return max(DESFASES_POSIBLES, key=aciertos)  # max() se queda con el primero en empate → 0 h


def centavos(x):
    return round(x * 100)


def cargar_tablet(ruta, desde, hasta):
    """Tickets de CarniceriaApp (respaldo SQLite, Room v5) con su lista de renglones."""
    ms = lambda d: int(d.replace(tzinfo=ZONA_TIENDA).timestamp() * 1000)
    con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    tickets = {}
    for id_, ts, total, folio, anulado in con.execute(
            "SELECT id, timestamp, total_amount, daily_folio, voided_at FROM tickets "
            "WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp", (ms(desde), ms(hasta))):
        tickets[id_] = {"id": id_, "hora": a_hora_tienda(ts), "total": round(total, 2), "folio": folio,
                        "anulado": anulado is not None, "items": []}
    for tid, codigo, nombre, unidad, cantidad, importe in con.execute(
            "SELECT ticket_id, product_code, product_name, unit, quantity, total_price FROM ticket_items ORDER BY id"):
        if tid in tickets:
            tickets[tid]["items"].append({"codigo": (codigo or "").strip(), "nombre": nombre, "unidad": unidad,
                                          "cantidad": cantidad, "importe": round(importe or 0, 2)})
    con.close()
    return list(tickets.values())


def conciliar(tickets, renglones, ventana=VENTANA, tolerancia=TOLERANCIA, fin_datos=None):
    """tickets: de cargar_tablet (hora de Juárez). renglones: de eleventa.articulos (hora del reloj de la caja).
    fin_datos: hasta dónde llegan los datos de eleventa (hora de caja); por omisión, el último renglón.
    Devuelve (resultados por ticket, cobros de caja que no casaron con ningún ticket). Cada resultado trae
    `hora_caja` = hora de impresión vista con el reloj de la caja (desfase medido por día)."""
    fin_datos = fin_datos or max((r["agregado"] for r in renglones), default=datetime.min)
    desfase = {}
    for dia in {t["hora"].date() for t in tickets}:
        del_dia = [t for t in tickets if t["hora"].date() == dia]
        cerca = [r for r in renglones if abs(r["agregado"].date() - dia) <= timedelta(days=1)]
        desfase[dia] = estimar_desfase(del_dia, cerca)
    grupos = agrupar(renglones)
    libres = defaultdict(list)  # (código, centavos) → cobros de caja vigentes, en orden de hora
    cancelados = defaultdict(list)
    for g in sorted(grupos, key=lambda g: g["agregado"]):
        (cancelados if g["cancelado"] else libres)[(g["codigo"], centavos(g["importe"]))].append(g)
    usados = set()  # IDs de cobros de caja ya asignados

    resultados = [{**t, "cobros": [None] * len(t["items"]), "notas": [""] * len(t["items"]),
                   "difs": [0.0] * len(t["items"]), "hora_caja": t["hora"] + desfase[t["hora"].date()]}
                  for t in sorted(tickets, key=lambda t: t["hora"])]
    vigentes = [r for r in resultados if not r["anulado"]]

    # Paso 1: un renglón de tablet = un cobro de caja con el mismo importe. Se asignan primero las parejas
    # cuyo ticket de caja cubre más renglones del ticket de tablet (un cliente = un cobro), luego las más
    # cercanas en hora. Asignar en orden de impresión "al primero libre" provocaba faltantes en cadena.
    # ponytail: heurística codiciosa global; asignación óptima (húngaro) si aparecen cruces raros.
    parejas = []  # (ticket de tablet, índice de renglón, cobro de caja)
    for res in vigentes:
        for i, it in enumerate(res["items"]):
            for g in libres.get((it["codigo"], centavos(it["importe"])), ()):
                if res["hora_caja"] - tolerancia <= g["agregado"] <= res["hora_caja"] + ventana:
                    parejas.append((res, i, g))
    cubre = defaultdict(set)
    for res, i, g in parejas:
        cubre[(res["id"], g["ticket_id"])].add(i)
    parejas.sort(key=lambda p: (-len(cubre[(p[0]["id"], p[2]["ticket_id"])]), abs(p[2]["agregado"] - p[0]["hora_caja"])))
    for res, i, g in parejas:
        if res["cobros"][i] is None and g["id"] not in usados:
            res["cobros"][i] = g
            usados.add(g["id"])

    # Paso 2: eleventa junta en un renglón el mismo producto escaneado varias veces en un ticket
    # (Deshebrada $100 + $100 → un renglón de $200), aunque vengan de tickets distintos de la tablet.
    sueltos = defaultdict(list)  # código → (ticket, índice) sin cobro, en orden de impresión
    for res in vigentes:
        for i, it in enumerate(res["items"]):
            if res["cobros"][i] is None:
                sueltos[it["codigo"]].append((res, i))
    for g in sorted((g for lista in libres.values() for g in lista if g["id"] not in usados),
                    key=lambda g: g["agregado"]):
        cerca = [(res, i) for res, i in reversed(sueltos[g["codigo"]]) if res["cobros"][i] is None
                 and g["agregado"] - ventana <= res["hora_caja"] <= g["agregado"] + tolerancia][:MAX_CANDIDATOS]
        for combo in (c for n in range(2, MAX_JUNTOS + 1) for c in combinations(cerca, n)):
            if sum(centavos(res["items"][i]["importe"]) for res, i in combo) == centavos(g["importe"]):
                for res, i in combo:
                    res["cobros"][i] = g
                usados.add(g["id"])
                break

    # Paso 3: mismo producto, poco después, otro importe: redondeo de eleventa ($100 → $100.01),
    # precio distinto en caja, o etiqueta escaneada dos veces ($20 → $40, se le cobró de más al cliente).
    restantes = defaultdict(list)
    for lista in libres.values():
        for g in lista:
            restantes[g["codigo"]].append(g)
    for res in vigentes:
        for i, it in enumerate(res["items"]):
            if res["cobros"][i] is not None:
                continue
            cerca = [g for g in restantes[it["codigo"]] if g["id"] not in usados
                     and res["hora_caja"] - tolerancia <= g["agregado"] <= res["hora_caja"] + VENTANA_DISTINTO]
            if cerca:
                g = min(cerca, key=lambda g: abs(g["agregado"] - res["hora_caja"]))
                res["cobros"][i] = g
                usados.add(g["id"])
                dif = round(g["importe"] - it["importe"], 2)
                if abs(dif) > REDONDEO:
                    res["difs"][i] = dif
                    res["notas"][i] = f"cobrado ${g['importe']:.2f} ({dif:+.2f})" + (
                        " ¿escaneado 2 veces?" if g["importe"] / it["importe"] in (2, 3) else "")

    # Pistas para lo que quedó sin cobrar: ¿se escaneó en un ticket que luego se canceló?
    for res in vigentes:
        for i, it in enumerate(res["items"]):
            if res["cobros"][i] is None:
                for g in cancelados.get((it["codigo"], centavos(it["importe"])), ()):
                    if res["hora_caja"] - tolerancia <= g["agregado"] <= res["hora_caja"] + ventana:
                        res["notas"][i] = f"escaneado en ticket CANCELADO: caja {g['caja']} folio {g['folio']}"
                        break

    for res in resultados:
        n = sum(c is not None for c in res["cobros"])
        if res["anulado"]:
            res["estado"] = ANULADO
        elif n == len(res["items"]) and n:
            res["estado"] = DISTINTO if any(res["difs"]) else COBRADO
        elif n:
            res["estado"] = PARCIAL
        elif res["hora_caja"] + ventana > fin_datos:
            res["estado"] = PENDIENTE  # la copia de eleventa termina antes de que venciera la ventana
        else:
            res["estado"] = NO_COBRADO
    sobrantes = [g for lista in libres.values() for g in lista if g["id"] not in usados]
    return resultados, sobrantes


def agrupar(renglones):
    """Suma los renglones del mismo producto dentro de un ticket de caja (así los presenta eleventa al cobrar)."""
    grupos = {}
    for r in sorted(renglones, key=lambda r: r["agregado"]):
        g = grupos.setdefault((r["ticket_id"], r["codigo"]), {**r, "importe": 0.0})
        g["importe"] = round(g["importe"] + r["importe"], 2)
    return list(grupos.values())


def imprimir(resultados, sobrantes, salida=sys.stdout):
    p = lambda *a: print(*a, file=salida)
    por_dia = defaultdict(Counter)
    sin_cobrar, dif = defaultdict(float), defaultdict(float)
    for r in resultados:
        dia = r["hora"].date()
        por_dia[dia][r["estado"]] += 1
        if r["estado"] in (NO_COBRADO, PARCIAL, DISTINTO):
            sin_cobrar[dia] += sum(it["importe"] for it, c in zip(r["items"], r["cobros"]) if c is None)
            dif[dia] += sum(r["difs"])
    estados = (COBRADO, DISTINTO, PARCIAL, NO_COBRADO, PENDIENTE, ANULADO)
    p("día        | " + " | ".join(estados) + " | $ sin cobrar | $ cobrado de más(+)/menos(-)")
    for dia in sorted(por_dia):
        p(f"{dia} | " + " | ".join(f"{por_dia[dia][e]:>{len(e)}}" for e in estados)
          + f" | {sin_cobrar[dia]:>12.2f} | {dif[dia]:>+9.2f}")
    p(f"TOTAL      | " + " | ".join(f"{sum(d[e] for d in por_dia.values()):>{len(e)}}" for e in estados)
      + f" | {sum(sin_cobrar.values()):>12.2f} | {sum(dif.values()):>+9.2f}")

    retrasos = sorted((c["agregado"] - r["hora_caja"]).total_seconds()
                      for r in resultados for c in r["cobros"] if c is not None)
    if retrasos:
        q = lambda f: timedelta(seconds=int(retrasos[min(len(retrasos) - 1, int(f * len(retrasos)))]))
        p(f"\nimprimir → escanear en caja: mediana {q(.5)}, p95 {q(.95)}, p99 {q(.99)}, máx {q(1)}")
    p(f"renglones cobrados en caja con código de carnicería sin ticket de tablet: {len(sobrantes)}")
    desfases = Counter(r["hora_caja"] - r["hora"] for r in resultados)
    p("reloj de la caja vs Juárez: " +
      ", ".join(f"{d.total_seconds() / 3600:+.0f} h: {n} tickets" for d, n in desfases.most_common()))

    p("\nTickets por revisar:")
    for r in resultados:
        if r["estado"] not in (NO_COBRADO, PARCIAL, DISTINTO):
            continue
        p(f"\n{r['estado']:<10} {r['hora']:%Y-%m-%d %H:%M:%S}  folio tablet {r['folio']}  total ${r['total']:.2f}")
        for it, c, nota in zip(r["items"], r["cobros"], r["notas"]):
            donde = (f"caja {c['caja']} folio {c['folio']} cajero {c['cajero']} {c['agregado']:%H:%M:%S} {nota}"
                     if c else f"— SIN COBRAR — {nota}")
            p(f"    {it['codigo']:>13} {it['nombre'][:28]:<28} ${it['importe']:>8.2f}  {donde}")


def guardar_csv(resultados, ruta):
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig para que Excel lo abra bien
        w = csv.writer(f)
        w.writerow(["fecha_hora_tablet", "folio_tablet", "estado", "codigo", "producto", "importe",
                    "caja", "folio_caja", "cajero", "hora_escaneo", "forma_pago", "nota"])
        for r in resultados:
            for it, c, nota in zip(r["items"], r["cobros"], r["notas"]):
                w.writerow([f"{r['hora']:%Y-%m-%d %H:%M:%S}", r["folio"], r["estado"], it["codigo"], it["nombre"],
                            f"{it['importe']:.2f}", *(("", "", "", "", "") if c is None else
                            (c["caja"], c["folio"], c["cajero"], f"{c['agregado']:%Y-%m-%d %H:%M:%S}", c["forma_pago"])),
                            nota])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tablet", required=True)
    ap.add_argument("--eleventa", required=True)
    ap.add_argument("--fb-lib")
    ap.add_argument("--desde", required=True, type=datetime.fromisoformat)
    ap.add_argument("--hasta", type=datetime.fromisoformat, default=datetime.now() + timedelta(days=1))
    ap.add_argument("--csv")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # la consola de Windows usa cp1252

    import eleventa  # aquí para que las pruebas no necesiten fdb
    tickets = cargar_tablet(a.tablet, a.desde, a.hasta)
    codigos = {it["codigo"] for t in tickets for it in t["items"]}
    con = eleventa.conectar(a.eleventa, a.fb_lib)
    desde_id = eleventa.primer_id_desde(con, a.desde - timedelta(hours=3))
    renglones = [r for r in eleventa.articulos(con, desde_id)
                 if r["codigo"] in codigos and r["agregado"] < a.hasta + VENTANA + timedelta(hours=3)]
    con.close()

    resultados, sobrantes = conciliar(tickets, renglones)
    imprimir(resultados, sobrantes)
    if a.csv:
        guardar_csv(resultados, a.csv)


if __name__ == "__main__":
    main()
