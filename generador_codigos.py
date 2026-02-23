#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de códigos de barras para el Sistema de Control de Tickets
Ayuda a generar códigos de prueba y valida el formato estándar
"""

from datetime import datetime, timedelta
import random

class GeneradorCodigosBarras:
    """Genera códigos de barras en el formato estándar para pruebas y validación"""
    
    def __init__(self):
        self.formato_estandar = "HHMMSS'FFF"
        self.ultimo_folio = 0
        self.fecha_actual = datetime.now()
    
    def generar_codigo_estandar(self, folio=None, fecha_hora=None):
        """
        Genera un código de barras CODE 128 en formato estándar
        HHMMSS'FFF (solo hora y folio, sin monto)
        Ejemplo: 081021'004
        """
        # Usar valores por defecto si no se proporcionan
        if fecha_hora is None:
            fecha_hora = self.fecha_actual
        
        if folio is None:
            self.ultimo_folio += 1
            folio = self.ultimo_folio
        
        # Formatear componentes
        hora_str = fecha_hora.strftime("%H%M%S")
        folio_str = str(folio).zfill(3)  # 001, 002, etc.
        
        return f"{hora_str}'{folio_str}"
    
    def generar_secuencia_prueba(self, cantidad=10, saltar_folio=None):
        """
        Genera una secuencia de códigos para pruebas
        Opcionalmente omite un folio para probar detección de faltantes
        """
        codigos = []
        base_time = datetime.now()
        
        for i in range(1, cantidad + 1):
            # Saltar folio si se especifica
            if saltar_folio and i == saltar_folio:
                continue
                
            # Incrementar tiempo por cada ticket (1-3 minutos entre tickets)
            tiempo_ticket = base_time + timedelta(minutes=i * random.randint(1, 3))
            
            codigo = self.generar_codigo_estandar(i, tiempo_ticket)
            codigos.append({
                'folio': i,
                'codigo': codigo,
                'tiempo': tiempo_ticket.strftime('%H:%M:%S')
            })
        
        return codigos
    
    def validar_formato(self, codigo):
        """Valida que un código cumpla con el formato estándar CODE 128"""
        import re
        
        patron = r"^(\d{6})'(\d{3})$"
        match = re.match(patron, codigo)
        
        if not match:
            return False, f"Formato incorrecto. Debe ser: HHMMSS'FFF (ejemplo: 081021'004)"
        
        hora_str, folio_str = match.groups()
        
        # Validar hora
        try:
            hora_int = int(hora_str[:2])
            minuto_int = int(hora_str[2:4])
            segundo_int = int(hora_str[4:6])
            
            if not (0 <= hora_int < 24):
                return False, "Hora debe estar entre 00 y 23"
            if not (0 <= minuto_int < 60):
                return False, "Minuto debe estar entre 00 y 59"
            if not (0 <= segundo_int < 60):
                return False, "Segundo debe estar entre 00 y 59"
                
        except ValueError:
            return False, "Hora/minuto/segundo inválidos"
        
        # Validar folio (001-999)
        folio_num = int(folio_str)
        if folio_num < 1 or folio_num > 999:
            return False, "Folio debe estar entre 001 y 999"
        
        return True, f"Válido - Folio: {folio_num}, Hora: {hora_str[:2]}:{hora_str[2:4]}:{hora_str[4:6]}"

def main():
    """Función principal para pruebas"""
    print("=== GENERADOR DE CODIGOS DE BARRAS ===\n")
    
    generador = GeneradorCodigosBarras()
    
    # Generar códigos individuales
    print("1. CÓDIGOS INDIVIDUALES DE EJEMPLO:")
    for i in range(5):
        codigo = generador.generar_codigo_estandar()
        print(f"   {codigo}")
    
    print("\n2. SECUENCIA DE PRUEBA (con folio 003 faltante):")
    secuencia = generador.generar_secuencia_prueba(8, saltar_folio=3)
    
    for item in secuencia:
        print(f"   Folio {item['folio']:03d}: {item['codigo']} (${item['monto']:.2f} a las {item['tiempo']})")
    
    # Agregar el folio faltante al final
    codigo_tardio = generador.generar_codigo_estandar(
        folio=3, 
        monto=67.50, 
        fecha_hora=datetime.now() - timedelta(minutes=15)
    )
    print(f"   Folio 003: {codigo_tardio} (TARDÍO)")
    
    print("\n3. VALIDACIÓN DE FORMATOS:")
    
    # Códigos para validar
    codigos_prueba = [
        generador.generar_codigo_estandar(),  # Válido
        "20251013143025-001-0125.50",         # Válido
        "20251013143025001125.50",            # Inválido (sin separadores)
        "20251013143025-1000-0125.50",        # Inválido (folio > 999)
        "20251013143025-001-10000.00",        # Inválido (monto > 9999.99)
        "invalid-format-here",                # Inválido (formato completamente incorrecto)
    ]
    
    for codigo in codigos_prueba:
        valido, mensaje = generador.validar_formato(codigo)
        estado = "✅ VÁLIDO" if valido else "❌ INVÁLIDO"
        print(f"   {estado}: {codigo}")
        print(f"              {mensaje}\n")
    
    print("4. PARA TU APP DE IMPRESIÓN:")
    print("   Usa este código base para generar códigos:")
    print(f"""
   // JavaScript
   function generarCodigoTicket(folio, monto) {{
       const now = new Date();
       const fecha = now.getFullYear().toString() +
                     (now.getMonth() + 1).toString().padStart(2, '0') +
                     now.getDate().toString().padStart(2, '0') +
                     now.getHours().toString().padStart(2, '0') +
                     now.getMinutes().toString().padStart(2, '0') +
                     now.getSeconds().toString().padStart(2, '0');
       
       const folioStr = folio.toString().padStart(3, '0');
       const montoStr = parseFloat(monto).toFixed(2).padStart(7, '0');
       
       return `${{fecha}}-${{folioStr}}-${{montoStr}}`;
   }}
   
   // Ejemplo de uso:
   let codigo = generarCodigoTicket(1, 125.50);
   // Resultado: "{datetime.now().strftime('%Y%m%d%H%M%S')}-001-0125.50"
   """)

if __name__ == "__main__":
    main()