import re
import json
from datetime import datetime, timedelta
from dateutil import parser
from typing import Dict, List, Optional, Tuple
import os

class Ticket:
    """Representa un ticket individual con folio, fecha/hora y monto"""
    
    def __init__(self, folio: str, fecha_hora: datetime, monto: float, codigo_original: str):
        self.folio = folio
        self.fecha_hora = fecha_hora
        self.monto = monto
        self.codigo_original = codigo_original
    
    def __str__(self):
        return f"Ticket {self.folio}: {self.fecha_hora.strftime('%H:%M:%S')} - ${self.monto:.2f}"
    
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
    
    def parsear_codigo_barras(self, codigo: str) -> Optional[Ticket]:
        """
        Parsea un código de barras y extrae hora, folio y monto.
        Formato compacto recomendado: HHMMSS-FFF-MMMM.CC
        También soporta formatos alternativos para compatibilidad.
        """
        try:
            # NORMALIZAR: quitar espacios en blanco alrededor
            codigo = codigo.strip()

            # FORMATO COMPACTO ROBUSTO (acepta cualquier separador no numérico y con/sin punto)
            # Normalizar: dejar sólo dígitos y el punto decimal
            codigo_norm = re.sub(r'[^0-9\.]', '', codigo)

            # Intento A: HHMMSS FFF MMMM . CC (con punto)
            m = re.match(r'^(\d{6})(\d{3})(\d{4})\.(\d{2})$', codigo_norm)
            if m:
                hora_str, folio_str, mmmm, cc = m.groups()
                hoy = datetime.now()
                fecha_encontrada = hoy.replace(
                    hour=int(hora_str[:2]),
                    minute=int(hora_str[2:4]),
                    second=int(hora_str[4:6]),
                    microsecond=0
                )
                folio_encontrado = folio_str
                monto_encontrado = float(f"{int(mmmm):04d}.{int(cc):02d}")
                return Ticket(folio_encontrado, fecha_encontrada, monto_encontrado, codigo)

            # Intento B: HHMMSS FFF MMMM CC (sin punto)
            m = re.match(r'^(\d{6})(\d{3})(\d{4})(\d{2})$', codigo_norm)
            if m:
                hora_str, folio_str, mmmm, cc = m.groups()
                hoy = datetime.now()
                fecha_encontrada = hoy.replace(
                    hour=int(hora_str[:2]),
                    minute=int(hora_str[2:4]),
                    second=int(hora_str[4:6]),
                    microsecond=0
                )
                folio_encontrado = folio_str
                monto_encontrado = float(f"{int(mmmm):04d}.{int(cc):02d}")
                return Ticket(folio_encontrado, fecha_encontrada, monto_encontrado, codigo)

            # PATRÓN ALTERNATIVO: YYYYMMDDHHMMSS-FFF-MMMM.CC
            patron_estandar = r'(\d{14})-(\d{3})-(\d{4}\.\d{2})'
            match_estandar = re.search(patron_estandar, codigo)
            if match_estandar:
                fecha_str, folio_str, monto_str = match_estandar.groups()
                fecha_encontrada = datetime.strptime(fecha_str, '%Y%m%d%H%M%S')
                folio_encontrado = folio_str
                monto_encontrado = float(monto_str)
                return Ticket(folio_encontrado, fecha_encontrada, monto_encontrado, codigo)

            # PATRONES ALTERNATIVOS para compatibilidad con formatos existentes
            patrones_fecha = [
                r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})',  # 2025-10-13T14:30:25
                r'(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})',   # 13/10/2025 14:30:25
                r'(\d{14})',                                # 20251013143025 (sin separadores)
                r'(\d{12})',                                # 202510131430 (sin segundos)
            ]
            
            # Patrón para folio (3 dígitos)
            patron_folio = r'(\b\d{3}\b)'
            
            # Patrón para monto (formato decimal con 2 decimales)
            patron_monto = r'(\d+\.\d{2})'
            
            fecha_encontrada = None
            folio_encontrado = None
            monto_encontrado = None
            
            # Buscar fecha/hora
            for patron in patrones_fecha:
                match = re.search(patron, codigo)
                if match:
                    fecha_str = match.group(1)
                    try:
                        if 'T' in fecha_str:
                            fecha_encontrada = datetime.strptime(fecha_str, '%Y-%m-%dT%H:%M:%S')
                        elif '/' in fecha_str:
                            fecha_encontrada = datetime.strptime(fecha_str, '%d/%m/%Y %H:%M:%S')
                        elif len(fecha_str) == 14:  # YYYYMMDDHHMMSS
                            fecha_encontrada = datetime.strptime(fecha_str, '%Y%m%d%H%M%S')
                        elif len(fecha_str) == 12:  # YYYYMMDDHHMM (sin segundos)
                            fecha_encontrada = datetime.strptime(fecha_str, '%Y%m%d%H%M')
                        break
                    except ValueError:
                        continue
            
            # Buscar folio (buscar específicamente después de guion bajo o al final)
            # Buscar patrón _XXX_ o _XXX al final
            match_folio = re.search(r'_(\d{3})(?:_|$)', codigo)
            if match_folio:
                folio_encontrado = match_folio.group(1)
            else:
                # Buscar cualquier secuencia de 3 dígitos como respaldo
                folios = re.findall(patron_folio, codigo)
                if folios:
                    folio_encontrado = folios[0]
            
            # Buscar monto
            montos = re.findall(patron_monto, codigo)
            if montos:
                monto_encontrado = float(montos[0])
            
            # Si no se encuentran todos los componentes, usar valores por defecto
            if not fecha_encontrada:
                fecha_encontrada = datetime.now()
            
            if not folio_encontrado:
                # Generar folio basado en timestamp si no se encuentra
                folio_encontrado = str(int(datetime.now().timestamp()) % 1000).zfill(3)
            
            if monto_encontrado is None:
                # Evitar interpretar cadenas numéricas largas como monto
                numeros = re.findall(r'\d+', codigo)
                numeros = [n for n in numeros if 1 <= len(n) <= 6]  # evitar 15+ dígitos
                if numeros:
                    try:
                        monto_encontrado = float(numeros[-1])
                    except ValueError:
                        monto_encontrado = 0.0
                else:
                    monto_encontrado = 0.0
            
            return Ticket(folio_encontrado, fecha_encontrada, monto_encontrado, codigo)
            
        except Exception as e:
            print(f"Error parseando código: {e}")
            return None
    
    def agregar_ticket(self, codigo: str) -> Tuple[bool, str, bool]:
        """
        Agrega un ticket y retorna (éxito, mensaje, mostrar_amarillo)
        """
        ticket = self.parsear_codigo_barras(codigo)
        if not ticket:
            return False, "Código de barras inválido", False
        
        # Verificar si ya existe
        if ticket.folio in self.tickets:
            return False, f"Ticket {ticket.folio} ya existe", False
        
        # Agregar ticket
        self.tickets[ticket.folio] = ticket
        fecha_str = ticket.fecha_hora.strftime('%Y-%m-%d')
        
        if fecha_str not in self.tickets_por_fecha:
            self.tickets_por_fecha[fecha_str] = []
        
        self.tickets_por_fecha[fecha_str].append(ticket)
        
        # Verificar si hay tickets faltantes
        mostrar_amarillo = self._verificar_tickets_faltantes(ticket)
        
        self.guardar_datos()
        return True, f"Ticket {ticket.folio} registrado correctamente", mostrar_amarillo
    
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
                self.tickets_faltantes_detectados.add(str(folio_faltante).zfill(3))
            
            self.ultimo_folio_esperado = folio_actual
            self.contador_advertencia = 3  # Mostrar amarillo por los próximos 3 tickets
            return True
        else:
            # Ticket anterior que llegó tarde
            folio_str = str(folio_actual).zfill(3)
            if folio_str in self.tickets_faltantes_detectados:
                self.tickets_faltantes_detectados.remove(folio_str)
            
            # Si aún hay advertencias pendientes, continuar mostrando amarillo
            if self.contador_advertencia > 0:
                self.contador_advertencia -= 1
                return self.contador_advertencia > 0
            
            return False
    
    def obtener_resumen_detallado(self) -> List[Dict]:
        """
        Genera lista completa de tickets con información de faltantes
        Retorna lista de diccionarios con: folio, status, hora, monto, horario_camaras
        """
        if not self.tickets:
            return []
        
        # Obtener rango de folios
        folios_existentes = [int(f) for f in self.tickets.keys()]
        if not folios_existentes:
            return []
            
        folio_min = min(folios_existentes)
        folio_max = max(folios_existentes)
        
        resultado = []
        
        for folio_num in range(folio_min, folio_max + 1):
            folio_str = str(folio_num).zfill(3)
            
            if folio_str in self.tickets:
                # Ticket existente
                ticket = self.tickets[folio_str]
                resultado.append({
                    'folio': folio_str,
                    'status': 'OK',
                    'hora': ticket.fecha_hora.strftime('%H:%M:%S'),
                    'monto': f"${ticket.monto:.2f}",
                    'horario_camaras': None
                })
            else:
                # Ticket faltante
                ticket_anterior = self._buscar_ticket_cercano(folio_num, -1)
                ticket_posterior = self._buscar_ticket_cercano(folio_num, 1)
                
                horario_camaras = ""
                if ticket_anterior and ticket_posterior:
                    hora_inicio = ticket_anterior.fecha_hora - timedelta(minutes=5)
                    hora_fin = ticket_posterior.fecha_hora + timedelta(minutes=5)
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
                    'folio': folio_str,
                    'status': 'FALTANTE',
                    'hora': '---',
                    'monto': '---',
                    'horario_camaras': horario_camaras
                })
        
        return resultado
    
    def obtener_resumen(self) -> str:
        """Genera un resumen de tickets faltantes y sugerencias de horarios (versión simple)"""
        if not self.tickets_faltantes_detectados:
            return "OK - Ningun ticket faltante"
        
        resumen = f"TICKETS FALTANTES: {len(self.tickets_faltantes_detectados)}\n\n"
        
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
            if folio_buscar < 1 or folio_buscar > 999:
                break
            
            folio_str = str(folio_buscar).zfill(3)
            if folio_str in self.tickets:
                return self.tickets[folio_str]
        
        return None
    
    def cierre_de_caja(self) -> str:
        """Realiza el cierre de caja y prepara para el siguiente turno"""
        resumen = self.obtener_resumen()
        
        # Cambiar turno
        nuevo_turno = "tarde" if self.turno_actual == "mañana" else "mañana"
        
        # Generar reporte de cierre
        total_tickets = len(self.tickets)
        total_monto = sum(ticket.monto for ticket in self.tickets.values())
        
        reporte = f"""
=== CIERRE DE CAJA - TURNO {self.turno_actual.upper()} ===
Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}

Total de tickets procesados: {total_tickets}
Monto total: ${total_monto:.2f}

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
                    'monto': ticket.monto,
                    'codigo_original': ticket.codigo_original
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
                        ticket_data['monto'],
                        ticket_data['codigo_original']
                    )
                    self.tickets[folio] = ticket
                    
                    # Organizar por fecha
                    fecha_str = fecha_hora.strftime('%Y-%m-%d')
                    if fecha_str not in self.tickets_por_fecha:
                        self.tickets_por_fecha[fecha_str] = []
                    self.tickets_por_fecha[fecha_str].append(ticket)
                        
        except Exception as e:
            print(f"Error cargando datos: {e}")