#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba para el Sistema de Control de Tickets
Simula codigos de barras de ejemplo para probar la funcionalidad
"""

from ticket_manager import TicketManager
from datetime import datetime, timedelta

def test_ticket_manager():
    """Prueba el funcionamiento del TicketManager"""
    print("=== PRUEBA DEL SISTEMA DE TICKETS ===\n")
    
    # Crear instancia del manejador
    tm = TicketManager()
    
    # Códigos de barras de prueba (simulando diferentes formatos)
    codigos_prueba = [
        "2025-10-13T09:15:30_001_125.50",  # Formato ISO con guiones bajos
        "13/10/2025 09:20:15_002_89.75",   # Formato fecha español
        "20251013092500003198.25",         # Formato compacto
        # Omitimos 004 intencionalmente para probar detección de faltantes
        "2025-10-13T09:35:45_005_67.80",  # Salta el 004
        "2025-10-13T09:40:12_006_156.90",
        "2025-10-13T09:42:30_004_201.15", # El 004 llega tarde
        "2025-10-13T09:45:10_007_78.60",
    ]
    
    print("Procesando tickets de prueba...\n")
    
    for i, codigo in enumerate(codigos_prueba, 1):
        print(f"Escaneando código {i}: {codigo}")
        exito, mensaje, mostrar_amarillo = tm.agregar_ticket(codigo)
        
        if exito:
            color = "🟡 AMARILLO" if mostrar_amarillo else "🟢 VERDE"
            print(f"   ✅ {mensaje} - Pantalla: {color}")
        else:
            print(f"   ❌ {mensaje}")
        
        print(f"   Faltantes actuales: {list(tm.tickets_faltantes_detectados)}")
        print(f"   Contador advertencia: {tm.contador_advertencia}")
        print()
    
    # Mostrar resumen final
    print("=== RESUMEN FINAL ===")
    resumen = tm.obtener_resumen()
    print(resumen)
    
    # Probar cierre de caja
    print("\n=== SIMULANDO CIERRE DE CAJA ===")
    resultado_cierre = tm.cierre_de_caja()
    print(resultado_cierre)

def test_parseo_codigos():
    """Prueba diferentes formatos de códigos de barras"""
    print("\n=== PRUEBA DE PARSEO DE CÓDIGOS ===\n")
    
    tm = TicketManager()
    
    # Diferentes formatos de código
    formatos_prueba = [
        "2025-10-13T14:30:25_123_99.99",     # ISO con separadores
        "13/10/2025 14:30:25_124_149.50",    # Español con separadores
        "20251013143025125199.75",           # Compacto
        "131020251430126250.00",             # Compacto alternativo
        "INICIO2025-10-13T14:35:00_127_75.25FIN", # Con prefijo/sufijo
        "CODE128:20251013144000128189.99END", # Con etiquetas
    ]
    
    for codigo in formatos_prueba:
        print(f"Probando: {codigo}")
        ticket = tm.parsear_codigo_barras(codigo)
        if ticket:
            print(f"   ✅ Parseado: Folio {ticket.folio}, "
                  f"Fecha {ticket.fecha_hora.strftime('%d/%m/%Y %H:%M:%S')}, "
                  f"Monto ${ticket.monto:.2f}")
        else:
            print(f"   ❌ No se pudo parsear")
        print()

if __name__ == "__main__":
    try:
        test_parseo_codigos()
        test_ticket_manager()
        print("\n🎉 ¡Todas las pruebas completadas exitosamente!")
        
    except Exception as e:
        print(f"\n❌ Error en las pruebas: {e}")
        import traceback
        traceback.print_exc()