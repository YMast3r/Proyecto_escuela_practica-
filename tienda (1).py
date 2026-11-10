# Importaciones: interfaz gráfica, conexión MySQL, mensajes y herramientas para clases abstractas.
import customtkinter as ctk
import mysql.connector
from mysql.connector import Error
import tkinter.messagebox as messagebox
from abc import ABC, abstractmethod

# Configura el tema visual general de la aplicación.
ctk.set_appearance_mode("Light")

# Constantes de colores reutilizadas en las distintas ventanas para mantener un diseño uniforme.
COLOR_BG_PANEL = "#f4f7f9"       
COLOR_SIDEBAR = "#aebde6"        
COLOR_SIDEBAR_ACTIVE = "#dce4f2" 
COLOR_CARD = "#ffffff"           
COLOR_PRIMARY = "#334155"        
COLOR_TEXT_MUTED = "#64748b"     
COLOR_BORDER = "#e2e8f0"         
COLOR_SUCCESS_BG = "#d1fae5"     
COLOR_SUCCESS_TXT = "#065f46"    

# CLASE 1: DatabaseHelper. Centraliza la conexión y las operaciones con la base de datos.
class DatabaseHelper:
    # Constructor: inicializa los datos de conexión y reserva el atributo para la conexión activa.
    def __init__(self):
        # Atributos privados (__): guardan la configuración y evitan el acceso directo desde otras clases.
        self.__host = "localhost"
        self.__port = 3003  # Puerto estándar de MySQL/XAMPP (cámbialo a 3003 si usas una configuración personalizada)
        self.__user = "root"
        self.__password = ""
        self.__database = "abarrotes"
        self.__connection = None

    # Abre la conexión con MySQL. Devuelve True si funciona y False si ocurre un error.
    def conectar(self):
        try:
            self.__connection = mysql.connector.connect(
                host=self.__host,
                port=self.__port,
                user=self.__user,
                password=self.__password,
                database=self.__database
            )
            return True
        except Error as e:
            print(f"Error de conexión: {e}")
            self.__connection = None
            return False

    # Ejecuta consultas SQL. 'fetch=True' recupera registros; de lo contrario confirma cambios.
    def ejecutar_consulta(self, query, parametros=None, fetch=False):
        if not self.__connection or not self.__connection.is_connected():
            if not self.conectar():
                return None
        
        cursor = self.__connection.cursor(dictionary=True)
        try:
            cursor.execute(query, parametros or ())
            if fetch:
                filas = cursor.fetchall()
                self.__connection.commit()
                return filas
            self.__connection.commit()
            if query.strip().upper().startswith("INSERT"):
                return cursor.lastrowid
            return cursor.rowcount
        except Error as e:
            print(f"Error en SQL: {e}")
            return None
        finally:
            cursor.close()

    # Crea registros básicos en la base de datos simplificada si se encuentra vacía.
    def inicializar_catalogos(self):
        if not self.conectar(): return False
        
        # Proveedor por defecto
        if not self.ejecutar_consulta("SELECT * FROM proveedor LIMIT 1", fetch=True):
            self.ejecutar_consulta("INSERT INTO proveedor (nombreempresa, telefono) VALUES ('Proveedor General', '0000000000')")
        
        # Usuario Administrador por defecto
        if not self.ejecutar_consulta("SELECT * FROM usuario LIMIT 1", fetch=True):
            self.ejecutar_consulta("INSERT INTO usuario (nombre, correo, passwordhash, rol, turno, activo) VALUES ('Juan', 'Juan@Gmail.com', 'CAMBIAR_POR_HASH', 'Administrador', 'Matutino', 1)")
        return True

# CLASE 2: SesionUsuario. Conserva los datos del usuario que inició sesión.
class SesionUsuario:
    _instancia = None
    def __new__(cls):
        if cls._instancia is None:
            cls._instancia = super(SesionUsuario, cls).__new__(cls)
            cls._instancia.__usuario_actual = None
        return cls._instancia
        
    def set_usuario_actual(self, usuario):
        self.__usuario_actual = usuario

    def iniciar_sesion(self, id_usuario, nombre, rol):
        if id_usuario is None:
            self.set_usuario_actual(None)
        else:
            self.set_usuario_actual({"id": id_usuario, "nombre": nombre, "rol": rol})

    def get_usuario_actual(self):
        return self.__usuario_actual

    def cerrar_sesion(self):
        self.set_usuario_actual(None)


# CLASE 3: Producto. Representa un producto y protege sus atributos mediante encapsulación.
class Producto:
    def __init__(self, idproducto, codigobarras, nombre, idproveedor,
                 preciocompra, precioventa, stockactual, stockminimo=0):
        self.set_idproducto(idproducto)
        self.set_codigobarras(codigobarras)
        self.set_nombre(nombre)
        self.set_idproveedor(idproveedor)
        self.set_preciocompra(preciocompra)
        self.set_precioventa(precioventa)
        self.set_stockactual(stockactual)
        self.set_stockminimo(stockminimo)

    def get_idproducto(self): return self.__idproducto
    def set_idproducto(self, valor): self.__idproducto = None if valor is None else int(valor)

    def get_codigobarras(self): return self.__codigobarras
    def set_codigobarras(self, valor):
        valor = str(valor).strip()
        if not valor: raise ValueError("El código de barras es obligatorio.")
        self.__codigobarras = valor

    def get_nombre(self): return self.__nombre
    def set_nombre(self, valor):
        valor = str(valor).strip()
        if not valor: raise ValueError("El nombre del producto es obligatorio.")
        self.__nombre = valor

    def get_idproveedor(self): return self.__idproveedor
    def set_idproveedor(self, valor):
        if valor in (None, ""): raise ValueError("Selecciona un proveedor.")
        self.__idproveedor = int(valor)

    def get_preciocompra(self): return self.__preciocompra
    def set_preciocompra(self, valor):
        valor = 0.0 if valor in (None, "") else float(valor)
        if valor < 0: raise ValueError("El costo no puede ser negativo.")
        self.__preciocompra = valor

    def get_precioventa(self): return self.__precioventa
    def set_precioventa(self, valor):
        valor = float(valor)
        if valor < 0: raise ValueError("El precio de venta no puede ser negativo.")
        self.__precioventa = valor

    def get_stockactual(self): return self.__stockactual
    def set_stockactual(self, valor):
        valor = int(valor)
        if valor < 0: raise ValueError("El stock no puede ser negativo.")
        self.__stockactual = valor

    def get_stockminimo(self): return self.__stockminimo
    def set_stockminimo(self, valor):
        valor = int(valor)
        if valor < 0: raise ValueError("El stock mínimo no puede ser negativo.")
        self.__stockminimo = valor

    def to_dict(self):
        return {
            "idproducto": self.get_idproducto(),
            "codigobarras": self.get_codigobarras(),
            "nombre": self.get_nombre(),
            "idproveedor": self.get_idproveedor(),
            "preciocompra": self.get_preciocompra(),
            "precioventa": self.get_precioventa(),
            "stockactual": self.get_stockactual(),
            "stockminimo": self.get_stockminimo()
        }


# CLASE 4: VistaBase. Clase abstracta que define la estructura común de las ventanas.
class VistaBase(ctk.CTkFrame, ABC):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=COLOR_BG_PANEL)
        self.controller = controller
        self.db = DatabaseHelper()
        self.sesion = SesionUsuario()
        self.construir_interfaz()

    @abstractmethod
    def construir_interfaz(self): pass
    
    @abstractmethod
    def actualizar_datos(self): pass

    def refrescar_vistas_relacionadas(self):
        dashboard = getattr(self.controller, "dashboard_view", None)
        if dashboard is not None:
            dashboard.actualizar_catalogos()
        else:
            self.actualizar_datos()


# VISTA 1: LoginView. Presenta el formulario para iniciar sesión.
class LoginView(VistaBase):
    def construir_interfaz(self):
        if not self.db.inicializar_catalogos():
            messagebox.showerror("Error crítico", "No se pudo conectar a MySQL. Asegúrate de encender XAMPP y crear la base de datos 'abarrotes'.")

        center_frame = ctk.CTkFrame(self, fg_color="transparent")
        center_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        logo_box = ctk.CTkFrame(center_frame, fg_color="#e2e8f0", width=55, height=55, corner_radius=12)
        logo_box.pack(pady=(0, 15))
        logo_box.pack_propagate(False)
        ctk.CTkLabel(logo_box, text="A", font=("Helvetica", 24, "bold"), text_color=COLOR_PRIMARY).pack(expand=True)
        
        ctk.CTkLabel(center_frame, text="Sistema de gestión de inventario", font=("Helvetica", 18, "bold"), text_color=COLOR_PRIMARY).pack(pady=(0, 20))
        
        card = ctk.CTkFrame(center_frame, fg_color=COLOR_CARD, corner_radius=16, width=380, height=380, border_width=1, border_color=COLOR_BORDER)
        card.pack()
        card.pack_propagate(False)
        
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=35, pady=30)
        
        ctk.CTkLabel(inner, text="Iniciar sesión", font=("Helvetica", 16, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0, 5))
        ctk.CTkLabel(inner, text="Ingresa tus credenciales para acceder.", font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED).pack(anchor="w", pady=(0, 20))
        
        ctk.CTkLabel(inner, text="Correo o Usuario", font=("Helvetica", 11, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0, 2))
        self.user = ctk.CTkEntry(inner, placeholder_text="ej. Juan", height=38, fg_color="#f8fafc", border_color=COLOR_BORDER)
        self.user.pack(fill="x", pady=(0, 12))
        
        ctk.CTkLabel(inner, text="Contraseña", font=("Helvetica", 11, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0, 2))
        self.pwd = ctk.CTkEntry(inner, placeholder_text="********", show="*", height=38, fg_color="#f8fafc", border_color=COLOR_BORDER)
        self.pwd.pack(fill="x", pady=(0, 20))
        
        ctk.CTkButton(inner, text="Ingresar al sistema", fg_color=COLOR_PRIMARY, hover_color="#1e293b", height=40, font=("Helvetica", 12, "bold"), command=self.autenticar).pack(fill="x")

    def autenticar(self):
        correo_usuario = self.user.get()
        password = self.pwd.get()
        
        # Consulta actualizada a la tabla usuario (valida por correo o nombre y contraseña)
        query = "SELECT idusuario, nombre, rol FROM usuario WHERE (correo = %s OR nombre = %s) AND passwordhash = %s AND activo = 1"
        res = self.db.ejecutar_consulta(query, (correo_usuario, correo_usuario, password), fetch=True)
        
        if res:
            self.sesion.iniciar_sesion(res[0]['idusuario'], res[0]['nombre'], res[0]['rol'])
            self.user.delete(0, 'end')
            self.pwd.delete(0, 'end')
            self.controller.iniciar_dashboard()
        else:
            messagebox.showerror("Error de acceso", "Usuario o contraseña incorrectos, o cuenta inactiva.")
            
    def actualizar_datos(self): pass


# VISTA 2: PuntoDeVentaView. Permite seleccionar productos y registrar ventas.
class PuntoDeVentaView(VistaBase):
    def construir_interfaz(self):
        self.carrito = {} 
        self.total_venta = 0.0

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)
        
        left_pane = ctk.CTkFrame(self, fg_color="transparent")
        left_pane.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
        
        header = ctk.CTkFrame(left_pane, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))
        encabezado_textos = ctk.CTkFrame(header, fg_color="transparent")
        encabezado_textos.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(encabezado_textos, text="Punto de Venta", font=("Helvetica", 24, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(encabezado_textos, text="Haz clic en un producto para agregarlo al ticket.", font=("Helvetica", 13), text_color=COLOR_TEXT_MUTED).pack(anchor="w")
        
        ctk.CTkButton(header, text="↻ Actualizar pantalla", width=145, height=32,
                      fg_color=COLOR_PRIMARY, command=self.refrescar_vistas_relacionadas).pack(side="right", padx=(8, 0))

        self.products_grid = ctk.CTkScrollableFrame(left_pane, fg_color="transparent")
        self.products_grid.pack(fill="both", expand=True)

        right_pane = ctk.CTkFrame(self, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=0)
        right_pane.grid(row=0, column=1, sticky="nsew")
        
        ctk.CTkLabel(right_pane, text="Ticket de Venta", font=("Helvetica", 16, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", padx=20, pady=(30, 10))
        
        self.cart_frame = ctk.CTkScrollableFrame(right_pane, fg_color="transparent")
        self.cart_frame.pack(fill="both", expand=True, padx=10)
        
        bottom_box = ctk.CTkFrame(right_pane, fg_color="transparent")
        bottom_box.pack(side="bottom", fill="x", padx=20, pady=20)
        
        ctk.CTkFrame(bottom_box, fg_color=COLOR_BORDER, height=2).pack(fill="x", pady=(0,15))
        
        total_frame = ctk.CTkFrame(bottom_box, fg_color="transparent")
        total_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(total_frame, text="Total a Pagar:", font=("Helvetica", 14, "bold"), text_color=COLOR_PRIMARY).pack(side="left")
        self.lbl_total = ctk.CTkLabel(total_frame, text="$0.00", font=("Helvetica", 22, "bold"), text_color="#065f46")
        self.lbl_total.pack(side="right")
        
        ctk.CTkLabel(bottom_box, text="Método de pago", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0,5))
        self.combo_metodo = ctk.CTkComboBox(bottom_box, values=["Efectivo", "Tarjeta"], fg_color="#f8fafc", border_color=COLOR_BORDER, height=35)
        self.combo_metodo.pack(fill="x", pady=(0, 15))
        
        ctk.CTkButton(bottom_box, text="Procesar Venta", fg_color=COLOR_PRIMARY, text_color="white", height=45, font=("Helvetica", 14, "bold"), corner_radius=8, command=self.procesar_pago).pack(fill="x")

    def actualizar_datos(self):
        productos = self.db.ejecutar_consulta(
            "SELECT idproducto, nombre, codigobarras, precioventa, stockactual FROM producto ORDER BY nombre",
            fetch=True
        )
        if productos is None:
            messagebox.showerror("Error", "No fue posible actualizar el catálogo de productos.")
            return

        for w in self.products_grid.winfo_children(): w.destroy()

        productos_por_id = {p["idproducto"]: p for p in productos}
        for id_p in list(self.carrito.keys()):
            if id_p not in productos_por_id:
                del self.carrito[id_p]
                continue
            actual = productos_por_id[id_p]
            self.carrito[id_p]["nombre"] = actual["nombre"]
            self.carrito[id_p]["precio"] = float(actual["precioventa"])
            self.carrito[id_p]["stock"] = actual["stockactual"]
            self.carrito[id_p]["obj"] = actual
            if int(actual["stockactual"]) <= 0:
                del self.carrito[id_p]
            elif self.carrito[id_p]["cantidad"] > int(actual["stockactual"]):
                self.carrito[id_p]["cantidad"] = int(actual["stockactual"])

        if hasattr(self, "lbl_total"):
            self.dibujar_carrito()

        if not productos:
            ctk.CTkLabel(self.products_grid, text="No hay productos registrados.", text_color=COLOR_TEXT_MUTED).pack(pady=20)
            return

        row, col = 0, 0
        for p in productos:
            card = ctk.CTkFrame(self.products_grid, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=8, width=160, height=110, cursor="hand2")
            card.grid(row=row, column=col, padx=8, pady=8)
            card.grid_propagate(False)
            
            card.bind("<Button-1>", lambda e, prod=p: self.agregar_al_carrito(prod))
            
            lbl_nom = ctk.CTkLabel(card, text=p['nombre'][:15], font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY)
            lbl_nom.pack(anchor="w", padx=12, pady=(12, 0))
            lbl_nom.bind("<Button-1>", lambda e, prod=p: self.agregar_al_carrito(prod))
            
            ctk.CTkLabel(card, text=str(p['codigobarras'] or ''), font=("Helvetica", 10), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=12)
            
            bottom = ctk.CTkFrame(card, fg_color="transparent")
            bottom.pack(fill="x", side="bottom", padx=12, pady=12)
            ctk.CTkLabel(bottom, text=f"${p['precioventa']}", font=("Helvetica", 14, "bold"), text_color=COLOR_PRIMARY).pack(side="left")
            
            stock_color = COLOR_SUCCESS_TXT if p['stockactual'] > 0 else "#991b1b"
            ctk.CTkLabel(bottom, text=f"{p['stockactual']} pz", font=("Helvetica", 11, "bold"), text_color=stock_color).pack(side="right")
            
            col += 1
            if col > 2:
                col = 0
                row += 1

    def agregar_al_carrito(self, p):
        id_p = p['idproducto']
        if p['stockactual'] <= 0:
            messagebox.showwarning("Sin stock", "Este producto está agotado.")
            return
            
        cant_actual = self.carrito[id_p]['cantidad'] if id_p in self.carrito else 0
        if cant_actual >= p['stockactual']:
            messagebox.showwarning("Límite de stock", f"Solo hay {p['stockactual']} piezas disponibles en inventario.")
            return
            
        if id_p in self.carrito:
            self.carrito[id_p]['cantidad'] += 1
        else:
            self.carrito[id_p] = {'nombre': p['nombre'], 'precio': float(p['precioventa']), 'cantidad': 1, 'stock': p['stockactual'], 'obj': p}
        
        self.dibujar_carrito()

    def restar_del_carrito(self, id_p):
        if id_p in self.carrito:
            if self.carrito[id_p]['cantidad'] > 1:
                self.carrito[id_p]['cantidad'] -= 1
            else:
                del self.carrito[id_p]
        self.dibujar_carrito()

    def eliminar_del_carrito(self, id_p):
        if id_p in self.carrito:
            del self.carrito[id_p]
        self.dibujar_carrito()

    def dibujar_carrito(self):
        for w in self.cart_frame.winfo_children(): w.destroy()
        
        self.total_venta = 0.0
        for id_p, data in self.carrito.items():
            item_frame = ctk.CTkFrame(self.cart_frame, fg_color=COLOR_BG_PANEL, border_width=1, border_color=COLOR_BORDER, corner_radius=8)
            item_frame.pack(fill="x", pady=5, padx=5)
            
            top_row = ctk.CTkFrame(item_frame, fg_color="transparent")
            top_row.pack(fill="x", padx=10, pady=(10, 5))
            ctk.CTkLabel(top_row, text=data['nombre'], font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY).pack(side="left")
            ctk.CTkButton(top_row, text="🗑️", width=25, height=25, fg_color="transparent", hover_color="#fee2e2", text_color="#ef4444", command=lambda i=id_p: self.eliminar_del_carrito(i)).pack(side="right")
            
            bot_row = ctk.CTkFrame(item_frame, fg_color="transparent")
            bot_row.pack(fill="x", padx=10, pady=(0, 10))
            
            ctrl_box = ctk.CTkFrame(bot_row, fg_color="transparent")
            ctrl_box.pack(side="left")
            
            ctk.CTkButton(ctrl_box, text="-", width=28, height=28, fg_color="#e2e8f0", text_color=COLOR_PRIMARY, font=("Helvetica", 14, "bold"), command=lambda i=id_p: self.restar_del_carrito(i)).pack(side="left", padx=2)
            ctk.CTkLabel(ctrl_box, text=str(data['cantidad']), font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY, width=25).pack(side="left", padx=5)
            ctk.CTkButton(ctrl_box, text="+", width=28, height=28, fg_color="#e2e8f0", text_color=COLOR_PRIMARY, font=("Helvetica", 14, "bold"), command=lambda p=data['obj']: self.agregar_al_carrito(p)).pack(side="left", padx=2)
            
            subtotal = data['cantidad'] * data['precio']
            self.total_venta += subtotal
            
            detalle_texto = f"(${data['precio']} c/u) = ${subtotal:.2f}"
            ctk.CTkLabel(bot_row, text=detalle_texto, font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(side="right")
            
        self.lbl_total.configure(text=f"${self.total_venta:.2f}")

    def procesar_pago(self):
        if not self.carrito:
            messagebox.showwarning("Ticket vacío", "Agrega productos al ticket antes de cobrar.")
            return
            
        for id_p, item in self.carrito.items():
            consulta_stock = self.db.ejecutar_consulta(
                "SELECT stockactual FROM producto WHERE idproducto = %s", (id_p,), fetch=True
            )
            if not consulta_stock:
                messagebox.showerror("Producto no disponible", f"El producto {item['nombre']} ya no existe en el inventario.")
                self.actualizar_datos()
                return
            stock_bd = consulta_stock[0]["stockactual"]
            if stock_bd < item['cantidad']:
                messagebox.showerror("Stock insuficiente", f"No hay suficientes piezas de {item['nombre']} en inventario.")
                return

        id_usuario = self.sesion.get_usuario_actual()['id']
        metodo = self.combo_metodo.get() # 'Efectivo' o 'Tarjeta'
        
        # Inserta la venta utilizando el ENUM 'metodopago' directo en la tabla venta
        id_venta = self.db.ejecutar_consulta(
            "INSERT INTO venta (fecha, idusuario, metodopago, total) VALUES (NOW(), %s, %s, %s)", 
            (id_usuario, metodo, self.total_venta)
        )
        
        if id_venta:
            for id_p, data in self.carrito.items():
                subtotal = data['cantidad'] * data['precio']
                self.db.ejecutar_consulta(
                    "INSERT INTO detalle_venta (idventa, idproducto, cantidadvendida, preciounitario, subtotal) VALUES (%s, %s, %s, %s, %s)", 
                    (id_venta, id_p, data['cantidad'], data['precio'], subtotal)
                )
                self.db.ejecutar_consulta(
                    "UPDATE producto SET stockactual = stockactual - %s WHERE idproducto = %s", 
                    (data['cantidad'], id_p)
                )
                # Registrar movimiento de inventario (SALIDA por venta)
                self.db.ejecutar_consulta(
                    "INSERT INTO movimiento_inventario (idproducto, tipo, cantidad, fecha, idusuario, referencia) VALUES (%s, 'SALIDA', %s, NOW(), %s, %s)",
                    (id_p, data['cantidad'], id_usuario, f"venta #{id_venta}")
                )
                
            messagebox.showinfo("Venta Exitosa", f"El ticket #{id_venta} ha sido cobrado correctamente.")
            self.carrito.clear()
            self.dibujar_carrito()
            self.actualizar_datos()


# VISTA 3: ProductosView. Administra altas, consultas, cambios y bajas de productos.
class ProductosView(VistaBase):
    def construir_interfaz(self):
        main_box = ctk.CTkFrame(self, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=40, pady=30)

        header_frame = ctk.CTkFrame(main_box, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(header_frame, text="Productos", font=("Helvetica", 24, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(header_frame, text="Gestiona el inventario, revisa disponibilidad y edita los productos.", font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")

        action_bar = ctk.CTkFrame(main_box, fg_color="transparent")
        action_bar.pack(fill="x", pady=(0, 20))
        ctk.CTkButton(action_bar, text="Agregar producto +", fg_color=COLOR_PRIMARY, text_color="white",
                      corner_radius=6, height=38, font=("Helvetica", 12),
                      command=self.modal_agregar_producto).pack(side="right")
        ctk.CTkButton(action_bar, text="↻ Actualizar pantalla", fg_color=COLOR_PRIMARY, text_color="white",
                      corner_radius=6, height=38, font=("Helvetica", 12),
                      command=self.refrescar_vistas_relacionadas).pack(side="right", padx=8)

        self.metrics_frame = ctk.CTkFrame(main_box, fg_color="transparent")
        self.metrics_frame.pack(fill="x", pady=(0, 20))
        table_container = ctk.CTkFrame(main_box, fg_color=COLOR_CARD, border_width=1,
                                       border_color=COLOR_BORDER, corner_radius=10)
        table_container.pack(fill="both", expand=True)
        self.table_frame = ctk.CTkScrollableFrame(table_container, fg_color="transparent")
        self.table_frame.pack(fill="both", expand=True, padx=5, pady=5)

    def actualizar_datos(self):
        for widget in self.metrics_frame.winfo_children():
            widget.destroy()

        stats = self.db.ejecutar_consulta(
            "SELECT COUNT(*) AS t, SUM(CASE WHEN stockactual > 0 THEN 1 ELSE 0 END) AS s FROM producto",
            fetch=True
        )
        if stats and stats[0]["t"] is not None:
            datos_metricas = [
                ("Total de productos", str(stats[0]["t"])),
                ("En stock", str(stats[0]["s"] or 0)),
                ("Última actualización", "Hoy")
            ]
            for label, valor in datos_metricas:
                card = ctk.CTkFrame(self.metrics_frame, fg_color=COLOR_CARD, border_width=1,
                                    border_color=COLOR_BORDER, corner_radius=8, height=75)
                card.pack(side="left", padx=(0, 10), expand=True, fill="both")
                card.pack_propagate(False)
                ctk.CTkLabel(card, text=label, font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=15, pady=(10, 0))
                ctk.CTkLabel(card, text=valor, font=("Helvetica", 18, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", padx=15)

        for widget in self.table_frame.winfo_children():
            widget.destroy()

        headers = ["Producto", "Código", "Precio", "Inventario", "Estado", "Acciones"]
        for idx, titulo in enumerate(headers):
            ctk.CTkLabel(self.table_frame, text=titulo, font=("Helvetica", 12, "bold"),
                         text_color=COLOR_PRIMARY).grid(row=0, column=idx, padx=15, pady=15, sticky="w")

        productos = self.db.ejecutar_consulta("SELECT * FROM producto ORDER BY nombre", fetch=True)
        if productos is None:
            ctk.CTkLabel(self.table_frame, text="No fue posible consultar los productos.",
                         text_color="#991b1b").grid(row=1, column=0, columnspan=6, pady=20)
            return
        if not productos:
            ctk.CTkLabel(self.table_frame, text="No hay productos registrados.",
                         text_color=COLOR_TEXT_MUTED).grid(row=1, column=0, columnspan=6, pady=20)
            return

        for i, producto in enumerate(productos, start=1):
            nombre_frame = ctk.CTkFrame(self.table_frame, fg_color="transparent")
            nombre_frame.grid(row=i, column=0, padx=15, pady=10, sticky="w")
            ctk.CTkLabel(nombre_frame, text=producto["nombre"], font=("Helvetica", 13, "bold"),
                         text_color=COLOR_PRIMARY).pack(anchor="w")
            ctk.CTkLabel(self.table_frame, text=str(producto["codigobarras"] or ''), font=("Helvetica", 12),
                         text_color=COLOR_TEXT_MUTED).grid(row=i, column=1, padx=15, sticky="w")
            ctk.CTkLabel(self.table_frame, text=f"${float(producto['precioventa']):.2f}",
                         font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY).grid(row=i, column=2, padx=15, sticky="w")
            ctk.CTkLabel(self.table_frame, text=f"{producto['stockactual']} pz",
                         font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY).grid(row=i, column=3, padx=15, sticky="w")

            hay_stock = int(producto["stockactual"]) > 0
            estado_frame = ctk.CTkFrame(self.table_frame,
                                        fg_color=COLOR_SUCCESS_BG if hay_stock else "#fee2e2",
                                        corner_radius=12)
            estado_frame.grid(row=i, column=4, padx=15, sticky="w")
            ctk.CTkLabel(estado_frame, text="En stock" if hay_stock else "Agotado",
                         font=("Helvetica", 11, "bold"),
                         text_color=COLOR_SUCCESS_TXT if hay_stock else "#991b1b").pack(padx=10, pady=2)

            acciones = ctk.CTkFrame(self.table_frame, fg_color="transparent")
            acciones.grid(row=i, column=5, padx=10, sticky="w")
            ctk.CTkButton(acciones, text="Editar", width=65, height=28,
                          fg_color="transparent", border_width=1, border_color=COLOR_BORDER,
                          text_color=COLOR_PRIMARY,
                          command=lambda p=producto: self.modal_editar_producto(p)).pack(side="left", padx=3)
            ctk.CTkButton(acciones, text="Eliminar", width=70, height=28,
                          fg_color="#fee2e2", hover_color="#fecaca", text_color="#991b1b",
                          command=lambda p=producto: self.eliminar_producto(p)).pack(side="left", padx=3)

    def modal_agregar_producto(self):
        self._abrir_formulario_producto()

    def modal_editar_producto(self, producto):
        self._abrir_formulario_producto(producto)

    def _abrir_formulario_producto(self, producto=None):
        es_edicion = producto is not None
        proveedores = self.db.ejecutar_consulta("SELECT idproveedor, nombreempresa FROM proveedor ORDER BY nombreempresa", fetch=True) or []

        if not proveedores:
            messagebox.showerror("Falta un proveedor", "Registra al menos un proveedor antes de agregar productos.")
            return

        modal = ctk.CTkToplevel(self)
        modal.title("Editar producto" if es_edicion else "Nuevo producto")
        modal.geometry("470x650")
        modal.minsize(430, 550)
        modal.grab_set()

        inner = ctk.CTkScrollableFrame(modal, fg_color="transparent")
        inner.pack(padx=25, pady=20, fill="both", expand=True)
        entradas = {}

        valores_iniciales = {
            "codigobarras": producto["codigobarras"] if es_edicion else "",
            "nombre": producto["nombre"] if es_edicion else "",
            "preciocompra": str(producto["preciocompra"]) if es_edicion and producto["preciocompra"] is not None else "",
            "precioventa": str(producto["precioventa"]) if es_edicion else "",
            "stockactual": str(producto["stockactual"]) if es_edicion else "0",
            "stockminimo": str(producto.get("stockminimo", 0)) if es_edicion else "0"
        }

        for key, titulo in [
            ("codigobarras", "Código de barras"),
            ("nombre", "Nombre del producto"),
            ("preciocompra", "Costo de compra $"),
            ("precioventa", "Precio de venta $"),
            ("stockactual", "Existencias actuales"),
            ("stockminimo", "Stock mínimo")
        ]:
            ctk.CTkLabel(inner, text=titulo, font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(9, 2))
            entrada = ctk.CTkEntry(inner, height=35)
            entrada.pack(fill="x", pady=(0, 4))
            entrada.insert(0, str(valores_iniciales[key]))
            entradas[key] = entrada

        mapa_proveedores = {f"{p['idproveedor']} | {p['nombreempresa']}": p["idproveedor"] for p in proveedores}

        ctk.CTkLabel(inner, text="Proveedor", font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(9, 2))
        combo_proveedor = ctk.CTkComboBox(inner, values=list(mapa_proveedores.keys()), height=35)
        combo_proveedor.pack(fill="x", pady=(0, 4))

        if es_edicion:
            for etiqueta, identificador in mapa_proveedores.items():
                if identificador == producto["idproveedor"]:
                    combo_proveedor.set(etiqueta)
                    break
        else:
            combo_proveedor.set(next(iter(mapa_proveedores)))

        def guardar():
            try:
                proveedor_id = mapa_proveedores.get(combo_proveedor.get())
                nuevo_producto = Producto(
                    producto["idproducto"] if es_edicion else None,
                    entradas["codigobarras"].get(),
                    entradas["nombre"].get(),
                    proveedor_id,
                    entradas["preciocompra"].get(),
                    entradas["precioventa"].get(),
                    entradas["stockactual"].get(),
                    entradas["stockminimo"].get()
                )
                datos = nuevo_producto.to_dict()

                if es_edicion:
                    resultado = self.db.ejecutar_consulta(
                        "UPDATE producto SET codigobarras=%s, nombre=%s, idproveedor=%s, "
                        "preciocompra=%s, precioventa=%s, stockactual=%s, stockminimo=%s WHERE idproducto=%s",
                        (datos["codigobarras"], datos["nombre"], datos["idproveedor"],
                         datos["preciocompra"] if datos["preciocompra"] > 0 else None, 
                         datos["precioventa"], datos["stockactual"],
                         datos["stockminimo"], datos["idproducto"])
                    )
                else:
                    resultado = self.db.ejecutar_consulta(
                        "INSERT INTO producto (codigobarras, nombre, idproveedor, preciocompra, precioventa, stockactual, stockminimo) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (datos["codigobarras"], datos["nombre"], datos["idproveedor"], 
                         datos["preciocompra"] if datos["preciocompra"] > 0 else None, 
                         datos["precioventa"], datos["stockactual"], datos["stockminimo"])
                    )

                if resultado is None:
                    messagebox.showerror("Error", "No se pudo guardar el producto. Verifica que el código no esté repetido.")
                    return

                modal.destroy()
                self.refrescar_vistas_relacionadas()
                messagebox.showinfo("Producto guardado", "Los datos del producto se guardaron correctamente.")
            except (ValueError, TypeError) as error:
                messagebox.showerror("Datos inválidos", str(error))
            except Exception as error:
                messagebox.showerror("Error", f"No se pudo guardar el producto: {error}")

        ctk.CTkButton(inner, text="Guardar cambios" if es_edicion else "Guardar producto",
                      fg_color=COLOR_PRIMARY, height=42, command=guardar).pack(pady=20, fill="x")

    def eliminar_producto(self, producto):
        confirmar = messagebox.askyesno(
            "Eliminar producto",
            f"¿Seguro que deseas eliminar '{producto['nombre']}'? Esta acción no se puede deshacer."
        )
        if not confirmar:
            return

        resultado = self.db.ejecutar_consulta(
            "DELETE FROM producto WHERE idproducto = %s", (producto["idproducto"],)
        )
        if resultado is None:
            messagebox.showerror(
                "No se pudo eliminar",
                "El producto tiene registros de ventas o compras relacionadas. "
                "La base de datos impide borrarlo para conservar el historial."
            )
        elif resultado == 0:
            messagebox.showwarning("Sin cambios", "El producto ya no existe o no se encontró.")
        else:
            self.refrescar_vistas_relacionadas()
            messagebox.showinfo("Producto eliminado", "El producto se eliminó correctamente.")


# VISTA 4: ProveedoresView. Administra altas, consultas, cambios y bajas de proveedores.
class ProveedoresView(VistaBase):
    def construir_interfaz(self):
        main_box = ctk.CTkFrame(self, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=40, pady=30)

        header_frame = ctk.CTkFrame(main_box, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))
        titles = ctk.CTkFrame(header_frame, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(titles, text="Proveedores", font=("Helvetica", 24, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(titles, text="Gestiona empresas y teléfonos de proveedores.", font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")

        actions = ctk.CTkFrame(header_frame, fg_color="transparent")
        actions.pack(side="right", fill="y")
        ctk.CTkButton(actions, text="Agregar proveedor +", fg_color=COLOR_PRIMARY,
                      corner_radius=6, height=35, command=self.modal_agregar).pack(side="left", padx=(8, 0))
        ctk.CTkButton(actions, text="↻ Actualizar pantalla", fg_color=COLOR_PRIMARY,
                      corner_radius=6, height=35, command=self.refrescar_vistas_relacionadas).pack(side="left", padx=8)

        table_container = ctk.CTkFrame(main_box, fg_color=COLOR_CARD, border_width=1,
                                       border_color=COLOR_BORDER, corner_radius=10)
        table_container.pack(fill="both", expand=True, pady=(20, 0))
        self.table_frame = ctk.CTkScrollableFrame(table_container, fg_color="transparent")
        self.table_frame.pack(fill="both", expand=True, padx=5, pady=5)

    def actualizar_datos(self):
        proveedores = self.db.ejecutar_consulta(
            "SELECT * FROM proveedor ORDER BY nombreempresa", fetch=True
        )
        for widget in self.table_frame.winfo_children():
            widget.destroy()

        headers = ["Empresa", "Teléfono", "Acciones"]
        for idx, titulo in enumerate(headers):
            ctk.CTkLabel(self.table_frame, text=titulo, font=("Helvetica", 12, "bold"),
                         text_color=COLOR_PRIMARY).grid(row=0, column=idx, padx=20, pady=15, sticky="w")

        if proveedores is None:
            ctk.CTkLabel(self.table_frame, text="No fue posible consultar los proveedores.",
                         text_color="#991b1b").grid(row=1, column=0, columnspan=3, pady=20)
            return
        if not proveedores:
            ctk.CTkLabel(self.table_frame, text="No hay proveedores registrados.",
                         text_color=COLOR_TEXT_MUTED).grid(row=1, column=0, columnspan=3, pady=20)
            return

        for i, proveedor in enumerate(proveedores, start=1):
            nombre_frame = ctk.CTkFrame(self.table_frame, fg_color="transparent")
            nombre_frame.grid(row=i, column=0, padx=20, pady=10, sticky="w")
            ctk.CTkLabel(nombre_frame, text=proveedor["nombreempresa"],
                         font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
            ctk.CTkLabel(self.table_frame, text=proveedor.get("telefono") or "—",
                         font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(row=i, column=1, padx=20, sticky="w")

            acciones = ctk.CTkFrame(self.table_frame, fg_color="transparent")
            acciones.grid(row=i, column=2, padx=15, sticky="w")
            ctk.CTkButton(acciones, text="Editar", width=65, height=30,
                          fg_color="transparent", border_width=1, border_color=COLOR_BORDER,
                          text_color=COLOR_PRIMARY,
                          command=lambda p=proveedor: self.modal_editar(p)).pack(side="left", padx=3)
            ctk.CTkButton(acciones, text="Eliminar", width=70, height=30,
                          fg_color="#fee2e2", hover_color="#fecaca", text_color="#991b1b",
                          command=lambda p=proveedor: self.eliminar_proveedor(p)).pack(side="left", padx=3)

    def modal_agregar(self):
        self._abrir_formulario_proveedor()

    def modal_editar(self, proveedor):
        self._abrir_formulario_proveedor(proveedor)

    def _abrir_formulario_proveedor(self, proveedor=None):
        es_edicion = proveedor is not None
        modal = ctk.CTkToplevel(self)
        modal.title("Editar proveedor" if es_edicion else "Nuevo proveedor")
        modal.geometry("390x320")
        modal.grab_set()

        inner = ctk.CTkFrame(modal, fg_color="transparent")
        inner.pack(padx=30, pady=20, fill="both", expand=True)
        entradas = {}
        campos = [
            ("empresa", "Nombre de la Empresa", proveedor.get("nombreempresa", "") if es_edicion else ""),
            ("telefono", "Teléfono", proveedor.get("telefono", "") if es_edicion else "")
        ]
        for clave, titulo, valor in campos:
            ctk.CTkLabel(inner, text=titulo, font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(10, 2))
            entrada = ctk.CTkEntry(inner, height=35)
            entrada.pack(fill="x", pady=(0, 5))
            entrada.insert(0, str(valor or ""))
            entradas[clave] = entrada

        def guardar():
            empresa = entradas["empresa"].get().strip()
            telefono = entradas["telefono"].get().strip()
            if not empresa:
                messagebox.showwarning("Dato obligatorio", "El nombre de la empresa es obligatorio.")
                return

            if es_edicion:
                resultado = self.db.ejecutar_consulta(
                    "UPDATE proveedor SET nombreempresa=%s, telefono=%s WHERE idproveedor=%s",
                    (empresa, telefono, proveedor["idproveedor"])
                )
            else:
                resultado = self.db.ejecutar_consulta(
                    "INSERT INTO proveedor (nombreempresa, telefono) VALUES (%s, %s)",
                    (empresa, telefono)
                )

            if resultado is None:
                messagebox.showerror("Error", "No se pudieron guardar los datos del proveedor.")
                return
            modal.destroy()
            self.refrescar_vistas_relacionadas()
            messagebox.showinfo("Proveedor guardado", "Los datos del proveedor se guardaron correctamente.")

        ctk.CTkButton(inner, text="Guardar cambios" if es_edicion else "Guardar proveedor",
                      fg_color=COLOR_PRIMARY, height=40, command=guardar).pack(pady=25, fill="x")

    def eliminar_proveedor(self, proveedor):
        confirmar = messagebox.askyesno(
            "Eliminar proveedor",
            f"¿Seguro que deseas eliminar a '{proveedor['nombreempresa']}'?"
        )
        if not confirmar:
            return

        resultado = self.db.ejecutar_consulta(
            "DELETE FROM proveedor WHERE idproveedor=%s", (proveedor["idproveedor"],)
        )
        if resultado is None:
            messagebox.showerror(
                "No se pudo eliminar",
                "Este proveedor está asociado a productos existentes."
            )
        elif resultado == 0:
            messagebox.showwarning("Sin cambios", "El proveedor ya no existe o no se encontró.")
        else:
            self.refrescar_vistas_relacionadas()
            messagebox.showinfo("Proveedor eliminado", "El proveedor se eliminó correctamente.")


# CLASE 5: MainDashboardView. Organiza la navegación entre los módulos del sistema.
class MainDashboardView(VistaBase):
    def construir_interfaz(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.sidebar = ctk.CTkFrame(self, fg_color=COLOR_SIDEBAR, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        
        self.content_area = ctk.CTkFrame(self, fg_color=COLOR_BG_PANEL, corner_radius=0)
        self.content_area.grid(row=0, column=1, sticky="nsew")
        self.content_area.grid_rowconfigure(0, weight=1)
        self.content_area.grid_columnconfigure(0, weight=1)
        
        self.vistas = {
            "Punto de venta": PuntoDeVentaView(self.content_area, self.controller),
            "Productos": ProductosView(self.content_area, self.controller),
            "Proveedores": ProveedoresView(self.content_area, self.controller)
        }
        for view in self.vistas.values(): 
            view.grid(row=0, column=0, sticky="nsew")
            
        self.setup_sidebar()

    def setup_sidebar(self):
        title_box = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        title_box.pack(fill="x", pady=(30, 20), padx=20)
        ctk.CTkLabel(title_box, text="Abarrotes Lupita", font=("Helvetica", 18, "bold"), text_color=COLOR_PRIMARY).pack(side="left")
        ctk.CTkFrame(self.sidebar, fg_color="#475569", height=2).pack(fill="x", pady=(0, 20))
        
        self.nav_buttons = {}
        for titulo in ["Punto de venta", "Productos", "Proveedores"]:
            btn = ctk.CTkButton(self.sidebar, text=f"  {titulo}", fg_color="transparent", text_color=COLOR_PRIMARY,
                                hover_color=COLOR_SIDEBAR_ACTIVE, anchor="w", height=50, font=("Helvetica", 15, "bold"), corner_radius=0)
            if titulo in self.vistas:
                btn.configure(command=lambda t=titulo: self.cambiar_vista(t))
            btn.pack(fill="x", pady=2)
            self.nav_buttons[titulo] = btn

        ctk.CTkButton(
            self.sidebar, text="↻ Actualizar todo", fg_color=COLOR_PRIMARY,
            text_color="white", hover_color="#1e293b", height=38,
            command=self.actualizar_catalogos
        ).pack(fill="x", padx=15, pady=(12, 0))

        self.footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.footer.pack(side="bottom", fill="x", padx=20, pady=30)
        ctk.CTkLabel(self.footer, text="Sesión activa", font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")
        
        self.lbl_usuario = ctk.CTkLabel(self.footer, text="", font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY)
        self.lbl_usuario.pack(anchor="w")
        
        ctk.CTkButton(self.footer, text="Cerrar sesión", fg_color="transparent", text_color="#ef4444", hover_color="#cbd5e1", anchor="w", command=self.cerrar_sesion).pack(fill="x", pady=(10,0))

    def actualizar_datos(self):
        user = self.sesion.get_usuario_actual()
        if user:
            self.lbl_usuario.configure(text=user['nombre'])
        self.cambiar_vista("Punto de venta")

    def actualizar_catalogos(self):
        errores = []
        for nombre in ("Productos", "Proveedores", "Punto de venta"):
            vista = self.vistas.get(nombre)
            if vista is None:
                continue
            try:
                vista.actualizar_datos()
            except Exception as error:
                errores.append(f"{nombre}: {error}")
                print(f"Error al actualizar la vista '{nombre}': {error}")
        if errores:
            messagebox.showwarning(
                "Actualización parcial",
                "No se pudieron actualizar todas las pantallas. Revisa la conexión a MySQL.\n\n"
                + "\n".join(errores)
            )

    def cambiar_vista(self, nombre_vista):
        for k, btn in self.nav_buttons.items():
            btn.configure(fg_color=COLOR_SIDEBAR_ACTIVE if k == nombre_vista else "transparent")
        vista = self.vistas[nombre_vista]
        vista.actualizar_datos()
        vista.tkraise()
        
    def cerrar_sesion(self):
        self.sesion.cerrar_sesion()
        self.controller.mostrar_login()

# CLASE 6: SistemaAbarrotesApp. Ventana raíz y controlador general de la aplicación.
class SistemaAbarrotesApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Sistema de Punto de Venta - Abarrotes")
        self.geometry("1200x750")
        self.configure(fg_color=COLOR_BG_PANEL)
        
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        
        self.login_view = LoginView(self.container, self)
        self.dashboard_view = MainDashboardView(self.container, self)
        
        self.login_view.grid(row=0, column=0, sticky="nsew")
        self.dashboard_view.grid(row=0, column=0, sticky="nsew")
        
        self.mostrar_login()

    def iniciar_dashboard(self):
        self.dashboard_view.actualizar_datos()
        self.dashboard_view.tkraise()
        
    def mostrar_login(self):
        self.login_view.tkraise()

if __name__ == "__main__":
    app = SistemaAbarrotesApp()
    app.mainloop()
