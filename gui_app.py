import re
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
from ticket_manager import TicketManager

class PantallaConfirmacion:
    """Ventana de confirmación verde/amarilla que aparece al registrar tickets"""
    
    def __init__(self, parent, es_advertencia=False, mensaje="Ticket registrado"):
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("Confirmación")
        
        # Configurar ventana
        self.ventana.geometry("400x200")
        self.ventana.resizable(False, False)
        self.ventana.transient(parent)
        self.ventana.grab_set()
        # Forzar siempre visible sobre otras ventanas (solo esta confirmación)
        try:
            self.ventana.attributes("-topmost", True)
        except Exception:
            pass
        
        # Centrar en pantalla
        self.ventana.update_idletasks()
        x = (self.ventana.winfo_screenwidth() // 2) - (400 // 2)
        y = (self.ventana.winfo_screenheight() // 2) - (200 // 2)
        self.ventana.geometry(f"400x200+{x}+{y}")
        
        # Color de fondo
        color_fondo = "#FFD700" if es_advertencia else "#00FF00"  # Amarillo o verde fosforescente
        self.ventana.configure(bg=color_fondo)
        
        # Etiqueta principal
        label = tk.Label(
            self.ventana,
            text=mensaje,
            font=("Arial", 16, "bold"),
            bg=color_fondo,
            fg="black" if es_advertencia else "white",
            wraplength=350
        )
        label.pack(expand=True)
        
        # Auto-cerrar después de 1.5 segundos
        self.ventana.after(1500, self.cerrar)
        
        # También permitir cerrar con clic o tecla
        self.ventana.bind("<Button-1>", lambda e: self.cerrar())
        self.ventana.bind("<Key>", lambda e: self.cerrar())
        self.ventana.focus_set()
    
    def cerrar(self):
        if self.ventana.winfo_exists():
            self.ventana.destroy()

class AplicacionTickets:
    """Aplicación principal para el manejo de tickets de carnicería"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Sistema de Control de Tickets - Carnicería")
        self.root.geometry("800x600")
        self.root.configure(bg="#f0f0f0")
        
        # Inicializar el manejador de tickets
        self.ticket_manager = TicketManager()
        
        # Variable para el código de barras
        self.codigo_var = tk.StringVar()
        self.codigo_var.trace('w', self.on_codigo_change)
        
        # Modo cancelado
        self.modo_cancelado = False
        
        # Configurar interfaz
        self.crear_interfaz()
        
        # Focus en campo de entrada
        self.entrada_codigo.focus_set()
    
    def crear_interfaz(self):
        """Crea la interfaz gráfica principal"""
        
        # Título principal
        titulo = tk.Label(
            self.root,
            text="Sistema de Control de Tickets",
            font=("Arial", 20, "bold"),
            bg="#f0f0f0",
            fg="#2c3e50"
        )
        titulo.pack(pady=20)
        
        # Subtítulo con turno actual
        self.subtitulo = tk.Label(
            self.root,
            text=f"Turno: {self.ticket_manager.turno_actual.upper()}",
            font=("Arial", 14),
            bg="#f0f0f0",
            fg="#34495e"
        )
        self.subtitulo.pack(pady=(0, 20))
        
        # Frame para entrada de código
        frame_entrada = tk.Frame(self.root, bg="#f0f0f0")
        frame_entrada.pack(pady=20)
        
        tk.Label(
            frame_entrada,
            text="Escanear código de barras:",
            font=("Arial", 12),
            bg="#f0f0f0"
        ).pack()
        
        self.entrada_codigo = tk.Entry(
            frame_entrada,
            textvariable=self.codigo_var,
            font=("Arial", 14),
            width=40,
            justify="center"
        )
        self.entrada_codigo.pack(pady=10)
        self.entrada_codigo.bind("<Return>", self.procesar_codigo_manual)
        
        # Instrucciones
        instrucciones = tk.Label(
            self.root,
            text="El código se procesará automáticamente al escanear",
            font=("Arial", 10, "italic"),
            bg="#f0f0f0",
            fg="#7f8c8d"
        )
        instrucciones.pack(pady=(0, 20))
        
        # Frame para botones principales
        frame_botones = tk.Frame(self.root, bg="#f0f0f0")
        frame_botones.pack(pady=20)
        
        # Botón de resumen
        btn_resumen = tk.Button(
            frame_botones,
            text="📊 Ver Resumen",
            command=self.mostrar_resumen,
            font=("Arial", 12, "bold"),
            bg="#3498db",
            fg="white",
            width=15,
            height=2,
            relief="raised",
            bd=3
        )
        btn_resumen.pack(side="left", padx=10)
        
        # Botón de cierre de caja
        btn_cierre = tk.Button(
            frame_botones,
            text="🔒 Cierre de Caja",
            command=self.cierre_de_caja,
            font=("Arial", 12, "bold"),
            bg="#e74c3c",
            fg="white",
            width=15,
            height=2,
            relief="raised",
            bd=3
        )
        btn_cierre.pack(side="left", padx=10)

        # Botón para agregar ticket CANCELADO
        btn_cancelado = tk.Button(
            frame_botones,
            text="➖ Agregar Cancelado",
            command=self.procesar_ticket_cancelado,
            font=("Arial", 12, "bold"),
            bg="#f39c12",
            fg="white",
            width=18,
            height=2,
            relief="raised",
            bd=3
        )
        btn_cancelado.pack(side="left", padx=10)
        
        # Botón para imprimir resumen
        btn_imprimir = tk.Button(
            frame_botones,
            text="🖨️ Imprimir Resumen",
            command=self.imprimir_resumen,
            font=("Arial", 12, "bold"),
            bg="#27ae60",
            fg="white",
            width=18,
            height=2,
            relief="raised",
            bd=3
        )
        btn_imprimir.pack(side="left", padx=10)

        # Checkbox: Siempre visible (investigación: usa atributo topmost)
        self.topmost_var = tk.BooleanVar(value=False)
        chk_topmost = tk.Checkbutton(
            self.root,
            text="Siempre visible",
            variable=self.topmost_var,
            command=self.toggle_topmost,
            bg="#f0f0f0",
            font=("Arial", 10)
        )
        chk_topmost.pack(pady=(0, 10))
        
        # Estadísticas actuales
        self.frame_stats = tk.LabelFrame(
            self.root,
            text="Estadísticas del Turno Actual",
            font=("Arial", 12, "bold"),
            bg="#f0f0f0",
            fg="#2c3e50"
        )
        self.frame_stats.pack(pady=20, padx=20, fill="x")
        
        self.label_stats = tk.Label(
            self.frame_stats,
            text="",
            font=("Arial", 11),
            bg="#f0f0f0",
            justify="left"
        )
        self.label_stats.pack(pady=10, padx=10)
        
        # Actualizar estadísticas
        self.actualizar_estadisticas()
        
        # Area de log (oculta por defecto, se puede mostrar para debug)
        self.log_visible = False

    def _codigo_parece_completo(self, codigo: str) -> bool:
        """Valida si el escaneo ya tiene todos los fragmentos esperados"""
        codigo_limpio = codigo.strip()
        if not codigo_limpio:
            return False

        codigo_norm = re.sub(r'[^0-9\.]', '', codigo_limpio)

        patrones_norm = [
            r'^\d{6}\d{3,4}\d{4}\.\d{2}$',  # HHMMSS + folio + monto con punto
            r'^\d{6}\d{3,4}\d{4}\d{2}$',     # HHMMSS + folio + monto sin punto
        ]

        if any(re.fullmatch(p, codigo_norm) for p in patrones_norm):
            return True

        # Si el escáner envía Enter/CR al final, úsalo como señal de fin
        if (codigo_limpio.endswith('\n') or codigo_limpio.endswith('\r')) and len(codigo_norm) >= 12:
            return True

        # Permitir formatos largos con fecha completa + folio + monto
        if len(codigo_norm) >= 18 and re.search(r'\d{14}', codigo_norm):
            return True

        return False
    
    def on_codigo_change(self, *args):
        """Se ejecuta cuando cambia el contenido del campo de código"""
        codigo = self.codigo_var.get()

        # Procesar solo cuando el código parece completo para evitar lecturas parciales
        if not hasattr(self, '_procesando') and self._codigo_parece_completo(codigo):
            self._procesando = True
            if self.modo_cancelado:
                self.root.after(50, self.procesar_codigo_cancelado_auto)
            else:
                self.root.after(50, self.procesar_codigo_automatico)

    def procesar_codigo_manual(self, event=None):
        """Procesa cuando el escáner envía Enter al finalizar el código"""
        codigo = self.codigo_var.get().strip()
        if not codigo:
            return

        if self.modo_cancelado:
            self.procesar_ticket_cancelado_codigo(codigo)
        else:
            self.procesar_ticket(codigo)
        self.codigo_var.set("")
        self.entrada_codigo.focus_set()
        if hasattr(self, '_procesando'):
            delattr(self, '_procesando')
    
    def procesar_codigo_cancelado_auto(self):
        """Procesa automáticamente en modo cancelado después de un delay"""
        try:
            codigo = self.codigo_var.get().strip()
            if codigo:
                self.procesar_ticket_cancelado_codigo(codigo)
                self.codigo_var.set("")
        finally:
            if hasattr(self, '_procesando'):
                delattr(self, '_procesando')
            self.entrada_codigo.focus_set()
    
    def procesar_ticket_cancelado_codigo(self, codigo):
        """Procesa un código como cancelado"""
        try:
            exito, mensaje, _ = self.ticket_manager.agregar_ticket_cancelado(codigo)
            if exito:
                PantallaConfirmacion(self.root, es_advertencia=True, mensaje=mensaje)
                self.actualizar_estadisticas()
                # Salir del modo cancelado después de procesar
                self.modo_cancelado = False
            else:
                messagebox.showerror("Error", mensaje)
        except Exception as e:
            messagebox.showerror("Error", f"Error procesando cancelado: {str(e)}")
    
    def procesar_codigo_automatico(self):
        """Procesa el código automáticamente después de un breve delay"""
        try:
            codigo = self.codigo_var.get().strip()
            if codigo:
                self.procesar_ticket(codigo)
                # Limpiar campo para próximo código
                self.codigo_var.set("")
        finally:
            if hasattr(self, '_procesando'):
                delattr(self, '_procesando')
            
            # Mantener focus en el campo de entrada
            self.entrada_codigo.focus_set()
    
    def procesar_ticket(self, codigo):
        """Procesa un ticket y muestra la confirmación correspondiente"""
        try:
            exito, mensaje, mostrar_amarillo = self.ticket_manager.agregar_ticket(codigo)
            
            if exito:
                # Mostrar pantalla de confirmación
                PantallaConfirmacion(
                    self.root,
                    es_advertencia=mostrar_amarillo,
                    mensaje=mensaje
                )
                
                # Actualizar estadísticas
                self.actualizar_estadisticas()
                
            else:
                # Error al procesar
                messagebox.showerror("Error", mensaje)
                
        except Exception as e:
            messagebox.showerror("Error", f"Error procesando ticket: {str(e)}")

    def procesar_ticket_cancelado(self):
        """Cambia a modo cancelado para escanear el ticket a cancelar"""
        # Cambiar modo a cancelado (sin bloquear con messagebox)
        self.modo_cancelado = True
        self.entrada_codigo.focus_set()
        messagebox.showinfo(
            "Modo Cancelado",
            "Escanea o escribe el código a cancelar.\n(Se procesará automáticamente)"
        )
        self.entrada_codigo.focus_set()
    
    def actualizar_estadisticas(self):
        """Actualiza las estadísticas mostradas en pantalla (solo datos confiables)"""
        stats = self.ticket_manager.obtener_estadisticas_turno()

        stats_text = (
            f"Tickets OK: {stats['total_ok']}\n"
            f"Cancelados: {stats['total_cancelados']}\n"
            f"Total escaneados: {stats['total_escaneados']}\n"
            f"Monto acumulado: ${stats['monto_ok']:.2f}"
        )

        if stats['monto_cancelado'] > 0:
            stats_text += f"\nMonto cancelado (no suma): ${stats['monto_cancelado']:.2f}"
        
        self.label_stats.config(text=stats_text)
        
        # Actualizar subtítulo con turno
        self.subtitulo.config(text=f"Turno: {self.ticket_manager.turno_actual.upper()}")
    
    def mostrar_resumen(self):
        """Muestra el resumen completo de tickets con faltantes en rojo"""
        tickets_detalle = self.ticket_manager.obtener_resumen_detallado()
        
        # Crear ventana de resumen
        ventana_resumen = tk.Toplevel(self.root)
        ventana_resumen.title("Resumen Completo de Tickets")
        ventana_resumen.geometry("800x500")
        ventana_resumen.transient(self.root)
        
        # Centrar ventana
        ventana_resumen.update_idletasks()
        x = (ventana_resumen.winfo_screenwidth() // 2) - (400)
        y = (ventana_resumen.winfo_screenheight() // 2) - (250)
        ventana_resumen.geometry(f"800x500+{x}+{y}")
        
        # Título
        titulo = tk.Label(
            ventana_resumen,
            text="Resumen Completo de Tickets del Turno",
            font=("Arial", 14, "bold"),
            bg="#f0f0f0"
        )
        titulo.pack(pady=10)
        
        # Frame con scroll para la lista
        frame_scroll = tk.Frame(ventana_resumen)
        frame_scroll.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Crear canvas y scrollbar
        canvas = tk.Canvas(frame_scroll, bg="white")
        scrollbar = tk.Scrollbar(frame_scroll, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="white")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Encabezados
        header_frame = tk.Frame(scrollable_frame, bg="#34495e")
        header_frame.pack(fill="x", padx=5, pady=5)
        
        tk.Label(header_frame, text="Folio", font=("Arial", 10, "bold"), 
                bg="#34495e", fg="white", width=10).pack(side="left", padx=5)
        tk.Label(header_frame, text="Estado", font=("Arial", 10, "bold"), 
                bg="#34495e", fg="white", width=12).pack(side="left", padx=5)
        tk.Label(header_frame, text="Hora", font=("Arial", 10, "bold"), 
                bg="#34495e", fg="white", width=12).pack(side="left", padx=5)
        tk.Label(header_frame, text="Monto", font=("Arial", 10, "bold"), 
                bg="#34495e", fg="white", width=12).pack(side="left", padx=5)
        tk.Label(header_frame, text="Revisar Cámaras", font=("Arial", 10, "bold"), 
                bg="#34495e", fg="white", width=20).pack(side="left", padx=5)
        
        # Contador de faltantes
        total_faltantes = sum(1 for t in tickets_detalle if t['status'] == 'FALTANTE')
        
        # Mostrar tickets
        if not tickets_detalle:
            tk.Label(
                scrollable_frame,
                text="No hay tickets registrados aún",
                font=("Arial", 12),
                bg="white",
                fg="#7f8c8d"
            ).pack(pady=20)
        else:
            for ticket in tickets_detalle:
                if ticket['status'] == 'FALTANTE':
                    # Ticket faltante en ROJO
                    fila_frame = tk.Frame(scrollable_frame, bg="#ffcccc", bd=1, relief="solid")
                    fila_frame.pack(fill="x", padx=5, pady=2)
                    
                    tk.Label(fila_frame, text=ticket['folio'], font=("Arial", 10, "bold"), 
                            bg="#ffcccc", fg="#c0392b", width=10).pack(side="left", padx=5)
                    tk.Label(fila_frame, text="⚠️ FALTANTE", font=("Arial", 10, "bold"), 
                            bg="#ffcccc", fg="#c0392b", width=12).pack(side="left", padx=5)
                    tk.Label(fila_frame, text=ticket['hora'], font=("Arial", 10), 
                            bg="#ffcccc", fg="#c0392b", width=12).pack(side="left", padx=5)
                    tk.Label(fila_frame, text=ticket['monto'], font=("Arial", 10), 
                            bg="#ffcccc", fg="#c0392b", width=12).pack(side="left", padx=5)
                    tk.Label(fila_frame, text=ticket['horario_camaras'], font=("Arial", 10, "bold"), 
                            bg="#ffcccc", fg="#c0392b", width=20).pack(side="left", padx=5)
                elif ticket['status'] == 'CANCELADO':
                    # Ticket cancelado en GRIS
                    fila_frame = tk.Frame(scrollable_frame, bg="#eeeeee", bd=1, relief="solid")
                    fila_frame.pack(fill="x", padx=5, pady=2)
                    
                    tk.Label(fila_frame, text=ticket['folio'], font=("Arial", 10), 
                            bg="#eeeeee", fg="#7f8c8d", width=10).pack(side="left", padx=5)
                    tk.Label(fila_frame, text="✖ CANCELADO", font=("Arial", 10, "bold"), 
                            bg="#eeeeee", fg="#7f8c8d", width=12).pack(side="left", padx=5)
                    tk.Label(fila_frame, text=ticket['hora'], font=("Arial", 10), 
                            bg="#eeeeee", fg="#7f8c8d", width=12).pack(side="left", padx=5)
                    tk.Label(fila_frame, text=ticket['monto'], font=("Arial", 10), 
                            bg="#eeeeee", fg="#7f8c8d", width=12).pack(side="left", padx=5)
                    tk.Label(fila_frame, text="(no suma)", font=("Arial", 10, "italic"), 
                            bg="#eeeeee", fg="#7f8c8d", width=20).pack(side="left", padx=5)
                else:
                    # Ticket OK en blanco
                    fila_frame = tk.Frame(scrollable_frame, bg="white", bd=1, relief="flat")
                    fila_frame.pack(fill="x", padx=5, pady=1)
                    
                    tk.Label(fila_frame, text=ticket['folio'], font=("Arial", 10), 
                            bg="white", fg="#2c3e50", width=10).pack(side="left", padx=5)
                    tk.Label(fila_frame, text="✓ OK", font=("Arial", 10), 
                            bg="white", fg="#27ae60", width=12).pack(side="left", padx=5)
                    tk.Label(fila_frame, text=ticket['hora'], font=("Arial", 10), 
                            bg="white", fg="#2c3e50", width=12).pack(side="left", padx=5)
                    tk.Label(fila_frame, text=ticket['monto'], font=("Arial", 10), 
                            bg="white", fg="#2c3e50", width=12).pack(side="left", padx=5)
                    tk.Label(fila_frame, text="", font=("Arial", 10), 
                            bg="white", fg="#2c3e50", width=20).pack(side="left", padx=5)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Resumen al final
        resumen_frame = tk.Frame(ventana_resumen, bg="#ecf0f1")
        resumen_frame.pack(fill="x", padx=20, pady=10)
        
        if total_faltantes > 0:
            tk.Label(
                resumen_frame,
                text=f"⚠️ ATENCIÓN: {total_faltantes} ticket(s) faltante(s) detectado(s)",
                font=("Arial", 12, "bold"),
                bg="#ecf0f1",
                fg="#c0392b"
            ).pack()
        else:
            tk.Label(
                resumen_frame,
                text="✓ Todos los tickets en orden",
                font=("Arial", 12, "bold"),
                bg="#ecf0f1",
                fg="#27ae60"
            ).pack()

        stats = self.ticket_manager.obtener_estadisticas_turno()
        tk.Label(
            resumen_frame,
            text=(
                f"Cancelados en turno: {stats['total_cancelados']}  "
                f"(monto cancelado: ${stats['monto_cancelado']:.2f})"
            ),
            font=("Arial", 11),
            bg="#ecf0f1",
            fg="#7f8c8d"
        ).pack(pady=(8, 0))
        
        # Botón cerrar
        btn_cerrar = tk.Button(
            ventana_resumen,
            text="Cerrar",
            command=ventana_resumen.destroy,
            font=("Arial", 12),
            bg="#95a5a6",
            fg="white",
            width=10
        )
        btn_cerrar.pack(pady=(0, 20))

    def toggle_topmost(self):
        """Activa/Desactiva que la ventana principal quede siempre visible"""
        try:
            self.root.attributes("-topmost", bool(self.topmost_var.get()))
        except Exception:
            pass
    
    def cierre_de_caja(self):
        """Realiza el cierre de caja con confirmación"""
        # Confirmar cierre
        respuesta = messagebox.askyesno(
            "Confirmar Cierre",
            f"¿Está seguro de realizar el cierre de caja del turno {self.ticket_manager.turno_actual}?\n\n"
            "Esta acción generará un reporte y reiniciará el contador de tickets.",
            icon="warning"
        )
        
        if respuesta:
            try:
                mensaje = self.ticket_manager.cierre_de_caja()
                
                # Mostrar resultado
                messagebox.showinfo("Cierre Completado", mensaje)
                
                # Actualizar interfaz
                self.actualizar_estadisticas()
                
                # Limpiar campo de entrada
                self.codigo_var.set("")
                self.entrada_codigo.focus_set()
                
            except Exception as e:
                messagebox.showerror("Error", f"Error en cierre de caja: {str(e)}")
    
    def ejecutar(self):
        """Ejecuta la aplicación principal"""
        # Configurar evento de cierre
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Ejecutar loop principal
        self.root.mainloop()
    
    def on_closing(self):
        """Maneja el cierre de la aplicación"""
        if messagebox.askokcancel("Salir", "¿Desea salir del sistema de tickets?"):
            self.root.destroy()
    
    def imprimir_resumen(self):
        """Imprime el resumen en la impresora térmica POS"""
        try:
            resumen_texto = self._generar_resumen_impresion()
            exito = self._enviar_a_impresora(resumen_texto)
            if exito:
                messagebox.showinfo("Impresión", "Resumen enviado a la impresora.")
            else:
                messagebox.showerror("Error", "No se pudo enviar a la impresora. Verifica que esté disponible.")
        except Exception as e:
            messagebox.showerror("Error", f"Error imprimiendo: {str(e)}")
    
    def _generar_resumen_impresion(self) -> str:
        """Genera el texto formateado para la impresora térmica (57mm)"""
        import datetime
        
        stats = self.ticket_manager.obtener_estadisticas_turno()
        tickets_detalle = self.ticket_manager.obtener_resumen_detallado()
        
        # Ancho para impresora térmica 57mm (aprox 32 caracteres)
        ancho = 32
        
        linea_sep = "=" * ancho
        
        # Encabezado
        lineas = [
            linea_sep,
            "CIERRE DE CAJA - TURNO",
            self.ticket_manager.turno_actual.upper(),
            linea_sep,
            f"Fecha: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}",
            "",
            f"Total de tickets procesados:",
            f"{stats['total_ok']}",
            f"Monto total: ${stats['monto_ok']:.2f}",
            ""
        ]
        
        # Cancelados si hay
        if stats['total_cancelados'] > 0:
            lineas.append(f"\nTICKETS CANCELADOS: {stats['total_cancelados']}")
            lineas.append(f"Monto cancelado (no suma): ${stats['monto_cancelado']:.2f}")
            lineas.append("")
        
        # Tickets faltantes
        total_faltantes = sum(1 for t in tickets_detalle if t['status'] == 'FALTANTE')
        if total_faltantes > 0:
            lineas.append(f"TICKETS FALTANTES: {total_faltantes}")
            lineas.append(linea_sep)
            
            for ticket in tickets_detalle:
                if ticket['status'] == 'FALTANTE':
                    folio_str = f"Folio {ticket['folio']}"
                    lineas.append(folio_str)
                    lineas.append(f"Revisar camaras:")
                    if ticket['horario_camaras']:
                        # Partir el horario en dos líneas si es necesario
                        horario = ticket['horario_camaras']
                        if len(horario) > ancho:
                            parts = horario.split(' - ')
                            lineas.append(parts[0])
                            if len(parts) > 1:
                                lineas.append("a " + parts[1])
                        else:
                            lineas.append(horario)
                    lineas.append("")
        else:
            lineas.append("TICKETS FALTANTES: 0")
            lineas.append("Todos los tickets en orden")
            lineas.append("")
        
        # Pie de página
        lineas.append(linea_sep)
        lineas.append(f"Próximo turno: {'tarde' if self.ticket_manager.turno_actual == 'mañana' else 'mañana'}")
        lineas.append(linea_sep)
        lineas.append("")  # Salto final para el papel
        
        return "\n".join(lineas)
    
    def _enviar_a_impresora(self, texto: str) -> bool:
        """Envía el texto a la impresora térmica POS predeterminada"""
        try:
            import subprocess
            import os
            
            # Crear archivo temporal con el contenido
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(texto)
                temp_file = f.name
            
            try:
                # Enviar a la impresora predeterminada en Windows
                # Usar comando de impresión directa sin abrir diálogo
                subprocess.run(
                    ["notepad.exe", "/p", temp_file],
                    check=True,
                    capture_output=True,
                    timeout=10
                )
                return True
            finally:
                # Limpiar archivo temporal
                try:
                    os.remove(temp_file)
                except:
                    pass
                    
        except subprocess.TimeoutExpired:
            return False
        except Exception as e:
            print(f"Error en impresora: {e}")
            return False

def main():
    """Función principal"""
    try:
        app = AplicacionTickets()
        app.ejecutar()
    except Exception as e:
        messagebox.showerror("Error Fatal", f"Error iniciando aplicación: {str(e)}")

if __name__ == "__main__":
    main()