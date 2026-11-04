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
        self.__user = "root"
        self.__password = ""
        self.__database = "abarrotes"
        self.__connection = None

    # Abre la conexión con MySQL. Devuelve True si funciona y False si ocurre un error.
    def conectar(self):
        # try/except permite controlar errores de conexión sin cerrar inesperadamente el programa.
        try:
            self.__connection = mysql.connector.connect(
                host=self.__host, 
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
        # Si no existe una conexión activa, intenta conectarse antes de ejecutar la consulta.
        if not self.__connection or not self.__connection.is_connected():
            if not self.conectar():
                return None
        
        # dictionary=True permite acceder a los campos por nombre, por ejemplo fila['nombre'].
        cursor = self.__connection.cursor(dictionary=True)
        try:
            # Ejecuta la consulta usando parámetros para separar los datos del texto SQL.
            cursor.execute(query, parametros or ())
            # Las consultas de lectura devuelven todas las filas encontradas.
            if fetch: 
                return cursor.fetchall()
            # Las consultas INSERT/UPDATE/DELETE se confirman en la base de datos.
            self.__connection.commit()
            return cursor.lastrowid
        except Error as e:
            print(f"Error en SQL: {e}")
            return None
            # finally garantiza que el cursor se cierre incluso si ocurre un error.
        finally:
            cursor.close()

    # Crea registros básicos para que el sistema tenga categoría, proveedor, pagos, rol y usuario inicial.
    def inicializar_catalogos(self):
        # Si no se puede conectar, detiene la inicialización y comunica el fallo.
        if not self.conectar(): return False
        # Comprueba si ya existe al menos un registro en cada catálogo para evitar duplicados.
        if not self.ejecutar_consulta("SELECT * FROM categoria LIMIT 1", fetch=True):
            self.ejecutar_consulta("INSERT INTO categoria (nombre) VALUES ('General')")
        if not self.ejecutar_consulta("SELECT * FROM proveedor LIMIT 1", fetch=True):
            self.ejecutar_consulta("INSERT INTO proveedor (nombreempresa, contacto, telefono) VALUES ('Proveedor Default', 'N/A', '0000')")
        if not self.ejecutar_consulta("SELECT * FROM metodo_pago LIMIT 1", fetch=True):
            self.ejecutar_consulta("INSERT INTO metodo_pago (nombre) VALUES ('Efectivo'), ('Tarjeta')")
        if not self.ejecutar_consulta("SELECT * FROM rol LIMIT 1", fetch=True):
            self.ejecutar_consulta("INSERT INTO rol (nombre) VALUES ('Administrador')")
        if not self.ejecutar_consulta("SELECT * FROM usuario LIMIT 1", fetch=True):
            self.ejecutar_consulta("INSERT INTO usuario (nombre, correo, passwordhash, idrol) VALUES ('Administrador', 'admin', '123', 1)")
        return True

# CLASE 2: SesionUsuario. Conserva los datos del usuario que inició sesión.
class SesionUsuario:
    # Variable de clase compartida por todas las instancias: se usa para implementar Singleton.
    _instancia = None
    # __new__ controla la creación del objeto antes de ejecutar el constructor tradicional.
    def __new__(cls):
        # Solo crea una instancia la primera vez que se solicita la clase.
        if cls._instancia is None:
            cls._instancia = super(SesionUsuario, cls).__new__(cls)
            # Guarda el usuario actual como atributo privado de la instancia.
            cls._instancia.__usuario_actual = None
        return cls._instancia
    # Registra los datos del usuario autenticado en la sesión compartida.
    def iniciar_sesion(self, id_usuario, nombre, rol): self.__usuario_actual = {"id": id_usuario, "nombre": nombre, "rol": rol}
    # Getter: permite consultar el usuario actual sin acceder directamente al atributo privado.
    def get_usuario_actual(self): return self.__usuario_actual

# CLASE 3: VistaBase. Clase abstracta que define la estructura común de las ventanas.
class VistaBase(ctk.CTkFrame, ABC):
    # Recibe el contenedor y el controlador principal de la aplicación.
    def __init__(self, parent, controller):
        # Inicializa la parte visual heredada de CTkFrame con el color de fondo.
        super().__init__(parent, fg_color=COLOR_BG_PANEL)
        # Referencia al controlador para poder cambiar entre ventanas.
        self.controller = controller
        # Cada vista dispone de un auxiliar para consultar la base de datos.
        self.db = DatabaseHelper()
        # Todas las vistas comparten la misma sesión Singleton.
        self.sesion = SesionUsuario()
        # Llama al método que cada subclase debe implementar para construir su interfaz.
        self.construir_interfaz()
    # Método abstracto: obliga a las vistas hijas a definir cómo construir su interfaz.
    @abstractmethod
    def construir_interfaz(self): pass
    # Método abstracto: obliga a las vistas hijas a definir cómo actualizar sus datos.
    @abstractmethod
    def actualizar_datos(self): pass


# Las siguientes clases heredan de VistaBase y personalizan su interfaz y comportamiento.
# ==========================================
# VISTA 1: LoginView. Presenta el formulario para iniciar sesión.
# 1. VISTA LOGIN
# ==========================================
# Herencia: LoginView recibe los atributos y métodos comunes definidos en VistaBase.
class LoginView(VistaBase):
    # Construye los elementos visuales del formulario de acceso.
    def construir_interfaz(self):
        # Prepara los catálogos iniciales y verifica la conexión a MySQL.
        # Validar conexión y catálogos al iniciar la vista
        if not self.db.inicializar_catalogos():
            messagebox.showerror("Error crítico", "No se pudo conectar a MySQL. Asegúrate de encender XAMPP y crear la base de datos 'abarrotes_db'.")

        # Contenedor centrado que agrupa los elementos del formulario.
        center_frame = ctk.CTkFrame(self, fg_color="transparent")
        center_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        logo_box = ctk.CTkFrame(center_frame, fg_color="#e2e8f0", width=55, height=55, corner_radius=12)
        logo_box.pack(pady=(0, 15))
        logo_box.pack_propagate(False)
        ctk.CTkLabel(logo_box, text="A", font=("Helvetica", 24, "bold"), text_color=COLOR_PRIMARY).pack(expand=True)
        
        ctk.CTkLabel(center_frame, text="Sistema de gestión de inventario", font=("Helvetica", 18, "bold"), text_color=COLOR_PRIMARY).pack(pady=(0, 20))
        
        # Tarjeta visual que contiene los campos y el botón de acceso.
        card = ctk.CTkFrame(center_frame, fg_color=COLOR_CARD, corner_radius=16, width=380, height=380, border_width=1, border_color=COLOR_BORDER)
        card.pack()
        card.pack_propagate(False)
        
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=35, pady=30)
        
        ctk.CTkLabel(inner, text="Iniciar sesión", font=("Helvetica", 16, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0, 5))
        ctk.CTkLabel(inner, text="Ingresa tus credenciales para acceder.", font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED).pack(anchor="w", pady=(0, 20))
        
        # Campo donde se captura el correo o nombre de usuario.
        ctk.CTkLabel(inner, text="Correo o Usuario", font=("Helvetica", 11, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0, 2))
        self.user = ctk.CTkEntry(inner, placeholder_text="ej. admin", height=38, fg_color="#f8fafc", border_color=COLOR_BORDER)
        self.user.pack(fill="x", pady=(0, 12))
        
        # Campo de contraseña: show='*' oculta los caracteres escritos.
        ctk.CTkLabel(inner, text="Contraseña", font=("Helvetica", 11, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0, 2))
        self.pwd = ctk.CTkEntry(inner, placeholder_text="********", show="*", height=38, fg_color="#f8fafc", border_color=COLOR_BORDER)
        self.pwd.pack(fill="x", pady=(0, 20))
        
        # El botón ejecuta autenticar cuando el usuario hace clic.
        ctk.CTkButton(inner, text="Ingresar al sistema", fg_color=COLOR_PRIMARY, hover_color="#1e293b", height=40, font=("Helvetica", 12, "bold"), command=self.autenticar).pack(fill="x")

    # Comprueba las credenciales ingresadas contra la tabla usuario.
    def autenticar(self):
        # Obtiene el texto escrito en el campo de usuario.
        correo_usuario = self.user.get()
        # Obtiene la contraseña escrita.
        password = self.pwd.get()
        
        # Consulta parametrizada: busca coincidencia de usuario/correo y contraseña.
        query = "SELECT idusuario, nombre, idrol FROM usuario WHERE (correo = %s OR nombre = %s) AND passwordhash = %s"
        res = self.db.ejecutar_consulta(query, (correo_usuario, correo_usuario, password), fetch=True)
        
        # Si la consulta devuelve un registro, las credenciales fueron aceptadas.
        if res:
            # Guarda los datos del usuario en la sesión compartida.
            self.sesion.iniciar_sesion(res[0]['idusuario'], res[0]['nombre'], res[0]['idrol'])
            self.user.delete(0, 'end')
            self.pwd.delete(0, 'end')
            # Pide al controlador mostrar el panel principal.
            self.controller.iniciar_dashboard()
        else:
            # Informa cuando no se encontró una combinación válida de credenciales.
            messagebox.showerror("Error de acceso", "Usuario o contraseña incorrectos, o base de datos desconectada.")
            
    # Implementación vacía del método abstracto; el login no necesita recargar datos.
    def actualizar_datos(self): pass


# VISTA 2: PuntoDeVentaView. Permite seleccionar productos y registrar ventas.
# ==========================================
# 2. PUNTO DE VENTA
# ==========================================
# Hereda la estructura general de VistaBase y define el punto de venta.
class PuntoDeVentaView(VistaBase):
    # Construye la pantalla y prepara las estructuras del carrito.
    def construir_interfaz(self):
        # Diccionario que almacena los productos agregados al ticket, usando su ID como clave.
        self.carrito = {} 
        # Acumulador del importe total de la venta.
        self.total_venta = 0.0

        # Configura la distribución de columnas y filas de la pantalla.
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)
        
        # Panel izquierdo: catálogo de productos disponibles.
        left_pane = ctk.CTkFrame(self, fg_color="transparent")
        left_pane.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
        
        header = ctk.CTkFrame(left_pane, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(header, text="Punto de Venta", font=("Helvetica", 24, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(header, text="Haz clic en un producto para agregarlo al ticket.", font=("Helvetica", 13), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        self.products_grid = ctk.CTkScrollableFrame(left_pane, fg_color="transparent")
        self.products_grid.pack(fill="both", expand=True)

        # Panel derecho: ticket, total y controles de cobro.
        right_pane = ctk.CTkFrame(self, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=0)
        right_pane.grid(row=0, column=1, sticky="nsew")
        
        ctk.CTkLabel(right_pane, text="Ticket de Venta", font=("Helvetica", 16, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", padx=20, pady=(30, 10))
        
        # Área desplazable donde se muestran los productos del carrito.
        self.cart_frame = ctk.CTkScrollableFrame(right_pane, fg_color="transparent")
        self.cart_frame.pack(fill="both", expand=True, padx=10)
        
        bottom_box = ctk.CTkFrame(right_pane, fg_color="transparent")
        bottom_box.pack(side="bottom", fill="x", padx=20, pady=20)
        
        ctk.CTkFrame(bottom_box, fg_color=COLOR_BORDER, height=2).pack(fill="x", pady=(0,15))
        
        # Zona inferior del ticket con total y método de pago.
        total_frame = ctk.CTkFrame(bottom_box, fg_color="transparent")
        total_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(total_frame, text="Total a Pagar:", font=("Helvetica", 14, "bold"), text_color=COLOR_PRIMARY).pack(side="left")
        self.lbl_total = ctk.CTkLabel(total_frame, text="$0.00", font=("Helvetica", 22, "bold"), text_color="#065f46")
        self.lbl_total.pack(side="right")
        
        # Selector del método de pago.
        ctk.CTkLabel(bottom_box, text="Método de pago", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0,5))
        self.combo_metodo = ctk.CTkComboBox(bottom_box, values=["Efectivo", "Tarjeta"], fg_color="#f8fafc", border_color=COLOR_BORDER, height=35)
        self.combo_metodo.pack(fill="x", pady=(0, 15))
        
        # Al pulsar el botón se ejecuta el método procesar_pago.
        ctk.CTkButton(bottom_box, text="Procesar Venta", fg_color=COLOR_PRIMARY, text_color="white", height=45, font=("Helvetica", 14, "bold"), corner_radius=8, command=self.procesar_pago).pack(fill="x")

    # Polimorfismo: implementa la actualización específica de los productos del punto de venta.
    def actualizar_datos(self):
        # Elimina tarjetas anteriores para reconstruir el catálogo actualizado.
        for w in self.products_grid.winfo_children(): w.destroy()
        # Consulta los productos y sus datos necesarios para vender.
        productos = self.db.ejecutar_consulta("SELECT idproducto, nombre, codigobarras, precioventa, stockactual FROM producto", fetch=True)
        
        # Si no hay registros, muestra un mensaje y termina el método.
        if not productos:
            ctk.CTkLabel(self.products_grid, text="No hay productos registrados.", text_color=COLOR_TEXT_MUTED).pack(pady=20)
            return

        # row y col controlan la posición de cada tarjeta en la cuadrícula.
        row, col = 0, 0
        # Recorre cada producto recuperado de MySQL.
        for p in productos:
            card = ctk.CTkFrame(self.products_grid, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=8, width=160, height=110, cursor="hand2")
            card.grid(row=row, column=col, padx=8, pady=8)
            card.grid_propagate(False)
            
            # Vincula el clic de la tarjeta con agregar_al_carrito; prod=p conserva el producto correcto.
            card.bind("<Button-1>", lambda e, prod=p: self.agregar_al_carrito(prod))
            
            # Muestra el nombre del producto en la tarjeta.
            lbl_nom = ctk.CTkLabel(card, text=p['nombre'][:15], font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY)
            lbl_nom.pack(anchor="w", padx=12, pady=(12, 0))
            lbl_nom.bind("<Button-1>", lambda e, prod=p: self.agregar_al_carrito(prod))
            
            ctk.CTkLabel(card, text=p['codigobarras'], font=("Helvetica", 10), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=12)
            
            bottom = ctk.CTkFrame(card, fg_color="transparent")
            bottom.pack(fill="x", side="bottom", padx=12, pady=12)
            ctk.CTkLabel(bottom, text=f"${p['precioventa']}", font=("Helvetica", 14, "bold"), text_color=COLOR_PRIMARY).pack(side="left")
            
            # Cambia el color del indicador según exista o no inventario.
            stock_color = COLOR_SUCCESS_TXT if p['stockactual'] > 0 else "#991b1b"
            ctk.CTkLabel(bottom, text=f"{p['stockactual']} pz", font=("Helvetica", 11, "bold"), text_color=stock_color).pack(side="right")
            
            col += 1
            if col > 2:
                col = 0
                row += 1

    # Agrega una unidad al carrito, validando que exista stock suficiente.
    def agregar_al_carrito(self, p):
        # Recupera el identificador del producto para usarlo como clave del carrito.
        id_p = p['idproducto']
        
        # No permite vender productos agotados.
        if p['stockactual'] <= 0:
            messagebox.showwarning("Sin stock", "Este producto está agotado.")
            return
            
        # Consulta cuántas unidades de ese producto ya están en el carrito.
        cant_actual = self.carrito[id_p]['cantidad'] if id_p in self.carrito else 0
        # Evita que la cantidad solicitada supere las existencias.
        if cant_actual >= p['stockactual']:
            messagebox.showwarning("Límite de stock", f"Solo hay {p['stockactual']} piezas disponibles en inventario.")
            return
            
        # Si el producto ya está agregado, aumenta su cantidad.
        if id_p in self.carrito:
            self.carrito[id_p]['cantidad'] += 1
            # Si es la primera unidad, crea su registro dentro del diccionario del carrito.
        else:
            self.carrito[id_p] = {'nombre': p['nombre'], 'precio': float(p['precioventa']), 'cantidad': 1, 'stock': p['stockactual'], 'obj': p}
        
        # Redibuja el ticket para reflejar cantidades y total actualizados.
        self.dibujar_carrito()

    # Resta una unidad del producto; si llega a cero, lo elimina del carrito.
    def restar_del_carrito(self, id_p):
        if id_p in self.carrito:
            if self.carrito[id_p]['cantidad'] > 1:
                self.carrito[id_p]['cantidad'] -= 1
            else:
                del self.carrito[id_p]
        self.dibujar_carrito()

    # Elimina completamente un producto del carrito.
    def eliminar_del_carrito(self, id_p):
        if id_p in self.carrito:
            del self.carrito[id_p]
        self.dibujar_carrito()

    # Reconstruye visualmente el ticket y calcula nuevamente el importe total.
    def dibujar_carrito(self):
        for w in self.cart_frame.winfo_children(): w.destroy()
        
        # Reinicia el total antes de sumar los subtotales actuales.
        self.total_venta = 0.0
        # Recorre cada producto y sus datos almacenados en el carrito.
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
            
            # Calcula el subtotal multiplicando cantidad por precio unitario.
            subtotal = data['cantidad'] * data['precio']
            # Acumula el subtotal para obtener el total de la venta.
            self.total_venta += subtotal
            
            detalle_texto = f"(${data['precio']} c/u) = ${subtotal:.2f}"
            ctk.CTkLabel(bot_row, text=detalle_texto, font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(side="right")
            
        # Actualiza la etiqueta del total que ve el usuario.
        self.lbl_total.configure(text=f"${self.total_venta:.2f}")

    # Valida el carrito, registra la venta, guarda sus detalles y descuenta existencias.
    def procesar_pago(self):
        # Impide procesar un ticket vacío.
        if not self.carrito:
            messagebox.showwarning("Ticket vacío", "Agrega productos al ticket antes de cobrar.")
            return
            
        # Verifica nuevamente el stock directamente en la base de datos antes de cobrar.
        for id_p, item in self.carrito.items():
            stock_bd = self.db.ejecutar_consulta("SELECT stockactual FROM producto WHERE idproducto = %s", (id_p,), fetch=True)[0]['stockactual']
            if stock_bd < item['cantidad']:
                messagebox.showerror("Stock insuficiente", f"No hay suficientes piezas de {item['nombre']} en inventario.")
                return

        # Obtiene el ID del usuario autenticado desde la sesión.
        id_usuario = self.sesion.get_usuario_actual()['id']
        # Lee el método de pago seleccionado en la interfaz.
        metodo = self.combo_metodo.get()
        # Traduce el método seleccionado al ID correspondiente del catálogo.
        id_metodo = 1 if metodo == "Efectivo" else 2
        
        # Inserta la venta principal y obtiene su identificador generado por MySQL.
        id_venta = self.db.ejecutar_consulta("INSERT INTO venta (fecha, idusuario, idmetodopago, total) VALUES (NOW(), %s, %s, %s)", (id_usuario, id_metodo, self.total_venta))
        
        # Solo registra los detalles si se obtuvo un ID de venta válido.
        if id_venta:
            # Recorre los productos incluidos en el ticket.
            for id_p, data in self.carrito.items():
                # Calcula el subtotal de cada producto vendido.
                subtotal = data['cantidad'] * data['precio']
                # Guarda la cantidad y el precio de cada producto en detalle_venta.
                self.db.ejecutar_consulta("INSERT INTO detalle_venta (idventa, idproducto, cantidadvendida, preciounitario, subtotal) VALUES (%s, %s, %s, %s, %s)", (id_venta, id_p, data['cantidad'], data['precio'], subtotal))
                # Descuenta del inventario las unidades que se acaban de vender.
                self.db.ejecutar_consulta("UPDATE producto SET stockactual = stockactual - %s WHERE idproducto = %s", (data['cantidad'], id_p))
                
            # Confirma visualmente que la operación terminó correctamente.
            messagebox.showinfo("Venta Exitosa", f"El ticket #{id_venta} ha sido cobrado correctamente.")
            # Vacía el carrito después de completar la venta.
            self.carrito.clear()
            self.dibujar_carrito()
            # Actualiza el catálogo para mostrar las existencias nuevas.
            self.actualizar_datos()


# VISTA 3: ProductosView. Muestra el inventario y permite registrar productos.
# ==========================================
# 3. PRODUCTOS Y PROVEEDORES
# ==========================================
# Hereda los elementos comunes de VistaBase.
class ProductosView(VistaBase):
    # Construye la pantalla de administración de productos.
    def construir_interfaz(self):
        main_box = ctk.CTkFrame(self, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=40, pady=30)
        header_frame = ctk.CTkFrame(main_box, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(header_frame, text="Productos", font=("Helvetica", 24, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(header_frame, text="Gestiona el inventario, revisa disponibilidad y accede a acciones rápidas.", font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
        action_bar = ctk.CTkFrame(main_box, fg_color="transparent")
        action_bar.pack(fill="x", pady=(0, 20))
        # Botón que abre el formulario para registrar un producto.
        ctk.CTkButton(action_bar, text="Agregar producto +", fg_color=COLOR_PRIMARY, text_color="white", corner_radius=6, height=38, font=("Helvetica", 12), command=self.modal_agregar_producto).pack(side="right")
        self.metrics_frame = ctk.CTkFrame(main_box, fg_color="transparent")
        self.metrics_frame.pack(fill="x", pady=(0, 20))
        table_container = ctk.CTkFrame(main_box, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=10)
        table_container.pack(fill="both", expand=True)
        self.table_frame = ctk.CTkScrollableFrame(table_container, fg_color="transparent")
        self.table_frame.pack(fill="both", expand=True, padx=5, pady=5)

    # Implementación propia de actualizar_datos: consulta y muestra el inventario.
    def actualizar_datos(self):
        for w in self.metrics_frame.winfo_children(): w.destroy()
        # Obtiene el número total de productos y cuántos tienen stock disponible.
        stats = self.db.ejecutar_consulta("SELECT COUNT(*) as t, SUM(CASE WHEN stockactual > 0 THEN 1 ELSE 0 END) as s FROM producto", fetch=True)
        if stats and stats[0]['t'] is not None:
            # Prepara los valores que se mostrarán en las tarjetas de resumen.
            datos_metricas = [("Total de productos", str(stats[0]['t'])), ("En stock", str(stats[0]['s'] or 0)), ("Última actualización", "Hoy")]
            for label, val in datos_metricas:
                card = ctk.CTkFrame(self.metrics_frame, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=8, height=75)
                card.pack(side="left", padx=(0, 10), expand=True, fill="both")
                card.pack_propagate(False)
                ctk.CTkLabel(card, text=label, font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=15, pady=(10, 0))
                ctk.CTkLabel(card, text=val, font=("Helvetica", 18, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", padx=15)

        # Limpia la tabla antes de volver a dibujarla.
        for w in self.table_frame.winfo_children(): w.destroy()
        # Define los encabezados de las columnas de la tabla.
        headers = ["Producto", "Código", "Precio", "Inventario", "Estado", "Acciones"]
        for idx, h in enumerate(headers):
            ctk.CTkLabel(self.table_frame, text=h, font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).grid(row=0, column=idx, padx=20, pady=15, sticky="w")
        # Recupera los productos registrados en la base de datos.
        productos = self.db.ejecutar_consulta("SELECT * FROM producto", fetch=True)
        if productos:
            # Recorre los productos y coloca sus datos en una fila.
            for i, p in enumerate(productos, start=1):
                col1 = ctk.CTkFrame(self.table_frame, fg_color="transparent")
                col1.grid(row=i, column=0, padx=20, pady=10, sticky="w")
                ctk.CTkLabel(col1, text=p['nombre'], font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
                ctk.CTkLabel(self.table_frame, text=p['codigobarras'], font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(row=i, column=1, padx=20, sticky="w")
                ctk.CTkLabel(self.table_frame, text=f"${p['precioventa']}", font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY).grid(row=i, column=2, padx=20, sticky="w")
                ctk.CTkLabel(self.table_frame, text=f"{p['stockactual']} pz", font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY).grid(row=i, column=3, padx=20, sticky="w")
                # El estado visual depende del stock actual.
                estado_frame = ctk.CTkFrame(self.table_frame, fg_color=COLOR_SUCCESS_BG if p['stockactual'] > 0 else "#fee2e2", corner_radius=12)
                estado_frame.grid(row=i, column=4, padx=20, sticky="w")
                ctk.CTkLabel(estado_frame, text="En stock" if p['stockactual'] > 0 else "Agotado", font=("Helvetica", 11, "bold"), text_color=COLOR_SUCCESS_TXT if p['stockactual'] > 0 else "#991b1b").pack(padx=10, pady=2)
                acciones = ctk.CTkFrame(self.table_frame, fg_color="transparent")
                acciones.grid(row=i, column=5, padx=20, sticky="w")
                ctk.CTkButton(acciones, text="📝 Editar", width=60, height=28, fg_color="transparent", border_width=1, border_color=COLOR_BORDER, text_color=COLOR_PRIMARY).pack(side="left", padx=3)

    # Abre una ventana secundaria con campos para capturar un producto nuevo.
    def modal_agregar_producto(self):
        # CTkToplevel crea una ventana independiente sobre la ventana principal.
        modal = ctk.CTkToplevel(self)
        modal.title("Nuevo Producto")
        modal.geometry("400x550")
        # grab_set mantiene el foco en el formulario hasta cerrarlo.
        modal.grab_set() 
        inner = ctk.CTkFrame(modal, fg_color="transparent")
        inner.pack(padx=30, pady=20, fill="both", expand=True)
        # Diccionario para relacionar el nombre de cada campo con su entrada.
        entradas = {}
        # Define los campos que tendrá el formulario de registro.
        for key, titulo in [("codigobarras", "Código"), ("nombre", "Nombre"), ("preciocompra", "Costo $"), ("precioventa", "Precio Venta $"), ("stockactual", "Stock")]:
            ctk.CTkLabel(inner, text=titulo, font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(10,0))
            ent = ctk.CTkEntry(inner, height=35)
            ent.pack(fill="x", pady=(0, 5))
            entradas[key] = ent
        # Función interna que valida y guarda los datos capturados.
        def guardar():
            # try/except evita que datos numéricos inválidos detengan la aplicación.
            try:
                # Inserta el nuevo producto; los valores escritos se envían como parámetros.
                self.db.ejecutar_consulta("INSERT INTO producto (codigobarras, nombre, idcategoria, idproveedor, preciocompra, precioventa, stockactual, stockminimo) VALUES (%s, %s, 1, 1, %s, %s, %s, 0)", 
                    (entradas['codigobarras'].get(), entradas['nombre'].get(), float(entradas['preciocompra'].get()), float(entradas['precioventa'].get()), int(entradas['stockactual'].get())))
                # Cierra el formulario después de guardar.
                modal.destroy()
                # Actualiza la tabla para mostrar el producto recién agregado.
                self.actualizar_datos()
            except: messagebox.showerror("Error", "Datos inválidos.")
        ctk.CTkButton(inner, text="Guardar", fg_color=COLOR_PRIMARY, height=40, command=guardar).pack(pady=25, fill="x")

# VISTA 4: ProveedoresView. Administra la información de proveedores.
class ProveedoresView(VistaBase):
    # Construye la pantalla de proveedores.
    def construir_interfaz(self):
        main_box = ctk.CTkFrame(self, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=40, pady=30)
        header_frame = ctk.CTkFrame(main_box, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))
        titles = ctk.CTkFrame(header_frame, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(titles, text="Proveedores", font=("Helvetica", 24, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(titles, text="Gestiona contactos, teléfonos y acciones de cada proveedor desde un solo lugar.", font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
        actions = ctk.CTkFrame(header_frame, fg_color="transparent")
        actions.pack(side="right", fill="y")
        # Botón para abrir el formulario de alta de proveedores.
        ctk.CTkButton(actions, text="Agregar proveedor", fg_color=COLOR_PRIMARY, corner_radius=6, height=35, command=self.modal_agregar).pack(side="left")
        table_container = ctk.CTkFrame(main_box, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=10)
        table_container.pack(fill="both", expand=True, pady=(20, 0))
        self.table_frame = ctk.CTkScrollableFrame(table_container, fg_color="transparent")
        self.table_frame.pack(fill="both", expand=True, padx=5, pady=5)

    # Implementación propia de actualizar_datos para consultar y mostrar proveedores.
    def actualizar_datos(self):
        # Consulta todos los proveedores registrados.
        provs = self.db.ejecutar_consulta("SELECT * FROM proveedor", fetch=True)
        # Limpia los elementos anteriores de la tabla.
        for w in self.table_frame.winfo_children(): w.destroy()
        # Encabezados de la tabla de proveedores.
        headers = ["Proveedor", "Contacto", "Teléfono", "Acciones"]
        for idx, h in enumerate(headers):
            ctk.CTkLabel(self.table_frame, text=h, font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).grid(row=0, column=idx, padx=20, pady=15, sticky="w")
        # Si existen proveedores, recorre y presenta sus datos.
        if provs:
            for i, p in enumerate(provs, start=1):
                col1 = ctk.CTkFrame(self.table_frame, fg_color="transparent")
                col1.grid(row=i, column=0, padx=20, pady=10, sticky="w")
                ctk.CTkLabel(col1, text=p['nombreempresa'], font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
                ctk.CTkLabel(self.table_frame, text=p['contacto'], font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(row=i, column=1, padx=20, sticky="w")
                ctk.CTkLabel(self.table_frame, text=p['telefono'], font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(row=i, column=2, padx=20, sticky="w")
                acciones = ctk.CTkFrame(self.table_frame, fg_color="transparent")
                acciones.grid(row=i, column=3, padx=20, sticky="w")
                ctk.CTkButton(acciones, text="📝 Editar", width=70, height=30, fg_color="transparent", border_width=1, border_color=COLOR_BORDER, text_color=COLOR_PRIMARY).pack(side="left")

    # Abre el formulario para capturar una empresa, contacto y teléfono.
    def modal_agregar(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Nuevo Proveedor")
        modal.geometry("350x350")
        modal.grab_set()
        inner = ctk.CTkFrame(modal, fg_color="transparent")
        inner.pack(padx=30, pady=20, fill="both", expand=True)
        # Diccionario que guarda las entradas del formulario.
        entradas = {}
        # Define los campos que se solicitarán al usuario.
        for key, titulo in [("empresa", "Empresa"), ("contacto", "Contacto"), ("telefono", "Teléfono")]:
            ctk.CTkLabel(inner, text=titulo, font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(10,0))
            ent = ctk.CTkEntry(inner, height=35)
            ent.pack(fill="x", pady=(0, 5))
            entradas[key] = ent
            # Guarda los datos del formulario en la tabla proveedor.
        def guardar():
            self.db.ejecutar_consulta("INSERT INTO proveedor (nombreempresa, contacto, telefono) VALUES (%s, %s, %s)", (entradas['empresa'].get(), entradas['contacto'].get(), entradas['telefono'].get()))
            # Cierra la ventana secundaria.
            modal.destroy()
            # Actualiza la tabla para mostrar el nuevo proveedor.
            self.actualizar_datos()
        ctk.CTkButton(inner, text="Guardar", fg_color=COLOR_PRIMARY, height=40, command=guardar).pack(pady=25, fill="x")

# VISTA 5: MainDashboardView. Organiza la navegación entre los módulos del sistema.
# ==========================================
# 4. DASHBOARD PRINCIPAL Y CONTROLADOR DE VISTAS
# ==========================================
# Hereda de VistaBase y actúa como contenedor de las vistas internas.
class MainDashboardView(VistaBase):
    # Construye el menú lateral y el área donde se muestran los módulos.
    def construir_interfaz(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Barra lateral con los botones de navegación.
        self.sidebar = ctk.CTkFrame(self, fg_color=COLOR_SIDEBAR, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        
        # Panel principal donde se colocan las vistas.
        self.content_area = ctk.CTkFrame(self, fg_color=COLOR_BG_PANEL, corner_radius=0)
        self.content_area.grid(row=0, column=1, sticky="nsew")
        self.content_area.grid_rowconfigure(0, weight=1)
        self.content_area.grid_columnconfigure(0, weight=1)
        
        # Diccionario que relaciona el nombre de cada módulo con su objeto de vista.
        self.vistas = {
            # Instancia de la vista de punto de venta.
            "Punto de venta": PuntoDeVentaView(self.content_area, self.controller),
            # Instancia de la vista de productos.
            "Productos": ProductosView(self.content_area, self.controller),
            # Instancia de la vista de proveedores.
            "Proveedores": ProveedoresView(self.content_area, self.controller)
        }
        # Coloca todas las vistas en la misma posición; tkraise muestra la seleccionada.
        for view in self.vistas.values(): 
            view.grid(row=0, column=0, sticky="nsew")
            
        # Construye los botones y datos del menú lateral.
        self.setup_sidebar()

    # Crea los elementos del menú y configura las acciones de navegación.
    def setup_sidebar(self):
        title_box = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        title_box.pack(fill="x", pady=(30, 20), padx=20)
        ctk.CTkLabel(title_box, text="Abarrotes Lupita", font=("Helvetica", 18, "bold"), text_color=COLOR_PRIMARY).pack(side="left")
        ctk.CTkFrame(self.sidebar, fg_color="#475569", height=2).pack(fill="x", pady=(0, 20))
        
        # Diccionario para conservar los botones asociados a cada nombre de vista.
        self.nav_buttons = {}
        # Recorre los módulos que se mostrarán en el menú.
        for titulo in ["Punto de venta", "Productos", "Proveedores"]:
            btn = ctk.CTkButton(self.sidebar, text=f"  {titulo}", fg_color="transparent", text_color=COLOR_PRIMARY,
                                hover_color=COLOR_SIDEBAR_ACTIVE, anchor="w", height=50, font=("Helvetica", 15, "bold"), corner_radius=0)
            # Asocia cada botón con cambiar_vista y conserva el nombre correspondiente.
            if titulo in self.vistas:
                btn.configure(command=lambda t=titulo: self.cambiar_vista(t))
            btn.pack(fill="x", pady=2)
            self.nav_buttons[titulo] = btn

        # Pie del menú: usuario activo y opción para cerrar sesión.
        self.footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.footer.pack(side="bottom", fill="x", padx=20, pady=30)
        ctk.CTkLabel(self.footer, text="Sesión activa", font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")
        
        # Etiqueta donde se mostrará el nombre del usuario conectado.
        self.lbl_usuario = ctk.CTkLabel(self.footer, text="", font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY)
        self.lbl_usuario.pack(anchor="w")
        
        ctk.CTkButton(self.footer, text="Cerrar sesión", fg_color="transparent", text_color="#ef4444", hover_color="#cbd5e1", anchor="w", command=self.cerrar_sesion).pack(fill="x", pady=(10,0))

    # Actualiza el nombre de usuario y abre por defecto el punto de venta.
    def actualizar_datos(self):
        # Recupera los datos de la sesión compartida.
        user = self.sesion.get_usuario_actual()
        if user:
            self.lbl_usuario.configure(text=user['nombre'])
        self.cambiar_vista("Punto de venta")

    # Cambia el módulo visible y actualiza sus datos antes de mostrarlo.
    def cambiar_vista(self, nombre_vista):
        # Recorre los botones para marcar visualmente el módulo seleccionado.
        for k, btn in self.nav_buttons.items():
            btn.configure(fg_color=COLOR_SIDEBAR_ACTIVE if k == nombre_vista else "transparent")
        # Obtiene el objeto de vista solicitado.
        vista = self.vistas[nombre_vista]
        # Llama al mismo método en distintas clases: ejemplo de polimorfismo.
        vista.actualizar_datos()
        # Eleva la vista seleccionada al frente de las demás.
        vista.tkraise()
        
    # Cierra la sesión actual y regresa a la pantalla de inicio de sesión.
    def cerrar_sesion(self):
        # Limpia los datos del usuario guardados en la sesión.
        self.sesion.iniciar_sesion(None, None, None)
        # Solicita al controlador regresar al login.
        self.controller.mostrar_login()

# CLASE 9: SistemaAbarrotesApp. Ventana raíz y controlador general de la aplicación.
class SistemaAbarrotesApp(ctk.CTk):
    # Constructor de la aplicación: configura la ventana y crea las vistas principales.
    def __init__(self):
        super().__init__()
        # Título que aparece en la barra de la ventana.
        self.title("Sistema de Punto de Venta")
        # Tamaño inicial de la ventana principal.
        self.geometry("1200x750")
        self.configure(fg_color=COLOR_BG_PANEL)
        
        # Contenedor general donde se colocan las pantallas.
        # CONTENEDOR PRINCIPAL: Usamos exclusivamente .grid() para evitar el choque con .pack()
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        
        # Crea los objetos de LoginView y MainDashboardView.
        self.login_view = LoginView(self.container, self)
        self.dashboard_view = MainDashboardView(self.container, self)
        
        # Coloca las vistas en la misma celda para poder alternarlas.
        self.login_view.grid(row=0, column=0, sticky="nsew")
        self.dashboard_view.grid(row=0, column=0, sticky="nsew")
        
        # Al iniciar, muestra primero la pantalla de acceso.
        self.mostrar_login()

    # Se ejecuta después de autenticar correctamente al usuario.
    def iniciar_dashboard(self):
        # Actualiza el dashboard y sus módulos.
        self.dashboard_view.actualizar_datos()
        # Muestra el dashboard por encima del login.
        self.dashboard_view.tkraise()
        
    # Muestra la pantalla de inicio de sesión.
    def mostrar_login(self):
        self.login_view.tkraise()

# Punto de entrada: este bloque solo se ejecuta cuando el archivo se inicia directamente.
if __name__ == "__main__":
    # Crea una instancia de la aplicación.
    app = SistemaAbarrotesApp()
    # Inicia el ciclo de eventos de Tkinter para mantener abierta la interfaz.
    app.mainloop()
