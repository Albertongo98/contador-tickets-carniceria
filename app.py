"""Contador de Tickets · Carnicería — programa de la caja (interfaz web en ventana nativa, pywebview + WebView2).

Ventanas:
  · widget  — tarjeta flotante, siempre encima: la cajera le da un clic, escanea el control (HHmmss-folio) y el
              programa le regresa el foco a eleventa solo. Muestra cuántos tickets van en camino.
  · completa — vista "Escáner" (sin datos) y vista "Tablero" (por revisar en cámaras, lista del día, fuentes).
Cada minuto (y con cada escaneo) cruza la tablet (PalmApp) con lo cobrado en eleventa; lo que hay que revisar le
llega a la dueña en PalmApp. La interfaz está en ui/index.html; aquí solo vive la lógica y la API para la página.
Uso: app.py [--completa]   (por omisión abre el widget)
"""
import ctypes
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import winreg
from ctypes import wintypes

import webview

import verificar as V
from registro import Registro

VERSION, VERSION_CODE = "2.1", 21  # al publicar: subirlos y usar tools/publicar_version.py de PalmApp (app "contador")
CADA = 60  # segundos entre revisiones automáticas
CADA_VERSION = 6 * 3600  # buscar actualizaciones al abrir y cada 6 h
CONTROL = re.compile(r"^(\d{6})\D(\d{1,5})$")  # HHmmss-folio (el lector puede mandar ' en vez de -)
UI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "index.html")
TAM_WIDGET = (480, 150)
OPACIDAD_REPOSO = 0.82  # widget en reposo (config: "transparencia_widget"); al pasar el mouse o con foco: opaco

RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
NOMBRE_RUN = "ContadorTicketsLaPalma"
user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi


def script_actualizar(pid, nuevo, prog, tmp):
    """.bat que espera a que este proceso se cierre, copia la versión nueva encima del programa (sin borrar nada más),
    lo vuelve a abrir y se limpia."""
    # Rutas completas (otro find/timeout en el PATH, p. ej. el de Git, rompe la espera) y ping como pausa: timeout.exe
    # falla sin consola, y el .bat corre sin ventana.
    s32 = r"%SystemRoot%\System32"
    return (f'@echo off\r\n:espera\r\n{s32}\\tasklist.exe /FI "PID eq {pid}" | {s32}\\find.exe "{pid}" >nul && '
            f'({s32}\\PING.EXE -n 2 127.0.0.1 >nul & goto espera)\r\n'
            f'robocopy "{nuevo}" "{prog}" /E /R:5 /W:1 /NFL /NDL /NJH /NJS >nul\r\n'
            f'start "" "{os.path.join(prog, "SistemaTickets.exe")}"\r\n'
            f'rmdir /s /q "{tmp}"\r\ndel "%~f0"\r\n')


def autoinicio_activo():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN) as k:
            winreg.QueryValueEx(k, NOMBRE_RUN)
        return True
    except OSError:
        return False


def poner_autoinicio(activo):
    """Abrir el widget al iniciar sesión en Windows (registro "Run" del usuario: no pide administrador)."""
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN, 0, winreg.KEY_SET_VALUE) as k:
        if activo:
            winreg.SetValueEx(k, NOMBRE_RUN, 0, winreg.REG_SZ, f'"{sys.executable}"')
        else:
            try:
                winreg.DeleteValue(k, NOMBRE_RUN)
            except FileNotFoundError:
                pass


def _primer_arranque():
    """Instalado (.exe): la primera vez se registra para abrir con Windows. Después manda el interruptor del Tablero."""
    if not getattr(sys, "frozen", False):
        return  # en desarrollo no se registra el python de pruebas
    marca = os.path.join(V.carpeta(), "autoinicio.hecho")
    if not os.path.exists(marca):
        try:
            poner_autoinicio(True)
            open(marca, "w").close()
        except OSError:
            pass


def _es_nuestra(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value == os.getpid()


class Contador:
    """La lógica (sin ventanas). Sus métodos públicos son la API que llama la página (window.pywebview.api)."""

    def __init__(self):
        try:
            self._cfg = V.config()
            self._error_cfg = ""
        except Exception as e:
            self._cfg, self._error_cfg = {}, f"No se pudo leer config.json ({e})"
        self._registro = Registro(os.path.join(V.carpeta(), "contador.db"))
        self._palmapp = None
        if self._cfg.get("api_key"):
            from palmapp import PalmApp
            self._palmapp = PalmApp(self._cfg["api_key"], os.path.join(V.carpeta(), "palmapp_sesion.json"))
        self._filas, self._fuentes, self._folios_tablet, self._actualizado = [], {}, None, None
        self._ultimo = {"n": 0, "texto": "", "tipo": "listo"}
        self._despertar = threading.Event()
        self._ajena = None  # última ventana de otro programa con el foco (eleventa)
        self._widget = self._completa = None
        self._saliendo = False
        self._nueva, self._actualizando = None, None  # versión publicada más nueva; texto del avance al actualizar
        threading.Thread(target=self._ciclo, daemon=True).start()
        threading.Thread(target=self._vigilar_foco, daemon=True).start()
        threading.Thread(target=self._vigilar_version, daemon=True).start()

    # --- Actualizaciones (Storage + config/versiones de PalmApp) -----------------------------------------------
    def _vigilar_version(self):
        import time
        while True:
            self.buscar_actualizacion()
            time.sleep(CADA_VERSION)

    def buscar_actualizacion(self):
        if not (self._palmapp and self._palmapp.conectado):
            return {"ok": False, "mensaje": "Primero conecta esta caja con PalmApp (Tablero)."}
        try:
            v = self._palmapp.version_publicada("contador")
        except Exception as e:
            return {"ok": False, "mensaje": f"No se pudo revisar: {e}"}
        self._nueva = v if v and v.get("versionCode", 0) > VERSION_CODE else None
        if self._nueva:
            return {"ok": True, "mensaje": f"Hay versión nueva: {self._nueva['versionName']}", "nueva": self._nueva}
        return {"ok": True, "mensaje": f"Ya tienes la versión más nueva ({VERSION})."}

    def actualizar(self):
        """Descarga el zip, revisa que llegó completo (sha256), se cierra y un .bat copia la versión nueva encima del
        programa y lo vuelve a abrir. Los datos (%APPDATA%\\ContadorTickets) no se tocan."""
        if not getattr(sys, "frozen", False):
            return {"ok": False, "mensaje": "Solo se actualiza el programa instalado (SistemaTickets.exe)."}
        if not self._nueva or self._actualizando:
            return {"ok": False, "mensaje": "No hay actualización pendiente."}
        threading.Thread(target=self._actualizar, args=(self._nueva,), daemon=True).start()
        return {"ok": True, "mensaje": "Descargando…"}

    def _actualizar(self, v):
        import hashlib, shutil, time, zipfile
        tmp = None
        try:
            tmp = tempfile.mkdtemp(prefix="ContadorTickets_")
            zip_ = os.path.join(tmp, "nuevo.zip")
            self._palmapp.descargar(v["ruta"], zip_, lambda f: setattr(self, "_actualizando", f"Descargando {f:.0%}"))
            with open(zip_, "rb") as f:
                if v.get("sha256") and hashlib.sha256(f.read()).hexdigest() != v["sha256"]:
                    raise ValueError("el archivo llegó incompleto o dañado")
            self._actualizando = "Instalando…"
            zipfile.ZipFile(zip_).extractall(os.path.join(tmp, "nuevo"))
            nuevo = next(r for r, _, fs in os.walk(os.path.join(tmp, "nuevo")) if "SistemaTickets.exe" in fs)
            prog, pid = V.programa(), os.getpid()
            bat = os.path.join(tempfile.gettempdir(), f"actualizar_contador_{pid}.bat")
            with open(bat, "w", encoding="mbcs") as f:
                f.write(script_actualizar(pid, nuevo, prog, tmp))
            subprocess.Popen(["cmd", "/c", bat], creationflags=0x08000000 | 0x00000200)  # sin ventana, grupo aparte
            time.sleep(0.5)
            self.salir()
        except Exception as e:
            self._actualizando = None
            self._ultimo = {"n": self._ultimo["n"] + 1, "tipo": "error", "texto": f"No se pudo actualizar: {e}"}
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)

    # --- Revisión en segundo plano ------------------------------------------------------------------------------
    def _ciclo(self):
        while True:
            self._revisar()
            self._despertar.wait(CADA)
            self._despertar.clear()

    def _revisar(self):
        dia = V.ahora_juarez().date()
        try:
            filas, fuentes, tablet = V.cargar(self._cfg, self._palmapp, self._registro.escaneados(dia),
                                              self._registro.revisados(dia), dia)
        except Exception as e:  # nunca tumbar el Contador
            self._fuentes = {"tablet": f"error: {e}"}
            return
        self._filas, self._fuentes = filas, fuentes
        self._folios_tablet = None if tablet is None else {t["folio"] for t in tablet}
        self._actualizado = V.ahora_juarez().strftime("%H:%M")
        # Solo con eleventa leído: sin él, todo lo no escaneado parecería faltante (avisos falsos a la dueña).
        if fuentes.get("eleventa") is not True or not self._palmapp:
            return
        ya = self._registro.avisados(dia)
        limite = (V.ahora_juarez() - V.AVISO_DUENA).strftime("%H:%M:%S")  # impreso antes de esto (mismo día, HH:MM:SS)
        for a in filas:
            # A la dueña hasta AVISO_DUENA: entre GRACIA y eso, solo el Tablero (casi siempre se cobra en ese rato).
            if a["estado"] in V.ALARMAS and a["folio"] not in ya and a["hora"] and a["hora"] <= limite:
                try:
                    self._palmapp.avisar_duena(
                        f"carniceria_{dia}_{a['folio']:03d}", f"⚠ Carnicería: ticket {a['estado'].lower()}",
                        f"Folio {a['folio']:03d} · ${a['total']:.2f} · impreso {a['hora']} · "
                        f"cámaras {a['camaras']} · {a['productos']}")
                    self._registro.avisado(dia, a["folio"])
                except Exception:
                    pass  # se reintenta en la siguiente revisión

    # --- Foco: regresar a eleventa después de escanear en el widget ----------------------------------------------
    def _vigilar_foco(self):
        import time
        while True:
            h = user32.GetForegroundWindow()
            if h and not _es_nuestra(h):
                self._ajena = h
            time.sleep(0.25)

    def _regresar_foco(self):
        h = self._ajena
        if h and user32.IsWindow(h) and self._cfg.get("regresar_foco", True):
            if user32.IsIconic(h):
                user32.ShowWindow(h, 9)  # SW_RESTORE: si la minimizaron por costumbre
            user32.SetForegroundWindow(h)

    # --- API para la página ---------------------------------------------------------------------------------------
    def estado(self):
        f = self._filas
        c = {e: sum(x["estado"] == e for x in f) for e in
             (V.OK, V.COBRADO_SIN_CONTROL, V.ANULADO_TABLET, V.EN_CAMINO, V.FALTANTE, V.SIN_COBRO, V.REVISADO)}
        hay = self._folios_tablet is not None
        return {
            "filas": f, "conteo": c, "hay_tablet": hay, "actualizado": self._actualizado,
            "impresos": len(self._folios_tablet) - c[V.ANULADO_TABLET] if hay else None,
            "en_camino": c[V.EN_CAMINO] if hay else None,
            "pendientes": c[V.EN_CAMINO] + c[V.FALTANTE] if hay else None,  # impresos que aún no se escanean ni cobran
            "vamos_en": max(self._folios_tablet or [x["folio"] for x in f] or [0]) or None,  # último folio del día
            "por_revisar": c[V.FALTANTE] + c[V.SIN_COBRO],
            "fuentes": {k: (v if v is True or v is None else str(v)) for k, v in self._fuentes.items()},
            "ultimo": self._ultimo, "error_config": self._error_cfg,
            "conectado": bool(self._palmapp and self._palmapp.conectado), "hay_palmapp": bool(self._palmapp),
            "resoluciones": V.RESOLUCIONES,
            "ahora": V.ahora_juarez().strftime("%Y-%m-%dT%H:%M:%S"),
            "autoinicio": autoinicio_activo() if getattr(sys, "frozen", False) else None,  # None: no aplica (desarrollo)
            "version": VERSION, "nueva": self._nueva and {k: self._nueva.get(k) for k in ("versionName", "notas")},
            "actualizando": self._actualizando,
        }

    def escanear(self, codigo, desde_widget=False):
        codigo = (codigo or "").strip()
        m = CONTROL.match(codigo)
        if not m:
            r = {"tipo": "error", "texto": f"Código no reconocido: {codigo}"}
        else:
            folio, ahora = int(m.group(2)), V.ahora_juarez()
            if not self._registro.escanear(ahora.date(), folio, ahora, codigo):
                r = {"tipo": "repetido", "texto": f"Folio {folio:03d} ya estaba escaneado"}
            elif self._folios_tablet is not None and folio not in self._folios_tablet:
                r = {"tipo": "aviso", "texto": f"✓ Folio {folio:03d} · aún no aparece en la tablet"}
            else:
                r = {"tipo": "ok", "texto": f"✓ Folio {folio:03d} registrado"}
            self._despertar.set()
        self._ultimo = {"n": self._ultimo["n"] + 1, **r}
        if desde_widget and r["tipo"] != "error":
            threading.Timer(0.6, self._regresar_foco).start()  # deja ver el ✓ un instante
        return self._ultimo

    def autoinicio(self, activo):
        try:
            poner_autoinicio(bool(activo))
            return {"ok": True, "mensaje": "Se abrirá al iniciar Windows" if activo else "Ya no se abrirá al iniciar Windows"}
        except OSError as e:
            return {"ok": False, "mensaje": f"No se pudo cambiar: {e}"}

    def revisado(self, folio, resolucion):
        if resolucion not in V.RESOLUCIONES:
            return {"ok": False, "mensaje": "Estado no válido"}
        self._registro.revisar(V.ahora_juarez(), int(folio), resolucion)
        self._despertar.set()
        return {"ok": True}

    def conectar(self, nombre, pin):
        try:
            self._palmapp.conectar(nombre, pin)
            self._despertar.set()
            return {"ok": True, "mensaje": "Listo: esta caja ya lee los tickets de la tablet."}
        except Exception as e:
            return {"ok": False, "mensaje": f"No se pudo conectar: {e}"}

    def config_eleventa(self):
        """Para la pantalla Configuración: {servidor, ruta} de lo que hay en config.json."""
        servidor, _, ruta = self._cfg.get("eleventa", "").partition(":")
        return {"servidor": servidor, "ruta": ruta}

    def guardar_eleventa(self, servidor, ruta):
        """Guarda dónde está la base de eleventa y prueba la conexión (se guarda aunque falle: el servidor puede estar
        apagado ahorita)."""
        try:
            dsn = V.dsn_eleventa(servidor or "", ruta or "")
        except ValueError as e:
            return {"ok": False, "mensaje": str(e)}
        cfg = {**self._cfg, "eleventa": dsn}
        try:
            V.guardar_config(cfg)
        except OSError as e:
            return {"ok": False, "mensaje": f"No se pudo guardar config.json: {e}"}
        self._cfg = cfg
        V._desde_id.clear()  # otra base: otros IDs
        self._despertar.set()
        try:
            V.conectar_eleventa(cfg).close()
            return {"ok": True, "mensaje": "Guardado. Conexión con eleventa ✓"}
        except Exception as e:
            return {"ok": False, "mensaje": f"Guardado, pero no conecta con eleventa: {e}"}

    def imprimir(self):
        """Reporte del día para la impresora térmica de 57 mm (32 columnas), con la impresora predeterminada."""
        f, ancho, c = self._filas, 32, self.estado()["conteo"]
        ln = ["=" * ancho, "CONTROL DE TICKETS CARNICERIA", V.ahora_juarez().strftime("%d/%m/%Y %H:%M"), "=" * ancho,
              f"Escaneados:            {c[V.OK]}", f"Cobrados sin control:  {c[V.COBRADO_SIN_CONTROL]}",
              f"Anulados en tablet:    {c[V.ANULADO_TABLET]}", f"En camino:             {c[V.EN_CAMINO]}", "",
              f"POR REVISAR: {c[V.FALTANTE] + c[V.SIN_COBRO]}   REVISADOS: {c[V.REVISADO]}", "-" * ancho]
        for x in f:
            if x["estado"] in V.ALARMAS + (V.REVISADO,):
                total = f" ${x['total']:.2f}" if x["total"] is not None else ""
                ln += [f"Folio {x['folio']:03d}{total} {x['estado']}", f"Impreso {x['hora']}"]
                ln += [f"Camaras {x['camaras']}"] if x["camaras"] else []
                ln += [x["detalle"][i:i + ancho] for i in range(0, len(x["detalle"]), ancho)] + [""]
        ln += ["=" * ancho, ""]
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
            tmp.write("\n".join(ln))
        try:
            subprocess.run(["notepad.exe", "/p", tmp.name], check=True, timeout=15)
            return {"ok": True, "mensaje": "Reporte enviado a la impresora"}
        except Exception as e:
            return {"ok": False, "mensaje": f"No se pudo imprimir: {e}"}
        finally:
            os.remove(tmp.name)

    # --- Ventanas -----------------------------------------------------------------------------------------------
    def opacidad(self, opaco):
        """Widget translúcido en reposo y opaco al usarlo (WS_EX_LAYERED: con WebView2 la transparencia por CSS no
        funciona, la de toda la ventana sí)."""
        try:
            hwnd = self._widget.native.Handle.ToInt64()
            ex = user32.GetWindowLongW(hwnd, -20)
            if not ex & 0x80000:
                user32.SetWindowLongW(hwnd, -20, ex | 0x80000)
            alfa = 1.0 if opaco else float(self._cfg.get("transparencia_widget", OPACIDAD_REPOSO))
            user32.SetLayeredWindowAttributes(hwnd, 0, int(255 * max(0.3, min(alfa, 1.0))), 2)
        except Exception:
            pass

    def abrir(self, vista="tablero"):
        """Del widget a la ventana completa."""
        self._completa.evaluate_js(f"mostrarVista({json.dumps(vista)})")
        self._completa.show()
        self._completa.restore()
        self._widget.hide()

    def al_widget(self):
        self._widget.show()
        self._completa.hide()

    def salir(self):
        self._saliendo = True
        for w in (self._completa, self._widget):
            w.destroy()


def _esquinas_redondas(ventana):
    """Windows 11: esquinas redondeadas también en la ventana sin bordes (DWMWA_WINDOW_CORNER_PREFERENCE = ROUND)."""
    try:
        hwnd = ventana.native.Handle.ToInt64()
        dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(ctypes.c_int(2)), 4)
    except Exception:
        pass


def _icono(ventana):
    """Logo de La Palma en la barra de título y en la barra de tareas (si no, sale el de Python en desarrollo)."""
    try:
        import clr  # noqa: F401  (pythonnet, ya viene con pywebview en Windows)
        from System import Action
        from System.Drawing import Icon
        forma = ventana.native
        forma.Invoke(Action(lambda: setattr(forma, "Icon", Icon(os.path.join(os.path.dirname(UI), "icono.ico")))))
    except Exception:
        pass


def _posicion_guardada():
    try:
        with open(os.path.join(V.carpeta(), "widget.json"), encoding="utf-8") as f:
            p = json.load(f)
        return p["x"], p["y"]
    except Exception:
        ancho, alto = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        return ancho - TAM_WIDGET[0] - 24, alto - TAM_WIDGET[1] - 72  # esquina inferior derecha


def _guardar_posicion(x, y):
    try:
        with open(os.path.join(V.carpeta(), "widget.json"), "w", encoding="utf-8") as f:
            json.dump({"x": x, "y": y}, f)
    except Exception:
        pass


def main(c=None, instancia="ContadorTicketsLaPalma"):
    # Una sola instancia (se abre al iniciar Windows y alguien podría abrirlo otra vez a mano).
    ctypes.windll.kernel32.CreateMutexW(None, False, instancia)
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        return
    _primer_arranque()
    # Identidad propia en la barra de tareas: se agrupa como "Contador de Tickets" con su logo, no como Python.
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LaPalma.ContadorTickets")
    c = c or Contador()
    completa = "--completa" in sys.argv
    x, y = _posicion_guardada()
    c._widget = webview.create_window(
        "Contador de Tickets", f"{UI}?modo=widget", js_api=c, width=TAM_WIDGET[0], height=TAM_WIDGET[1], x=x, y=y,
        frameless=True, easy_drag=True, on_top=True, resizable=False, background_color="#F5E2C0", hidden=completa)
    c._completa = webview.create_window(
        "Contador de Tickets · Carnicería", f"{UI}?modo=completa", js_api=c, width=1180, height=800,
        min_size=(720, 520), background_color="#F5E2C0", hidden=not completa)
    c._widget.events.shown += lambda: (_esquinas_redondas(c._widget), c.opacidad(False), _icono(c._widget))
    c._completa.events.shown += lambda: _icono(c._completa)
    c._widget.events.moved += _guardar_posicion

    def cerrar_completa():  # cerrar la ventana grande regresa al widget; el programa sigue vigilando
        if c._saliendo:
            return True
        threading.Timer(0, c.al_widget).start()
        return False
    c._completa.events.closing += cerrar_completa
    webview.start(private_mode=False, storage_path=os.path.join(V.carpeta(), "webview"))


if __name__ == "__main__":
    main()
