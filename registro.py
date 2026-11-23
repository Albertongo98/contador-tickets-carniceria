"""Lo que pasa en esta caja, por día: controles escaneados, alarmas revisadas y avisos ya enviados a la dueña.
SQLite (librería estándar). Nada se borra: se puede reimprimir el reporte de cualquier día."""
import sqlite3
import threading
from datetime import datetime

ESQUEMA = """
CREATE TABLE IF NOT EXISTS escaneos (fecha TEXT, folio INTEGER, hora TEXT, codigo TEXT, PRIMARY KEY (fecha, folio));
CREATE TABLE IF NOT EXISTS revisiones (fecha TEXT, folio INTEGER, estado TEXT, cuando TEXT, PRIMARY KEY (fecha, folio));
CREATE TABLE IF NOT EXISTS avisados (fecha TEXT, folio INTEGER, cuando TEXT, PRIMARY KEY (fecha, folio));
"""


class Registro:
    def __init__(self, ruta):
        # La usan la ventana y la revisión en segundo plano: una conexión compartida con candado.
        self.db = sqlite3.connect(ruta, check_same_thread=False)
        self.candado = threading.RLock()
        self.db.executescript(ESQUEMA)
        for nombre in ("escanear", "escaneados", "revisar", "revisados", "avisados", "avisado"):
            setattr(self, nombre, self._con_candado(getattr(self, nombre)))

    def _con_candado(self, metodo):
        def envuelto(*a):
            with self.candado:
                return metodo(*a)
        return envuelto

    def escanear(self, dia, folio, cuando, codigo):
        """True si es nuevo; False si ese control ya se había escaneado hoy."""
        with self.db:
            cur = self.db.execute("INSERT OR IGNORE INTO escaneos VALUES (?, ?, ?, ?)",
                                  (dia.isoformat(), folio, cuando.strftime("%H:%M:%S"), codigo))
        return cur.rowcount == 1

    def escaneados(self, dia):
        return {f for (f,) in self.db.execute("SELECT folio FROM escaneos WHERE fecha = ?", (dia.isoformat(),))}

    def revisar(self, cuando, folio, estado):
        """Cómo quedó una alarma (Revisado / Corregido / Cancelado). cuando: hora de Juárez (su fecha = día del ticket)."""
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO revisiones VALUES (?, ?, ?, ?)",
                            (cuando.date().isoformat(), folio, estado, cuando.strftime("%H:%M")))

    def revisados(self, dia):
        """{folio: ("Corregido", "14:05")}"""
        return {f: (e, c) for f, e, c in self.db.execute(
            "SELECT folio, estado, cuando FROM revisiones WHERE fecha = ?", (dia.isoformat(),))}

    def avisados(self, dia):
        return {f for (f,) in self.db.execute("SELECT folio FROM avisados WHERE fecha = ?", (dia.isoformat(),))}

    def avisado(self, dia, folio):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO avisados VALUES (?, ?, ?)",
                            (dia.isoformat(), folio, datetime.now().isoformat(timespec="seconds")))
