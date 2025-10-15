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
        self.formato_estandar = "YYYYMMDDHHMMSS-FFF-MMMM.CC"
        self.ultimo_folio = 0
        self.fecha_actual = datetime.now()
    
    def generar_codigo_estandar(self, folio=None, monto=None, fecha_hora=None):
        """
        Genera un código de barras en formato estándar
        YYYYMMDDHHMMSS-FFF-MMMM.CC
        """
        # Usar valores por defecto si no se proporcionan
        if fecha_hora is None:
            fecha_hora = self.fecha_actual
        
        if folio is None:
            self.ultimo_folio += 1
            folio = self.ultimo_folio
        
        if monto is None:
            monto = round(random.uniform(25.00, 500.00), 2)
        
        # Formatear componentes
        fecha_str = fecha_hora.strftime("%Y%m%d%H%M%S")
        folio_str = str(folio).zfill(3)  # 001, 002, etc.
        monto_str = f"{float(monto):07.2f}"  # 0125.50, 0089.75, etc.
        
        return f"{fecha_str}-{folio_str}-{monto_str}"
    
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
            monto = round(random.uniform(45.25, 350.75), 2)
            
            codigo = self.generar_codigo_estandar(i, monto, tiempo_ticket)
            codigos.append({
                'folio': i,
                'codigo': codigo,
                'monto': monto,
                'tiempo': tiempo_ticket.strftime('%H:%M:%S')
            })
        
        return codigos
    
    def validar_formato(self, codigo):
        """Valida que un código cumpla con el formato estándar"""
        import re
        
        patron = r'^(\d{14})-(\d{3})-(\d{4}\.\d{2})$'
        match = re.match(patron, codigo)
        
        if not match:
            return False, "Formato incorrecto. Debe ser: YYYYMMDDHHMMSS-FFF-MMMM.CC"
        
        fecha_str, folio_str, monto_str = match.groups()
        
        # Validar fecha
        try:
            fecha = datetime.strptime(fecha_str, '%Y%m%d%H%M%S')
        except ValueError:
            return False, "Fecha/hora inválida en el código"
        
        # Validar folio (001-999)
        folio_num = int(folio_str)
        if folio_num < 1 or folio_num > 999:
            return False, "Folio debe estar entre 001 y 999"
        
        # Validar monto (0000.01 - 9999.99)
        try:
            monto = float(monto_str)
            if monto <= 0 or monto > 9999.99:
                return False, "Monto debe estar entre 0000.01 y 9999.99"
        except ValueError:
            return False, "Formato de monto inválido"
        
        return True, f"Válido - Folio: {folio_num}, Monto: ${monto:.2f}, Fecha: {fecha.strftime('%d/%m/%Y %H:%M:%S')}"

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