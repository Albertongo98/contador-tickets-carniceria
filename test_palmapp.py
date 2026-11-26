"""python test_palmapp.py — la sesión vencida (401) se renueva sola, sin internet."""
import palmapp
from palmapp import ErrorPalmApp, PalmApp

p = PalmApp("key", "no-existe.json")
p._token = "viejo"
renovados, llamadas = [], []
p._refrescar = lambda refresh: renovados.append(1) or setattr(p, "_token", "nuevo") or "nuevo"
palmapp.open = lambda *a, **k: __import__("io").StringIO('{"refresh_token": "r"}')


def abrir(req):
    llamadas.append(req.headers["Authorization"])
    if "viejo" in req.headers["Authorization"]:  # así responde Firestore con el token vencido (sin «UNAUTHENTICATED»)
        raise ErrorPalmApp("Request had invalid authentication credentials.", 401)
    return {"fields": {"tickets": {"arrayValue": {"values": [{"integerValue": "7"}]}}}}


palmapp._abrir = abrir
assert p.tickets_del_dia("2026-11-26") == [7], "con 401 debe renovar el token y volver a leer"
assert renovados == [1] and llamadas == ["Bearer viejo", "Bearer nuevo"]

# Sin conexión: falla, pero olvida el token para que la siguiente vuelta se reconecte sola
p._token = "nuevo"
palmapp._abrir = lambda req: (_ for _ in ()).throw(ErrorPalmApp("Sin conexión con PalmApp", None))
try:
    p.tickets_del_dia("2026-11-26"); assert False
except ErrorPalmApp:
    assert p._token is None

# 404 = aún no hay tickets
palmapp._abrir = lambda req: (_ for _ in ()).throw(ErrorPalmApp("not found", 404))
p._token = "nuevo"
assert p.tickets_del_dia("2026-11-26") == []
print("ok")
