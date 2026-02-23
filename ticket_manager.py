import re
import json
from datetime import datetime, timedelta
from dateutil import parser
from typing import Dict, List, Optional, Tuple
import os

class Ticket:
    """Representa un ticket individual con folio, fecha/hora y estado"""
    
    def __init__(self, folio: str, fecha_hora: datetime, codigo_original: str, estado: str = "OK"):
        self.folio = folio
        self.fecha_hora = fecha_hora
        self.codigo_original = codigo_original
        # estado: "OK" | "CANCELADO" | "FALTANTE"
        self.estado = estado
    
    def __str__(self):
        return f"Ticket {self.folio}: {self.fecha_hora.strftime('%H:%M:%S')}"
    
    def __repr__(self):
        return self.__str__()

class TicketManager:
    """Maneja la colección de tickets, detecta faltantes y organiza por turnos"""
    
    def __init__(self):
        self.tickets: Dict[str, Ticket] = {}  # folio -> Ticket
        self.tickets_por_fecha: Dict[str, List[Ticket]] = {}  # fecha -> lista de tickets
        self.turno_actual = "mañana"
        self.tickets_faltantes_detectados = set()
        self.contador_advertencia = 0  # Para controlar los 3 tickets de advertencia
        self.ultimo_folio_esperado = None
        self.data_file = "tickets_data.json"
        self.cargar_datos()

    # Utilidades para manejar folios por número (evita depender del zfill)
    def _folio_key_variants(self, folio_num: int) -> List[str]:
        s = str(folio_num)
        return [s, s.zfill(3), s.zfill(4), s.zfill(5)]

    def _has_ticket_by_int(self, folio_num: int) -> bool:
        for k in self._folio_key_variants(folio_num):
            if k in self.tickets:
                return True
        return False

    def _get_ticket_by_int(self, folio_num: int) -> Optional['Ticket']:
        for k in self._folio_key_variants(folio_num):
            if k in self.tickets:
                return self.tickets[k]
        return None
    
    def parsear_codigo_barras(self, codigo: str) -> Optional[Ticket]:
        """
        Parsea un código de barras CODE 128 y extrae hora y folio.
        Formato: HHMMSS'FFFF o HHMMSS-FFFF (ej: 081021'004)
        """
        try:
            # NORMALIZAR: quitar espacios en blanco alrededor
            codigo = codigo.strip()

            # Normalizar: dejar sólo dígitos y separadores válidos (apostrofo, guion)
            codigo_limpio = re.sub(r'[^0-9\'\-]', '', codigo)

            # Evitar parsear cadenas claramente incompletas
            if len(codigo_limpio) < 9:  # HHMMSS + separador + al menos 1 dígito de folio
                return None

            # Patrón: HHMMSS'FFFF o HHMMSS-FFFF (folio 1-5 dígitos)
            m = re.match(r'^(\d{6})[\'\-](\d{1,5})$', codigo_limpio)
            if m:
                hora_str, folio_str = m.groups()
                hoy = datetime.now()
                fecha_encontrada = hoy.replace(
                    hour=int(hora_str[:2]),
                    minute=int(hora_str[2:4]),
                    second=int(hora_str[4:6]),
                    microsecond=0
                )
                # normalizar folio removiendo ceros a la izquierda
                folio_encontrado = str(int(folio_str))
                return Ticket(folio_encontrado, fecha_encontrada, codigo)

            # Si el patrón no coincide, retorna None
            return None
            
        except Exception as e:
            print(f"Error parseando código: {e}")
            return None
    
    def agregar_ticket(self, codigo: str, cancelado: bool = False, faltante: bool = False) -> Tuple[bool, str, bool]:
        """
        Agrega un ticket y retorna (éxito, mensaje, mostrar_amarillo)
        """
        ticket = self.parsear_codigo_barras(codigo)
        if not ticket:
            return False, "Código de barras inválido", False
        
        # Verificar si ya existe
        folio_nuevo = int(ticket.folio)
        # Normalizar clave a cadena sin ceros a la izquierda
        ticket.folio = str(folio_nuevo)
        if self._has_ticket_by_int(folio_nuevo):
            return False, f"Ticket {ticket.folio} ya existe", False
        
        # Validar que el ticket esté en un rango razonable
        if self.tickets:
            folios_existentes = [int(f) for f in self.tickets.keys()]
            folio_min_actual = min(folios_existentes)
            folio_max_actual = max(folios_existentes)
            folio_nuevo = int(ticket.folio)
            
            # Permitir tickets en el rango actual ±10 tickets
            RANGO_MAXIMO = 10
            
            # Si el ticket está muy por debajo del rango actual
            if folio_nuevo < folio_min_actual - RANGO_MAXIMO:
                return False, f"Ticket {ticket.folio} está muy fuera de rango (muy antiguo). Rango actual: {folio_min_actual:03d}-{folio_max_actual:03d}", False
            
            # Si el ticket está muy por encima del rango actual
            if folio_nuevo > folio_max_actual + RANGO_MAXIMO:
                return False, f"Ticket {ticket.folio} está muy fuera de rango (muy adelantado). Rango actual: {folio_min_actual:03d}-{folio_max_actual:03d}", False
        
        # Si es cancelado, marcar estado
        if cancelado:
            ticket.estado = "CANCELADO"
        
        # Si es faltante, marcar estado
        if faltante:
            ticket.estado = "FALTANTE"

        # Agregar ticket
        self.tickets[ticket.folio] = ticket
        fecha_str = ticket.fecha_hora.strftime('%Y-%m-%d')
        
        if fecha_str not in self.tickets_por_fecha:
            self.tickets_por_fecha[fecha_str] = []
        
        self.tickets_por_fecha[fecha_str].append(ticket)
        
        # Verificar si hay tickets faltantes (solo si no es cancelado ni faltante)
        mostrar_amarillo = False
        if not cancelado and not faltante:
            mostrar_amarillo = self._verificar_tickets_faltantes(ticket)
        
        self.guardar_datos()
        if cancelado:
            return True, f"Ticket {ticket.folio} CANCELADO registrado", False
        elif faltante:
            return True, f"Ticket {ticket.folio} FALTANTE registrado", False
        else:
            return True, f"Ticket {ticket.folio} registrado correctamente", mostrar_amarillo

    def agregar_ticket_cancelado(self, codigo: str) -> Tuple[bool, str, bool]:
        """Atajo para agregar ticket marcado como CANCELADO"""
        return self.agregar_ticket(codigo, cancelado=True)
    
    def agregar_ticket_faltante(self, codigo: str) -> Tuple[bool, str, bool]:
        """Atajo para agregar ticket marcado como FALTANTE"""
        return self.agregar_ticket(codigo, faltante=True)
    
    def _verificar_tickets_faltantes(self, nuevo_ticket: Ticket) -> bool:
        """
        Verifica si hay tickets faltantes y maneja la lógica de advertencia
        """
        folio_actual = int(nuevo_ticket.folio)
        
        # Si es el primer ticket del día o reinicio
        if self.ultimo_folio_esperado is None:
            self.ultimo_folio_esperado = folio_actual
            return False
        
        # Verificar secuencia
        if folio_actual == self.ultimo_folio_esperado + 1:
            # Secuencia normal
            self.ultimo_folio_esperado = folio_actual
            self.contador_advertencia = 0
            return False
        elif folio_actual > self.ultimo_folio_esperado + 1:
            # Hay tickets faltantes
            for folio_faltante in range(self.ultimo_folio_esperado + 1, folio_actual):
                # Guardar sin ceros a la izquierda
                self.tickets_faltantes_detectados.add(str(folio_faltante))
            
            self.ultimo_folio_esperado = folio_actual
            self.contador_advertencia = 3  # Mostrar amarillo por los próximos 3 tickets
            return True
        else:
            # Ticket anterior que llegó tarde
            # Quitar de faltantes cualquier variante
            for variante in [str(folio_actual), str(folio_actual).zfill(3), str(folio_actual).zfill(4)]:
                if variante in self.tickets_faltantes_detectados:
                    self.tickets_faltantes_detectados.remove(variante)
            
            # Si aún hay advertencias pendientes, continuar mostrando amarillo
            if self.contador_advertencia > 0:
                self.contador_advertencia -= 1
                return self.contador_advertencia > 0
            
            return False
    
    def obtener_resumen_detallado(self) -> List[Dict]:
        """
        Genera lista completa de tickets con información de faltantes
        Retorna lista de diccionarios con: folio, status, hora, horario_camaras
        """
        if not self.tickets:
            return []
        
        # Obtener rango de folios
        folios_existentes = [int(f) for f in self.tickets.keys()]
        if not folios_existentes:
            return []
            
        folio_min = min(folios_existentes)
        folio_max = max(folios_existentes)
        width = max(3, len(str(folio_max)))
        
        resultado = []
        
        for folio_num in range(folio_min, folio_max + 1):
            folio_display = str(folio_num).zfill(width)
            ticket = self._get_ticket_by_int(folio_num)
            if ticket:
                resultado.append({
                    'folio': folio_display,
                    'status': getattr(ticket, 'estado', 'OK'),
                    'hora': ticket.fecha_hora.strftime('%H:%M:%S'),
                    'horario_camaras': None
                })
            else:
                # Ticket faltante
                ticket_anterior = self._buscar_ticket_cercano(folio_num, -1)
                ticket_posterior = self._buscar_ticket_cercano(folio_num, 1)
                
                horario_camaras = ""
                if ticket_anterior and ticket_posterior:
                    # Nuevo criterio: desde la hora (minuto) del ticket anterior hasta 10 min después del posterior
                    hora_inicio = ticket_anterior.fecha_hora.replace(second=0, microsecond=0)
                    hora_fin = (ticket_posterior.fecha_hora + timedelta(minutes=10)).replace(second=0, microsecond=0)
                    horario_camaras = f"{hora_inicio.strftime('%H:%M')} - {hora_fin.strftime('%H:%M')}"
                elif ticket_anterior:
                    hora_inicio = ticket_anterior.fecha_hora
                    hora_fin = hora_inicio + timedelta(minutes=10)
                    horario_camaras = f"{hora_inicio.strftime('%H:%M')} - {hora_fin.strftime('%H:%M')}"
                elif ticket_posterior:
                    hora_fin = ticket_posterior.fecha_hora
                    hora_inicio = hora_fin - timedelta(minutes=10)
                    horario_camaras = f"{hora_inicio.strftime('%H:%M')} - {hora_fin.strftime('%H:%M')}"
                else:
                    horario_camaras = "Sin referencia"
                
                resultado.append({
                    'folio': folio_display,
                    'status': 'FALTANTE',
                    'hora': '---',
                    'horario_camaras': horario_camaras
                })
        
        return resultado

    def obtener_estadisticas_turno(self) -> Dict[str, int]:
        """Devuelve conteos de tickets por estado para el turno en curso"""
        tickets_cancelados = [t for t in self.tickets.values() if getattr(t, 'estado', 'OK') == 'CANCELADO']
        tickets_validos = [t for t in self.tickets.values() if getattr(t, 'estado', 'OK') != 'CANCELADO']

        return {
            'total_ok': len(tickets_validos),
            'total_cancelados': len(tickets_cancelados),
            'total_escaneados': len(self.tickets)
        }
    
    def obtener_resumen(self) -> str:
        """Genera un resumen de tickets faltantes y sugerencias de horarios (versión simple)"""
        stats = self.obtener_estadisticas_turno()

        if not self.tickets_faltantes_detectados:
            return (
                "OK - Ningun ticket faltante\n"
                f"Cancelados registrados: {stats['total_cancelados']}"
            )

        resumen = (
            f"TICKETS FALTANTES: {len(self.tickets_faltantes_detectados)}\n\n"
            f"Cancelados registrados: {stats['total_cancelados']}\n\n"
        )
        
        for folio in sorted(self.tickets_faltantes_detectados):
            # Buscar tickets antes y después para estimar horario
            folio_int = int(folio)
            ticket_anterior = self._buscar_ticket_cercano(folio_int, -1)
            ticket_posterior = self._buscar_ticket_cercano(folio_int, 1)
            
            if ticket_anterior and ticket_posterior:
                hora_inicio = ticket_anterior.fecha_hora - timedelta(minutes=5)
                hora_fin = ticket_posterior.fecha_hora + timedelta(minutes=5)
                resumen += f"Folio {folio}: Revisar camaras entre {hora_inicio.strftime('%H:%M')} y {hora_fin.strftime('%H:%M')}\n"
            elif ticket_anterior:
                hora_inicio = ticket_anterior.fecha_hora
                hora_fin = hora_inicio + timedelta(minutes=10)
                resumen += f"Folio {folio}: Revisar camaras desde {hora_inicio.strftime('%H:%M')} (+10 min)\n"
            elif ticket_posterior:
                hora_fin = ticket_posterior.fecha_hora
                hora_inicio = hora_fin - timedelta(minutes=10)
                resumen += f"Folio {folio}: Revisar camaras hasta {hora_fin.strftime('%H:%M')} (-10 min)\n"
            else:
                resumen += f"Folio {folio}: Sin referencia temporal\n"
        
        return resumen
    
    def _buscar_ticket_cercano(self, folio_objetivo: int, direccion: int) -> Optional[Ticket]:
        """Busca el ticket más cercano en la dirección especificada"""
        for i in range(1, 100):  # Buscar hasta 100 folios de distancia
            folio_buscar = folio_objetivo + (i * direccion)
            if folio_buscar < 1 or folio_buscar > 99999:
                break
            t = self._get_ticket_by_int(folio_buscar)
            if t:
                return t
        
        return None
    
    def cierre_de_caja(self) -> str:
        """Realiza el cierre de caja y prepara para el siguiente turno"""
        resumen = self.obtener_resumen()
        
        # Cambiar turno
        nuevo_turno = "tarde" if self.turno_actual == "mañana" else "mañana"
        
        # Generar reporte de cierre
        stats = self.obtener_estadisticas_turno()
        
        reporte = f"""
=== CIERRE DE CAJA - TURNO {self.turno_actual.upper()} ===
Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}

    Tickets OK: {stats['total_ok']}
    Cancelados: {stats['total_cancelados']}
    Total escaneados: {stats['total_escaneados']}

{resumen}

Próximo turno: {nuevo_turno}
========================================
"""
        
        # Guardar reporte
        fecha_actual = datetime.now().strftime('%Y%m%d')
        nombre_archivo = f"cierre_{self.turno_actual}_{fecha_actual}.txt"
        
        with open(nombre_archivo, 'w', encoding='utf-8') as f:
            f.write(reporte)
        
        # Resetear para nuevo turno
        self.turno_actual = nuevo_turno
        self.tickets.clear()
        self.tickets_por_fecha.clear()
        self.tickets_faltantes_detectados.clear()
        self.contador_advertencia = 0
        self.ultimo_folio_esperado = None
        
        self.guardar_datos()
        
        return f"Cierre completado. Reporte guardado en: {nombre_archivo}"
    
    def guardar_datos(self):
        """Guarda los datos en un archivo JSON"""
        try:
            datos = {
                'turno_actual': self.turno_actual,
                'tickets': {},
                'tickets_faltantes': list(self.tickets_faltantes_detectados),
                'contador_advertencia': self.contador_advertencia,
                'ultimo_folio_esperado': self.ultimo_folio_esperado
            }
            
            # Serializar tickets
            for folio, ticket in self.tickets.items():
                datos['tickets'][folio] = {
                    'folio': ticket.folio,
                    'fecha_hora': ticket.fecha_hora.isoformat(),
                    'codigo_original': ticket.codigo_original,
                    'estado': getattr(ticket, 'estado', 'OK')
                }
            
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(datos, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"Error guardando datos: {e}")
    
    def cargar_datos(self):
        """Carga los datos desde el archivo JSON"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    datos = json.load(f)
                
                self.turno_actual = datos.get('turno_actual', 'mañana')
                self.tickets_faltantes_detectados = set(datos.get('tickets_faltantes', []))
                self.contador_advertencia = datos.get('contador_advertencia', 0)
                self.ultimo_folio_esperado = datos.get('ultimo_folio_esperado')
                
                # Deserializar tickets
                tickets_data = datos.get('tickets', {})
                for folio, ticket_data in tickets_data.items():
                    fecha_hora = datetime.fromisoformat(ticket_data['fecha_hora'])
                    ticket = Ticket(
                        ticket_data['folio'],
                        fecha_hora,
                        ticket_data['codigo_original'],
                        ticket_data.get('estado', 'OK')
                    )
                    self.tickets[folio] = ticket
                    
                    # Organizar por fecha
                    fecha_str = fecha_hora.strftime('%Y-%m-%d')
                    if fecha_str not in self.tickets_por_fecha:
                        self.tickets_por_fecha[fecha_str] = []
                    self.tickets_por_fecha[fecha_str].append(ticket)
                        
        except Exception as e:
            print(f"Error cargando datos: {e}")