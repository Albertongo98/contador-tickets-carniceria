"""Lectura de los tickets de la tablet (Firestore `ticketsCarniceria/{yyyy-MM-dd}`, proyecto de PalmApp).

Solo librería estándar (REST). La PC de la caja se aprueba una vez con el nombre y PIN de administración o de la
dueña (función `entrar` con caja: true) y luego se quita la persona (`salir`): queda con permiso de SOLO leer los
tickets de carnicería. La sesión (refresh token) se guarda en `palmapp_sesion.json`, junto al programa.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

PROYECTO = "lapalma-proveedores"
FUNCIONES = f"https://us-central1-{PROYECTO}.cloudfunctions.net"
FIRESTORE = f"https://firestore.googleapis.com/v1/projects/{PROYECTO}/databases/(default)/documents"
TIEMPO = 8  # segundos; sin internet el Contador sigue como antes


class ErrorPalmApp(Exception):
    pass


def _post(url, datos, token=None, form=False):
    cuerpo = urllib.parse.urlencode(datos).encode() if form else json.dumps(datos).encode()
    req = urllib.request.Request(url, cuerpo, {
        "Content-Type": "application/x-www-form-urlencoded" if form else "application/json",
        **({"Authorization": f"Bearer {token}"} if token else {})})
    return _abrir(req)


def _abrir(req):
    try:
        with urllib.request.urlopen(req, timeout=TIEMPO) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            err = json.load(e).get("error", {})
            msg = err.get("message", "") if isinstance(err, dict) else str(err)
        except Exception:
            msg = ""
        raise ErrorPalmApp(msg or f"HTTP {e.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ErrorPalmApp(f"Sin conexión con PalmApp ({e})") from None


class PalmApp:
    def __init__(self, api_key, archivo_sesion):
        self.key, self.archivo = api_key, archivo_sesion
        self._token = None

    @property
    def conectado(self):
        return os.path.exists(self.archivo)

    def _refrescar(self, refresh):
        r = _post(f"https://securetoken.googleapis.com/v1/token?key={self.key}",
                  {"grant_type": "refresh_token", "refresh_token": refresh}, form=True)
        with open(self.archivo, "w", encoding="utf-8") as f:
            json.dump({"refresh_token": r["refresh_token"]}, f)
        self._token = r["id_token"]
        return self._token

    def _llamar(self, funcion, datos):
        r = _post(f"{FUNCIONES}/{funcion}", {"data": datos}, self._token)
        if "error" in r:
            raise ErrorPalmApp(r["error"].get("message", "Error"))
        return r.get("result")

    def conectar(self, nombre, pin):
        """Aprueba esta PC como 'caja' (una sola vez). Lanza ErrorPalmApp con el mensaje para la pantalla."""
        r = _post(f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={self.key}", {"returnSecureToken": True})
        self._token = r["idToken"]
        try:
            self._llamar("entrar", {"nombre": nombre.strip(), "pin": pin.strip(), "caja": True})
            self._refrescar(r["refreshToken"])          # la sesión ya trae equipo + caja + persona
            self._llamar("salir", {})                   # se quita la persona: solo queda el permiso de la caja
            with open(self.archivo, encoding="utf-8") as f:
                self._refrescar(json.load(f)["refresh_token"])
        except Exception:
            if os.path.exists(self.archivo):
                os.remove(self.archivo)
            raise

    def tickets_del_dia(self, fecha, reintentar=True):
        """Lista de tickets del día (dicts tal como los sube CarniceriaApp). [] si aún no hay ninguno."""
        if not self._token:
            with open(self.archivo, encoding="utf-8") as f:
                self._refrescar(json.load(f)["refresh_token"])
        req = urllib.request.Request(f"{FIRESTORE}/ticketsCarniceria/{fecha}",
                                     headers={"Authorization": f"Bearer {self._token}"})
        try:
            doc = _abrir(req)
        except ErrorPalmApp as e:
            if "not found" in str(e).lower() or "HTTP 404" in str(e):
                return []
            if reintentar and ("UNAUTHENTICATED" in str(e).upper() or "HTTP 401" in str(e)):  # token vence en 1 h
                self._token = None
                return self.tickets_del_dia(fecha, reintentar=False)
            raise
        return valor({"mapValue": doc}).get("tickets", [])


    def _token_fresco(self):
        with open(self.archivo, encoding="utf-8") as f:
            return self._refrescar(json.load(f)["refresh_token"])

    def version_publicada(self, app="contador"):
        """La última versión publicada (config/versiones.<app>, la escribe tools/publicar_version.py de PalmApp), o None."""
        req = urllib.request.Request(f"{FIRESTORE}/config/versiones",
                                     headers={"Authorization": f"Bearer {self._token_fresco()}"})
        return valor({"mapValue": _abrir(req)}).get(app)

    def descargar(self, ruta, destino, progreso=lambda f: None):
        """Descarga un archivo de Storage (actualizaciones/...): solo equipos aprobados (storage.rules)."""
        url = f"https://firebasestorage.googleapis.com/v0/b/{PROYECTO}.firebasestorage.app/o/" \
              f"{urllib.parse.quote(ruta, safe='')}?alt=media"
        req = urllib.request.Request(url, headers={"Authorization": f"Firebase {self._token_fresco()}"})
        with urllib.request.urlopen(req, timeout=60) as r, open(destino, "wb") as f:
            total, leido = int(r.headers.get("Content-Length") or 0), 0
            while bloque := r.read(256 * 1024):
                f.write(bloque); leido += len(bloque)
                if total: progreso(leido / total)

    def avisar_duena(self, id_aviso, titulo, mensaje):
        """Notificación urgente a la dueña en PalmApp (colección `avisos`; la entrega la función avisoNuevo).
        Con id fijo: si ya existe no se repite (Firestore responde ALREADY_EXISTS)."""
        if not self._token:
            with open(self.archivo, encoding="utf-8") as f:
                self._refrescar(json.load(f)["refresh_token"])
        import time
        campos = {"titulo": titulo, "mensaje": mensaje, "tag": "carniceria", "dispositivo": "contador-tickets",
                  "creadoEn": int(time.time() * 1000), "enviado": False, "para": [], "alDueno": True,
                  "esMensaje": False, "via": "fcm", "urgente": True, "entregadoA": []}
        try:
            _post(f"{FIRESTORE}/avisos?documentId={urllib.parse.quote(id_aviso)}",
                  {"fields": {k: a_firestore(v) for k, v in campos.items()}}, self._token)
        except ErrorPalmApp as e:
            if "already exists" not in str(e).lower():
                raise


def a_firestore(v):
    """Python → valor tipado de la API REST de Firestore (solo lo que usan los avisos)."""
    if isinstance(v, bool):
        return {"booleanValue": v}
    if isinstance(v, int):
        return {"integerValue": str(v)}
    if isinstance(v, list):
        return {"arrayValue": {"values": [a_firestore(x) for x in v]}}
    return {"stringValue": str(v)}


def valor(v):
    """Valor tipado de la API REST de Firestore → Python."""
    if "mapValue" in v:
        return {k: valor(x) for k, x in v["mapValue"].get("fields", {}).items()}
    if "arrayValue" in v:
        return [valor(x) for x in v["arrayValue"].get("values", [])]
    if "integerValue" in v:
        return int(v["integerValue"])
    if "doubleValue" in v:
        return float(v["doubleValue"])
    if "nullValue" in v:
        return None
    for k in ("stringValue", "booleanValue", "timestampValue"):
        if k in v:
            return v[k]
    return None
