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
                filas = cursor.fetchall()
                # Cada vista mantiene su propia conexión MySQL. Confirmar también
                # las lecturas cierra la transacción de solo lectura y evita que
                # MySQL conserve una instantánea antigua (REPEATABLE READ).
                # Sin esto, otra vista podía seguir mostrando datos viejos hasta
                # cerrar y volver a abrir el programa.
                self.__connection.commit()
                return filas
            # Confirma los cambios realizados en la base de datos.
            self.__connection.commit()
            # INSERT necesita devolver el ID generado; UPDATE/DELETE devuelven filas afectadas.
            if query.strip().upper().startswith("INSERT"):
                return cursor.lastrowid
            return cursor.rowcount
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
    # Setter: modifica el usuario actual sin acceder directamente al atributo privado.
    def set_usuario_actual(self, usuario):
        self.__usuario_actual = usuario

    # Registra los datos del usuario autenticado en la sesión compartida.
    def iniciar_sesion(self, id_usuario, nombre, rol):
        if id_usuario is None:
            self.set_usuario_actual(None)
        else:
            self.set_usuario_actual({"id": id_usuario, "nombre": nombre, "rol": rol})

    # Getter: permite consultar el usuario actual sin acceder al atributo privado.
    def get_usuario_actual(self):
        return self.__usuario_actual

    # Elimina la información del usuario que inició sesión.
    def cerrar_sesion(self):
        self.set_usuario_actual(None)


# CLASE 3: Producto. Representa un producto y protege sus atributos mediante encapsulación.
class Producto:
    def __init__(self, idproducto, codigobarras, nombre, idcategoria, idproveedor,
                 preciocompra, precioventa, stockactual, stockminimo=0):
        self.set_idproducto(idproducto)
        self.set_codigobarras(codigobarras)
        self.set_nombre(nombre)
        self.set_idcategoria(idcategoria)
        self.set_idproveedor(idproveedor)
        self.set_preciocompra(preciocompra)
        self.set_precioventa(precioventa)
        self.set_stockactual(stockactual)
        self.set_stockminimo(stockminimo)

    # Getters y setters: exponen los datos de forma controlada.
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

    def get_idcategoria(self): return self.__idcategoria
    def set_idcategoria(self, valor):
        if valor in (None, ""): raise ValueError("Selecciona una categoría.")
        self.__idcategoria = int(valor)

    def get_idproveedor(self): return self.__idproveedor
    def set_idproveedor(self, valor):
        if valor in (None, ""): raise ValueError("Selecciona un proveedor.")
        self.__idproveedor = int(valor)

    def get_preciocompra(self): return self.__preciocompra
    def set_preciocompra(self, valor):
        valor = float(valor)
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

    # Métodos de negocio para consultar y modificar existencias.
    def tiene_stock(self, cantidad=1):
        return self.__stockactual >= int(cantidad)

    def descontar_stock(self, cantidad=1):
        cantidad = int(cantidad)
        if cantidad <= 0 or not self.tiene_stock(cantidad):
            return False
        self.__stockactual -= cantidad
        return True

    def reponer_stock(self, cantidad=1):
        cantidad = int(cantidad)
        if cantidad <= 0:
            return False
        self.__stockactual += cantidad
        return True

    # Devuelve los atributos en un diccionario para facilitar su uso con formularios y SQL.
    def to_dict(self):
        # Utiliza los getters para consultar los atributos encapsulados.
        return {
            "idproducto": self.get_idproducto(),
            "codigobarras": self.get_codigobarras(),
            "nombre": self.get_nombre(),
            "idcategoria": self.get_idcategoria(),
            "idproveedor": self.get_idproveedor(),
            "preciocompra": self.get_preciocompra(),
            "precioventa": self.get_precioventa(),
            "stockactual": self.get_stockactual(),
            "stockminimo": self.get_stockminimo()
        }


# CLASE 4: VistaBase. Clase abstracta que define la estructura común de las ventanas.
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

    # Actualiza inmediatamente las pantallas relacionadas después de un cambio.
    def refrescar_vistas_relacionadas(self):
        dashboard = getattr(self.controller, "dashboard_view", None)
        if dashboard is not None:
            # La actualización es directa: el formulario ya se cerró y MySQL
            # confirmó el INSERT/UPDATE/DELETE antes de llegar a este método.
            dashboard.actualizar_catalogos()
        else:
            self.actualizar_datos()

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
            messagebox.showerror("Error crítico", "No se pudo conectar a MySQL. Asegúrate de encender XAMPP y crear la base de datos 'abarrotes'.")

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
        encabezado_textos = ctk.CTkFrame(header, fg_color="transparent")
        encabezado_textos.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(encabezado_textos, text="Punto de Venta", font=("Helvetica", 24, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(encabezado_textos, text="Haz clic en un producto para agregarlo al ticket.", font=("Helvetica", 13), text_color=COLOR_TEXT_MUTED).pack(anchor="w")
        # Botón de respaldo para volver a consultar MySQL manualmente.
        ctk.CTkButton(header, text="↻ Actualizar pantalla", width=145, height=32,
                      fg_color=COLOR_PRIMARY, command=self.refrescar_vistas_relacionadas).pack(side="right", padx=(8, 0))

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
        # Consulta primero; si falla la conexión, conserva lo que ya se muestra.
        productos = self.db.ejecutar_consulta(
            "SELECT idproducto, nombre, codigobarras, precioventa, stockactual FROM producto ORDER BY nombre",
            fetch=True
        )
        if productos is None:
            messagebox.showerror("Error", "No fue posible actualizar el catálogo de productos.")
            return

        # Elimina tarjetas anteriores para reconstruir el catálogo actualizado.
        for w in self.products_grid.winfo_children(): w.destroy()

        # Sincroniza el carrito: retira productos eliminados y actualiza nombre, precio y existencias.
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


# VISTA 3: ProductosView. Administra altas, consultas, cambios y bajas de productos.
# ==========================================
# 3. PRODUCTOS
# ==========================================
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
            ctk.CTkLabel(self.table_frame, text=str(producto["codigobarras"]), font=("Helvetica", 12),
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
        categorias = self.db.ejecutar_consulta("SELECT idcategoria, nombre FROM categoria ORDER BY nombre", fetch=True) or []
        proveedores = self.db.ejecutar_consulta("SELECT idproveedor, nombreempresa FROM proveedor ORDER BY nombreempresa", fetch=True) or []

        if not categorias:
            messagebox.showerror("Falta una categoría", "Registra al menos una categoría antes de agregar productos.")
            return
        if not proveedores:
            messagebox.showerror("Falta un proveedor", "Registra al menos un proveedor antes de agregar productos.")
            return

        modal = ctk.CTkToplevel(self)
        modal.title("Editar producto" if es_edicion else "Nuevo producto")
        modal.geometry("470x720")
        modal.minsize(430, 620)
        modal.grab_set()

        inner = ctk.CTkScrollableFrame(modal, fg_color="transparent")
        inner.pack(padx=25, pady=20, fill="both", expand=True)
        entradas = {}

        valores_iniciales = {
            "codigobarras": producto["codigobarras"] if es_edicion else "",
            "nombre": producto["nombre"] if es_edicion else "",
            "preciocompra": str(producto["preciocompra"]) if es_edicion else "",
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

        mapa_categorias = {f"{c['idcategoria']} | {c['nombre']}": c["idcategoria"] for c in categorias}
        mapa_proveedores = {f"{p['idproveedor']} | {p['nombreempresa']}": p["idproveedor"] for p in proveedores}

        ctk.CTkLabel(inner, text="Categoría", font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(9, 2))
        combo_categoria = ctk.CTkComboBox(inner, values=list(mapa_categorias.keys()), height=35)
        combo_categoria.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(inner, text="Proveedor", font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(9, 2))
        combo_proveedor = ctk.CTkComboBox(inner, values=list(mapa_proveedores.keys()), height=35)
        combo_proveedor.pack(fill="x", pady=(0, 4))

        if es_edicion:
            for etiqueta, identificador in mapa_categorias.items():
                if identificador == producto["idcategoria"]:
                    combo_categoria.set(etiqueta)
                    break
            for etiqueta, identificador in mapa_proveedores.items():
                if identificador == producto["idproveedor"]:
                    combo_proveedor.set(etiqueta)
                    break
        else:
            combo_categoria.set(next(iter(mapa_categorias)))
            combo_proveedor.set(next(iter(mapa_proveedores)))

        def guardar():
            try:
                categoria_id = mapa_categorias.get(combo_categoria.get())
                proveedor_id = mapa_proveedores.get(combo_proveedor.get())
                nuevo_producto = Producto(
                    producto["idproducto"] if es_edicion else None,
                    entradas["codigobarras"].get(),
                    entradas["nombre"].get(),
                    categoria_id,
                    proveedor_id,
                    entradas["preciocompra"].get(),
                    entradas["precioventa"].get(),
                    entradas["stockactual"].get(),
                    entradas["stockminimo"].get()
                )
                datos = nuevo_producto.to_dict()

                if es_edicion:
                    resultado = self.db.ejecutar_consulta(
                        "UPDATE producto SET codigobarras=%s, nombre=%s, idcategoria=%s, idproveedor=%s, "
                        "preciocompra=%s, precioventa=%s, stockactual=%s, stockminimo=%s WHERE idproducto=%s",
                        (datos["codigobarras"], datos["nombre"], datos["idcategoria"], datos["idproveedor"],
                         datos["preciocompra"], datos["precioventa"], datos["stockactual"],
                         datos["stockminimo"], datos["idproducto"])
                    )
                else:
                    resultado = self.db.ejecutar_consulta(
                        "INSERT INTO producto (codigobarras, nombre, idcategoria, idproveedor, preciocompra, precioventa, stockactual, stockminimo) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (datos["codigobarras"], datos["nombre"], datos["idcategoria"], datos["idproveedor"],
                         datos["preciocompra"], datos["precioventa"], datos["stockactual"], datos["stockminimo"])
                    )

                if resultado is None:
                    messagebox.showerror("Error", "No se pudo guardar el producto. Verifica que el código no esté repetido y que los datos sean correctos.")
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
                "El producto puede tener registros relacionados con ventas, compras o movimientos de inventario. "
                "La base de datos impide borrarlo para conservar el historial. Puedes editarlo y dejar su stock en 0."
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
        ctk.CTkLabel(titles, text="Gestiona empresas, contactos y teléfonos.", font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")

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

        headers = ["Proveedor", "Contacto", "Teléfono", "Acciones"]
        for idx, titulo in enumerate(headers):
            ctk.CTkLabel(self.table_frame, text=titulo, font=("Helvetica", 12, "bold"),
                         text_color=COLOR_PRIMARY).grid(row=0, column=idx, padx=20, pady=15, sticky="w")

        if proveedores is None:
            ctk.CTkLabel(self.table_frame, text="No fue posible consultar los proveedores.",
                         text_color="#991b1b").grid(row=1, column=0, columnspan=4, pady=20)
            return
        if not proveedores:
            ctk.CTkLabel(self.table_frame, text="No hay proveedores registrados.",
                         text_color=COLOR_TEXT_MUTED).grid(row=1, column=0, columnspan=4, pady=20)
            return

        for i, proveedor in enumerate(proveedores, start=1):
            nombre_frame = ctk.CTkFrame(self.table_frame, fg_color="transparent")
            nombre_frame.grid(row=i, column=0, padx=20, pady=10, sticky="w")
            ctk.CTkLabel(nombre_frame, text=proveedor["nombreempresa"],
                         font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
            ctk.CTkLabel(self.table_frame, text=proveedor.get("contacto") or "—",
                         font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(row=i, column=1, padx=20, sticky="w")
            ctk.CTkLabel(self.table_frame, text=proveedor.get("telefono") or "—",
                         font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(row=i, column=2, padx=20, sticky="w")

            acciones = ctk.CTkFrame(self.table_frame, fg_color="transparent")
            acciones.grid(row=i, column=3, padx=15, sticky="w")
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
        modal.geometry("390x420")
        modal.grab_set()

        inner = ctk.CTkFrame(modal, fg_color="transparent")
        inner.pack(padx=30, pady=20, fill="both", expand=True)
        entradas = {}
        campos = [
            ("empresa", "Empresa", proveedor.get("nombreempresa", "") if es_edicion else ""),
            ("contacto", "Contacto", proveedor.get("contacto", "") if es_edicion else ""),
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
            contacto = entradas["contacto"].get().strip()
            telefono = entradas["telefono"].get().strip()
            if not empresa:
                messagebox.showwarning("Dato obligatorio", "El nombre de la empresa es obligatorio.")
                return

            if es_edicion:
                resultado = self.db.ejecutar_consulta(
                    "UPDATE proveedor SET nombreempresa=%s, contacto=%s, telefono=%s WHERE idproveedor=%s",
                    (empresa, contacto, telefono, proveedor["idproveedor"])
                )
            else:
                resultado = self.db.ejecutar_consulta(
                    "INSERT INTO proveedor (nombreempresa, contacto, telefono) VALUES (%s, %s, %s)",
                    (empresa, contacto, telefono)
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
                "Este proveedor puede estar asociado a productos o compras existentes. "
                "Primero cambia esas relaciones y después vuelve a intentar eliminarlo."
            )
        elif resultado == 0:
            messagebox.showwarning("Sin cambios", "El proveedor ya no existe o no se encontró.")
        else:
            self.refrescar_vistas_relacionadas()
            messagebox.showinfo("Proveedor eliminado", "El proveedor se eliminó correctamente.")


# CLASE 9: MainDashboardView. Organiza la navegación entre los módulos del sistema.
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

        # Botón global para volver a consultar MySQL desde cualquier módulo.
        ctk.CTkButton(
            self.sidebar, text="↻ Actualizar todo", fg_color=COLOR_PRIMARY,
            text_color="white", hover_color="#1e293b", height=38,
            command=self.actualizar_catalogos
        ).pack(fill="x", padx=15, pady=(12, 0))

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

    # Actualiza las tablas de administración y vuelve a consultar el catálogo del punto de venta.
    def actualizar_catalogos(self):
        # Vuelve a consultar las tres secciones usando sus propias conexiones.
        # Los cambios ya están confirmados en MySQL antes de invocar esta función.
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

    # Fuerza una lectura nueva del catálogo del punto de venta, sin usar datos guardados en memoria.
    def actualizar_catalogo_punto_venta(self):
        vista_pos = self.vistas.get("Punto de venta")
        if vista_pos is not None:
            vista_pos.actualizar_datos()

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
        self.sesion.cerrar_sesion()
        # Solicita al controlador regresar al login.
        self.controller.mostrar_login()

# CLASE 10: SistemaAbarrotesApp. Ventana raíz y controlador general de la aplicación.
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
