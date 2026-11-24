# Importaciones: interfaz gráfica, conexión MySQL, seguridad, mensajes y clases abstractas.
import os
import hashlib
import hmac
import customtkinter as ctk
import mysql.connector
from mysql.connector import Error
import tkinter.messagebox as messagebox
from abc import ABC, abstractmethod

try:
    import bcrypt
    TIENE_BCRYPT = True
except ImportError:
    TIENE_BCRYPT = False

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
COLOR_WARN_BG = "#fef3c7"
COLOR_WARN_TXT = "#92400e"
COLOR_DANGER_BG = "#fee2e2"
COLOR_DANGER_TXT = "#991b1b"


# UTILIDADES DE SEGURIDAD (OWASP: Hash lento para contraseñas)
def generar_hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if TIENE_BCRYPT:
        return bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12)).decode("utf-8")
    salt = os.urandom(16).hex()
    iteraciones = 260000
    dk = hashlib.pbkdf2_hmac("sha256", password_bytes, bytes.fromhex(salt), iteraciones).hex()
    return f"pbkdf2_sha256${iteraciones}${salt}${dk}"


def verificar_password(password: str, almacenada: str) -> tuple[bool, bool]:
    """
    Retorna (es_valida, requiere_rehash).
    Soporta bcrypt ($2b$/$2a$), PBKDF2-SHA256 y texto plano heredado (migrándolo a hash).
    """
    if not almacenada:
        return False, False

    if almacenada.startswith(("$2a$", "$2b$", "$2y$")):
        if TIENE_BCRYPT:
            valida = bcrypt.checkpw(password.encode("utf-8"), almacenada.encode("utf-8"))
            return valida, False
        return False, False

    if almacenada.startswith("pbkdf2_sha256$"):
        try:
            _, iter_str, salt_hex, hash_hex = almacenada.split("$")
            dk = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                bytes.fromhex(salt_hex),
                int(iter_str)
            ).hex()
            return hmac.compare_digest(dk, hash_hex), False
        except Exception:
            return False, False

    # Compatibilidad con registros iniciales en texto plano (ej. '123' en abarrotes.sql)
    if hmac.compare_digest(password, almacenada):
        return True, True
    return False, False


# CLASE 1: DatabaseHelper. Centraliza la conexión y las operaciones con la base de datos.
class DatabaseHelper:
    def __init__(self):
        self.__host = "localhost"
        self.__ports = [3306, 3003]  # Prueba primero 3306 (estándar XAMPP) y luego 3003
        self.__user = "root"
        self.__password = ""
        self.__database = "abarrotes"
        self.__connection = None

    def conectar(self):
        for puerto in self.__ports:
            try:
                self.__connection = mysql.connector.connect(
                    host=self.__host,
                    port=puerto,
                    user=self.__user,
                    password=self.__password,
                    database=self.__database
                )
                return True
            except Error:
                self.__connection = None
        print("Error de conexión: No se pudo conectar a MySQL en los puertos 3306 ni 3003.")
        return False

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
            try:
                self.__connection.rollback()
            except Error:
                pass
            return None
        finally:
            cursor.close()

    def registrar_venta_transaccion(self, id_usuario, id_corte, metodo_pago, total, items_carrito):
        """
        Ejecuta venta, detalle_venta, descuento de stock y movimiento_inventario
        dentro de una única transacción ACID.
        """
        if not self.__connection or not self.__connection.is_connected():
            if not self.conectar():
                return None, "No hay conexión con la base de datos."

        cursor = self.__connection.cursor(dictionary=True)
        try:
            self.__connection.start_transaction()

            # 1. Bloquear y verificar existencias reales dentro de la transacción
            for id_p, item in items_carrito.items():
                cursor.execute(
                    "SELECT productoNombre, productoStockActual FROM producto WHERE productoId = %s FOR UPDATE",
                    (id_p,)
                )
                fila = cursor.fetchone()
                if not fila:
                    self.__connection.rollback()
                    return None, f"El producto '{item['nombre']}' ya no existe en el inventario."
                if int(fila["productoStockActual"]) < int(item["cantidad"]):
                    self.__connection.rollback()
                    return None, f"Stock insuficiente para '{fila['productoNombre']}' (disponible: {fila['productoStockActual']})."

            # 2. Insertar encabezado de venta
            cursor.execute(
                """
                INSERT INTO venta (ventaFecha, ventaUsuarioId, ventaCorteId, ventaMetodoPago, ventaTotal)
                VALUES (NOW(), %s, %s, %s, %s)
                """,
                (id_usuario, id_corte, metodo_pago, total)
            )
            id_venta = cursor.lastrowid

            # 3. Insertar detalle, descontar stock y registrar movimiento en bitácora
            for id_p, item in items_carrito.items():
                subtotal = item["cantidad"] * item["precio"]
                cursor.execute(
                    """
                    INSERT INTO detalle_venta
                        (detalleVentaVentaId, detalleVentaProductoId, detalleVentaCantidadVendida,
                         detalleVentaPrecioUnitario, detalleVentaSubtotal)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (id_venta, id_p, item["cantidad"], item["precio"], subtotal)
                )
                cursor.execute(
                    "UPDATE producto SET productoStockActual = productoStockActual - %s WHERE productoId = %s",
                    (item["cantidad"], id_p)
                )
                cursor.execute(
                    """
                    INSERT INTO movimiento_inventario
                        (movimientoInventarioProductoId, movimientoInventarioTipo, movimientoInventarioCantidad,
                         movimientoInventarioFecha, movimientoInventarioUsuarioId, movimientoInventarioReferencia)
                    VALUES (%s, 'SALIDA', %s, NOW(), %s, %s)
                    """,
                    (id_p, item["cantidad"], id_usuario, f"venta #{id_venta}")
                )

            self.__connection.commit()
            return id_venta, None
        except Error as e:
            self.__connection.rollback()
            return None, f"Error al procesar la transacción: {e}"
        finally:
            cursor.close()

    def inicializar_catalogos(self):
        if not self.conectar():
            return False

        # Proveedor por defecto si la tabla está vacía
        if not self.ejecutar_consulta("SELECT proveedorId FROM proveedor LIMIT 1", fetch=True):
            self.ejecutar_consulta(
                "INSERT INTO proveedor (proveedorNombreEmpresa, proveedorTelefono) VALUES (%s, %s)",
                ("Proveedor General", "0000000000")
            )

        # Usuario Administrador por defecto (usuario: Juan | contraseña: 123)
        if not self.ejecutar_consulta("SELECT usuarioId FROM usuario LIMIT 1", fetch=True):
            hash_default = generar_hash_password("123")
            self.ejecutar_consulta(
                """
                INSERT INTO usuario
                    (usuarioNombre, usuarioCorreo, `usuarioContraseña`, usuarioRol, usuarioTurno, usuarioActivo)
                VALUES (%s, %s, %s, %s, %s, 1)
                """,
                ("Juan", "Juan@Gmail.com", hash_default, "Administrador", "Matutino")
            )
        return True


# CLASE 2: SesionUsuario. Conserva los datos del usuario que inició sesión (Singleton).
class SesionUsuario:
    _instancia = None

    def __new__(cls):
        if cls._instancia is None:
            cls._instancia = super(SesionUsuario, cls).__new__(cls)
            cls._instancia.__usuario_actual = None
        return cls._instancia

    def set_usuario_actual(self, usuario):
        self.__usuario_actual = usuario

    def iniciar_sesion(self, id_usuario, nombre, rol, correo="", turno=None):
        if id_usuario is None:
            self.set_usuario_actual(None)
        else:
            self.set_usuario_actual({
                "id": id_usuario,
                "nombre": nombre,
                "rol": rol,
                "correo": correo,
                "turno": turno
            })

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

    def get_idproducto(self):
        return self.__idproducto

    def set_idproducto(self, valor):
        self.__idproducto = None if valor is None else int(valor)

    def get_codigobarras(self):
        return self.__codigobarras

    def set_codigobarras(self, valor):
        valor = str(valor).strip()
        if not valor:
            raise ValueError("El código de barras es obligatorio.")
        self.__codigobarras = valor

    def get_nombre(self):
        return self.__nombre

    def set_nombre(self, valor):
        valor = str(valor).strip()
        if not valor:
            raise ValueError("El nombre del producto es obligatorio.")
        self.__nombre = valor

    def get_idproveedor(self):
        return self.__idproveedor

    def set_idproveedor(self, valor):
        if valor in (None, ""):
            raise ValueError("Selecciona un proveedor.")
        self.__idproveedor = int(valor)

    def get_preciocompra(self):
        return self.__preciocompra

    def set_preciocompra(self, valor):
        valor = 0.0 if valor in (None, "") else float(valor)
        if valor < 0:
            raise ValueError("El costo no puede ser negativo.")
        self.__preciocompra = valor

    def get_precioventa(self):
        return self.__precioventa

    def set_precioventa(self, valor):
        valor = float(valor)
        if valor < 0:
            raise ValueError("El precio de venta no puede ser negativo.")
        self.__precioventa = valor

    def get_stockactual(self):
        return self.__stockactual

    def set_stockactual(self, valor):
        valor = int(valor)
        if valor < 0:
            raise ValueError("El stock no puede ser negativo.")
        self.__stockactual = valor

    def get_stockminimo(self):
        return self.__stockminimo

    def set_stockminimo(self, valor):
        valor = 0 if valor in (None, "") else int(valor)
        if valor < 0:
            raise ValueError("El stock mínimo no puede ser negativo.")
        self.__stockminimo = valor

    def to_dict(self):
        return {
            "productoId": self.get_idproducto(),
            "productoCodigoBarras": self.get_codigobarras(),
            "productoNombre": self.get_nombre(),
            "productoProveedorId": self.get_idproveedor(),
            "productoPrecioCompra": self.get_preciocompra(),
            "productoPrecioVenta": self.get_precioventa(),
            "productoStockActual": self.get_stockactual(),
            "productoStockMinimo": self.get_stockminimo()
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
    def construir_interfaz(self):
        pass

    @abstractmethod
    def actualizar_datos(self):
        pass

    def refrescar_vistas_relacionadas(self):
        dashboard = getattr(self.controller, "dashboard_view", None)
        if dashboard is not None:
            dashboard.actualizar_catalogos()
        else:
            self.actualizar_datos()


# VISTA 1: LoginView. Presenta el formulario para iniciar sesión con validación segura.
class LoginView(VistaBase):
    def construir_interfaz(self):
        if not self.db.inicializar_catalogos():
            messagebox.showerror(
                "Error crítico",
                "No se pudo conectar a MySQL. Asegúrate de encender XAMPP (puerto 3306 o 3003) y crear la base de datos 'abarrotes'."
            )

        center_frame = ctk.CTkFrame(self, fg_color="transparent")
        center_frame.place(relx=0.5, rely=0.5, anchor="center")

        logo_box = ctk.CTkFrame(center_frame, fg_color="#e2e8f0", width=55, height=55, corner_radius=12)
        logo_box.pack(pady=(0, 15))
        logo_box.pack_propagate(False)
        ctk.CTkLabel(logo_box, text="A", font=("Helvetica", 24, "bold"), text_color=COLOR_PRIMARY).pack(expand=True)

        ctk.CTkLabel(
            center_frame,
            text="Abarrotes Lupita — Punto de Venta",
            font=("Helvetica", 18, "bold"),
            text_color=COLOR_PRIMARY
        ).pack(pady=(0, 20))

        card = ctk.CTkFrame(
            center_frame,
            fg_color=COLOR_CARD,
            corner_radius=16,
            width=390,
            height=400,
            border_width=1,
            border_color=COLOR_BORDER
        )
        card.pack()
        card.pack_propagate(False)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=35, pady=30)

        ctk.CTkLabel(inner, text="Iniciar sesión", font=("Helvetica", 16, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0, 5))
        ctk.CTkLabel(inner, text="Ingresa tus credenciales para acceder.", font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED).pack(anchor="w", pady=(0, 20))

        ctk.CTkLabel(inner, text="Correo o Usuario", font=("Helvetica", 11, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0, 2))
        self.user = ctk.CTkEntry(inner, placeholder_text="ej. Juan o Juan@Gmail.com", height=38, fg_color="#f8fafc", border_color=COLOR_BORDER)
        self.user.pack(fill="x", pady=(0, 12))
        self.user.bind("<Return>", lambda e: self.pwd.focus())

        ctk.CTkLabel(inner, text="Contraseña", font=("Helvetica", 11, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0, 2))
        self.pwd = ctk.CTkEntry(inner, placeholder_text="********", show="*", height=38, fg_color="#f8fafc", border_color=COLOR_BORDER)
        self.pwd.pack(fill="x", pady=(0, 20))
        self.pwd.bind("<Return>", lambda e: self.autenticar())

        ctk.CTkButton(
            inner,
            text="Ingresar al sistema",
            fg_color=COLOR_PRIMARY,
            hover_color="#1e293b",
            height=40,
            font=("Helvetica", 12, "bold"),
            command=self.autenticar
        ).pack(fill="x")

    def autenticar(self):
        correo_usuario = self.user.get().strip()
        password = self.pwd.get()

        if not correo_usuario or not password:
            messagebox.showwarning("Campos vacíos", "Ingresa tu usuario o correo y tu contraseña.")
            return

        query = """
            SELECT usuarioId, usuarioNombre, usuarioCorreo, `usuarioContraseña`,
                   usuarioRol, usuarioTurno, usuarioActivo
            FROM usuario
            WHERE LOWER(usuarioCorreo) = LOWER(%s) OR LOWER(usuarioNombre) = LOWER(%s)
            LIMIT 1
        """
        res = self.db.ejecutar_consulta(query, (correo_usuario, correo_usuario), fetch=True)

        if res is None:
            messagebox.showerror("Error de conexión", "No se pudo consultar la base de datos. Verifica XAMPP.")
            return

        if not res:
            messagebox.showerror("Error de acceso", "Usuario o contraseña incorrectos.")
            return

        usuario = res[0]
        if int(usuario["usuarioActivo"]) != 1:
            messagebox.showerror("Cuenta inactiva", "Tu cuenta está desactivada. Contacta al Administrador.")
            return

        valida, requiere_rehash = verificar_password(password, usuario["usuarioContraseña"])
        if not valida:
            messagebox.showerror("Error de acceso", "Usuario o contraseña incorrectos.")
            return

        # Migrar automáticamente contraseñas legadas en texto plano a hash seguro
        if requiere_rehash:
            nuevo_hash = generar_hash_password(password)
            self.db.ejecutar_consulta(
                "UPDATE usuario SET `usuarioContraseña` = %s WHERE usuarioId = %s",
                (nuevo_hash, usuario["usuarioId"])
            )

        self.sesion.iniciar_sesion(
            usuario["usuarioId"],
            usuario["usuarioNombre"],
            usuario["usuarioRol"],
            usuario["usuarioCorreo"],
            usuario["usuarioTurno"]
        )
        self.user.delete(0, "end")
        self.pwd.delete(0, "end")
        self.controller.iniciar_dashboard()

    def actualizar_datos(self):
        pass


# VISTA 2: PuntoDeVentaView. Permite seleccionar productos y registrar ventas vinculadas al corte.
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
        header.pack(fill="x", pady=(0, 12))
        encabezado_textos = ctk.CTkFrame(header, fg_color="transparent")
        encabezado_textos.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(encabezado_textos, text="Punto de Venta", font=("Helvetica", 24, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(encabezado_textos, text="Haz clic en un producto para agregarlo al ticket.", font=("Helvetica", 13), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        ctk.CTkButton(
            header, text="↻ Actualizar", width=120, height=34,
            fg_color=COLOR_PRIMARY, command=self.refrescar_vistas_relacionadas
        ).pack(side="right", padx=(8, 0))

        # Banner de estado de caja / turno
        self.banner_turno = ctk.CTkFrame(left_pane, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=8)
        self.banner_turno.pack(fill="x", pady=(0, 12))
        self.lbl_estado_caja = ctk.CTkLabel(
            self.banner_turno,
            text="Verificando estado de caja...",
            font=("Helvetica", 12, "bold"),
            text_color=COLOR_TEXT_MUTED
        )
        self.lbl_estado_caja.pack(side="left", padx=14, pady=8)

        self.btn_ir_corte = ctk.CTkButton(
            self.banner_turno,
            text="Abrir caja",
            width=95,
            height=26,
            fg_color=COLOR_PRIMARY,
            font=("Helvetica", 11, "bold"),
            command=self._ir_a_corte
        )

        self.products_grid = ctk.CTkScrollableFrame(left_pane, fg_color="transparent")
        self.products_grid.pack(fill="both", expand=True)

        right_pane = ctk.CTkFrame(self, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=0)
        right_pane.grid(row=0, column=1, sticky="nsew")

        ctk.CTkLabel(right_pane, text="Ticket de Venta", font=("Helvetica", 16, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", padx=20, pady=(30, 10))

        self.cart_frame = ctk.CTkScrollableFrame(right_pane, fg_color="transparent")
        self.cart_frame.pack(fill="both", expand=True, padx=10)

        bottom_box = ctk.CTkFrame(right_pane, fg_color="transparent")
        bottom_box.pack(side="bottom", fill="x", padx=20, pady=20)

        ctk.CTkFrame(bottom_box, fg_color=COLOR_BORDER, height=2).pack(fill="x", pady=(0, 15))

        total_frame = ctk.CTkFrame(bottom_box, fg_color="transparent")
        total_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(total_frame, text="Total a Pagar:", font=("Helvetica", 14, "bold"), text_color=COLOR_PRIMARY).pack(side="left")
        self.lbl_total = ctk.CTkLabel(total_frame, text="$0.00", font=("Helvetica", 22, "bold"), text_color=COLOR_SUCCESS_TXT)
        self.lbl_total.pack(side="right")

        ctk.CTkLabel(bottom_box, text="Método de pago", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0, 5))
        self.combo_metodo = ctk.CTkComboBox(bottom_box, values=["Efectivo", "Tarjeta"], fg_color="#f8fafc", border_color=COLOR_BORDER, height=35)
        self.combo_metodo.pack(fill="x", pady=(0, 15))

        ctk.CTkButton(
            bottom_box,
            text="Procesar Venta",
            fg_color=COLOR_PRIMARY,
            text_color="white",
            height=45,
            font=("Helvetica", 14, "bold"),
            corner_radius=8,
            command=self.procesar_pago
        ).pack(fill="x")

    def _ir_a_corte(self):
        dashboard = getattr(self.controller, "dashboard_view", None)
        if dashboard and "Corte de caja" in dashboard.vistas:
            dashboard.cambiar_vista("Corte de caja")

    def _obtener_corte_abierto(self):
        user = self.sesion.get_usuario_actual()
        if not user:
            return None
        res = self.db.ejecutar_consulta(
            "SELECT corteId, corteFondoInicial, corteFechaApertura FROM corte WHERE corteUsuarioId = %s AND corteEstado = 1 ORDER BY corteId DESC LIMIT 1",
            (user["id"],),
            fetch=True
        )
        return res[0] if res else None

    def actualizar_datos(self):
        corte = self._obtener_corte_abierto()
        if corte:
            self.banner_turno.configure(fg_color=COLOR_SUCCESS_BG, border_color="#a7f3d0")
            self.lbl_estado_caja.configure(
                text=f"● Turno abierto (Corte #{corte['corteId']}) — Fondo inicial: ${float(corte['corteFondoInicial']):.2f}",
                text_color=COLOR_SUCCESS_TXT
            )
            self.btn_ir_corte.pack_forget()
        else:
            self.banner_turno.configure(fg_color=COLOR_WARN_BG, border_color="#fde68a")
            self.lbl_estado_caja.configure(
                text="⚠ Caja cerrada: abre tu turno antes de registrar ventas.",
                text_color=COLOR_WARN_TXT
            )
            self.btn_ir_corte.pack(side="right", padx=12, pady=6)

        productos = self.db.ejecutar_consulta(
            """
            SELECT productoId, productoNombre, productoCodigoBarras,
                   productoPrecioVenta, productoStockActual, productoStockMinimo
            FROM producto
            ORDER BY productoNombre
            """,
            fetch=True
        )
        if productos is None:
            messagebox.showerror("Error", "No fue posible actualizar el catálogo de productos.")
            return

        for w in self.products_grid.winfo_children():
            w.destroy()

        productos_por_id = {p["productoId"]: p for p in productos}
        for id_p in list(self.carrito.keys()):
            if id_p not in productos_por_id:
                del self.carrito[id_p]
                continue
            actual = productos_por_id[id_p]
            self.carrito[id_p]["nombre"] = actual["productoNombre"]
            self.carrito[id_p]["precio"] = float(actual["productoPrecioVenta"])
            self.carrito[id_p]["stock"] = actual["productoStockActual"]
            self.carrito[id_p]["obj"] = actual
            if int(actual["productoStockActual"]) <= 0:
                del self.carrito[id_p]
            elif self.carrito[id_p]["cantidad"] > int(actual["productoStockActual"]):
                self.carrito[id_p]["cantidad"] = int(actual["productoStockActual"])

        if hasattr(self, "lbl_total"):
            self.dibujar_carrito()

        if not productos:
            ctk.CTkLabel(self.products_grid, text="No hay productos registrados.", text_color=COLOR_TEXT_MUTED).pack(pady=20)
            return

        row, col = 0, 0
        for p in productos:
            stock = int(p["productoStockActual"])
            stock_min = int(p.get("productoStockMinimo") or 0)
            borde = "#fca5a5" if stock == 0 else ("#fcd34d" if stock <= stock_min else COLOR_BORDER)

            card = ctk.CTkFrame(
                self.products_grid,
                fg_color=COLOR_CARD,
                border_width=1,
                border_color=borde,
                corner_radius=8,
                width=165,
                height=115,
                cursor="hand2"
            )
            card.grid(row=row, column=col, padx=8, pady=8)
            card.grid_propagate(False)

            card.bind("<Button-1>", lambda e, prod=p: self.agregar_al_carrito(prod))

            lbl_nom = ctk.CTkLabel(card, text=p["productoNombre"][:16], font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY)
            lbl_nom.pack(anchor="w", padx=12, pady=(12, 0))
            lbl_nom.bind("<Button-1>", lambda e, prod=p: self.agregar_al_carrito(prod))

            lbl_cod = ctk.CTkLabel(card, text=str(p["productoCodigoBarras"] or ""), font=("Helvetica", 10), text_color=COLOR_TEXT_MUTED)
            lbl_cod.pack(anchor="w", padx=12)
            lbl_cod.bind("<Button-1>", lambda e, prod=p: self.agregar_al_carrito(prod))

            bottom = ctk.CTkFrame(card, fg_color="transparent")
            bottom.pack(fill="x", side="bottom", padx=12, pady=12)
            ctk.CTkLabel(bottom, text=f"${float(p['productoPrecioVenta']):.2f}", font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY).pack(side="left")

            if stock <= 0:
                stock_color = COLOR_DANGER_TXT
            elif stock <= stock_min:
                stock_color = COLOR_WARN_TXT
            else:
                stock_color = COLOR_SUCCESS_TXT

            ctk.CTkLabel(bottom, text=f"{stock} pz", font=("Helvetica", 11, "bold"), text_color=stock_color).pack(side="right")

            col += 1
            if col > 2:
                col = 0
                row += 1

    def agregar_al_carrito(self, p):
        id_p = p["productoId"]
        stock = int(p["productoStockActual"])
        if stock <= 0:
            messagebox.showwarning("Sin stock", "Este producto está agotado.")
            return

        cant_actual = self.carrito[id_p]["cantidad"] if id_p in self.carrito else 0
        if cant_actual >= stock:
            messagebox.showwarning("Límite de stock", f"Solo hay {stock} piezas disponibles en inventario.")
            return

        if id_p in self.carrito:
            self.carrito[id_p]["cantidad"] += 1
        else:
            self.carrito[id_p] = {
                "nombre": p["productoNombre"],
                "precio": float(p["productoPrecioVenta"]),
                "cantidad": 1,
                "stock": stock,
                "obj": p
            }

        self.dibujar_carrito()

    def restar_del_carrito(self, id_p):
        if id_p in self.carrito:
            if self.carrito[id_p]["cantidad"] > 1:
                self.carrito[id_p]["cantidad"] -= 1
            else:
                del self.carrito[id_p]
        self.dibujar_carrito()

    def eliminar_del_carrito(self, id_p):
        if id_p in self.carrito:
            del self.carrito[id_p]
        self.dibujar_carrito()

    def dibujar_carrito(self):
        for w in self.cart_frame.winfo_children():
            w.destroy()

        self.total_venta = 0.0
        for id_p, data in self.carrito.items():
            item_frame = ctk.CTkFrame(self.cart_frame, fg_color=COLOR_BG_PANEL, border_width=1, border_color=COLOR_BORDER, corner_radius=8)
            item_frame.pack(fill="x", pady=5, padx=5)

            top_row = ctk.CTkFrame(item_frame, fg_color="transparent")
            top_row.pack(fill="x", padx=10, pady=(10, 5))
            ctk.CTkLabel(top_row, text=data["nombre"], font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY).pack(side="left")
            ctk.CTkButton(top_row, text="🗑️", width=25, height=25, fg_color="transparent", hover_color="#fee2e2", text_color="#ef4444", command=lambda i=id_p: self.eliminar_del_carrito(i)).pack(side="right")

            bot_row = ctk.CTkFrame(item_frame, fg_color="transparent")
            bot_row.pack(fill="x", padx=10, pady=(0, 10))

            ctrl_box = ctk.CTkFrame(bot_row, fg_color="transparent")
            ctrl_box.pack(side="left")

            ctk.CTkButton(ctrl_box, text="-", width=28, height=28, fg_color="#e2e8f0", text_color=COLOR_PRIMARY, font=("Helvetica", 14, "bold"), command=lambda i=id_p: self.restar_del_carrito(i)).pack(side="left", padx=2)
            ctk.CTkLabel(ctrl_box, text=str(data["cantidad"]), font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY, width=25).pack(side="left", padx=5)
            ctk.CTkButton(ctrl_box, text="+", width=28, height=28, fg_color="#e2e8f0", text_color=COLOR_PRIMARY, font=("Helvetica", 14, "bold"), command=lambda p=data["obj"]: self.agregar_al_carrito(p)).pack(side="left", padx=2)

            subtotal = data["cantidad"] * data["precio"]
            self.total_venta += subtotal

            detalle_texto = f"(${data['precio']:.2f} c/u) = ${subtotal:.2f}"
            ctk.CTkLabel(bot_row, text=detalle_texto, font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(side="right")

        self.lbl_total.configure(text=f"${self.total_venta:.2f}")

    def procesar_pago(self):
        if not self.carrito:
            messagebox.showwarning("Ticket vacío", "Agrega productos al ticket antes de cobrar.")
            return

        corte = self._obtener_corte_abierto()
        if not corte:
            ir = messagebox.askyesno(
                "Caja cerrada",
                "No tienes un turno de caja abierto. Para que la venta se sume a tu corte debes abrir caja primero.\n\n¿Deseas ir a Corte de Caja ahora?"
            )
            if ir:
                self._ir_a_corte()
            return

        id_usuario = self.sesion.get_usuario_actual()["id"]
        metodo = self.combo_metodo.get()

        id_venta, error_msg = self.db.registrar_venta_transaccion(
            id_usuario=id_usuario,
            id_corte=corte["corteId"],
            metodo_pago=metodo,
            total=self.total_venta,
            items_carrito=self.carrito
        )

        if error_msg:
            messagebox.showerror("No se pudo procesar la venta", error_msg)
            self.actualizar_datos()
            return

        messagebox.showinfo("Venta Exitosa", f"El ticket #{id_venta} ha sido cobrado y registrado en el Corte #{corte['corteId']}.")
        self.carrito.clear()
        self.dibujar_carrito()
        self.refrescar_vistas_relacionadas()


# VISTA 3: CorteCajaView. Apertura de turno, arqueo, cierre de caja e historial de cortes.
class CorteCajaView(VistaBase):
    def construir_interfaz(self):
        self.corte_actual = None
        self.efectivo_esperado_actual = 0.0

        main_box = ctk.CTkFrame(self, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=36, pady=28)

        header = ctk.CTkFrame(main_box, fg_color="transparent")
        header.pack(fill="x", pady=(0, 16))
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(titles, text="Corte de Caja y Turnos", font=("Helvetica", 24, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(titles, text="Controla la apertura de turno, ingresos en efectivo/tarjeta y arqueo de cierre.", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        ctk.CTkButton(
            header, text="↻ Actualizar", width=120, height=34,
            fg_color=COLOR_PRIMARY, command=self.actualizar_datos
        ).pack(side="right")

        # Panel dinámico superior (Apertura si está cerrado / Resumen y Cierre si está abierto)
        self.panel_turno = ctk.CTkFrame(main_box, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=12)
        self.panel_turno.pack(fill="x", pady=(0, 18))

        # Historial de cortes
        hist_card = ctk.CTkFrame(main_box, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=12)
        hist_card.pack(fill="both", expand=True)

        hist_header = ctk.CTkFrame(hist_card, fg_color="transparent")
        hist_header.pack(fill="x", padx=20, pady=(16, 10))
        ctk.CTkLabel(hist_header, text="Historial de Cortes de Caja", font=("Helvetica", 15, "bold"), text_color=COLOR_PRIMARY).pack(side="left")
        self.lbl_alcance_hist = ctk.CTkLabel(hist_header, text="", font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED)
        self.lbl_alcance_hist.pack(side="right")

        self.hist_scroll = ctk.CTkScrollableFrame(hist_card, fg_color="transparent")
        self.hist_scroll.pack(fill="both", expand=True, padx=14, pady=(0, 12))

    def actualizar_datos(self):
        user = self.sesion.get_usuario_actual()
        if not user:
            return

        for w in self.panel_turno.winfo_children():
            w.destroy()

        res = self.db.ejecutar_consulta(
            """
            SELECT c.corteId, c.corteUsuarioId, c.corteFechaApertura, c.corteFondoInicial, u.usuarioNombre
            FROM corte c
            JOIN usuario u ON u.usuarioId = c.corteUsuarioId
            WHERE c.corteUsuarioId = %s AND c.corteEstado = 1
            ORDER BY c.corteId DESC LIMIT 1
            """,
            (user["id"],),
            fetch=True
        )
        self.corte_actual = res[0] if res else None

        if not self.corte_actual:
            self._construir_vista_apertura()
        else:
            self._construir_vista_cierre()

        self._cargar_historial(user)

    def _construir_vista_apertura(self):
        box = ctk.CTkFrame(self.panel_turno, fg_color="transparent")
        box.pack(fill="x", padx=24, pady=22)

        badge = ctk.CTkFrame(box, fg_color=COLOR_WARN_BG, corner_radius=10)
        badge.pack(anchor="w", pady=(0, 8))
        ctk.CTkLabel(badge, text="● Sin turno activo", font=("Helvetica", 11, "bold"), text_color=COLOR_WARN_TXT).pack(padx=10, pady=3)

        ctk.CTkLabel(box, text="Abrir nuevo turno de caja", font=("Helvetica", 17, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(box, text="Ingresa el efectivo inicial disponible en caja para comenzar a registrar ventas.", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).pack(anchor="w", pady=(2, 14))

        form_row = ctk.CTkFrame(box, fg_color="transparent")
        form_row.pack(fill="x")

        ctk.CTkLabel(form_row, text="Fondo inicial ($):", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(side="left", padx=(0, 10))
        self.entry_fondo = ctk.CTkEntry(form_row, placeholder_text="Ej. 500.00", width=180, height=38, fg_color="#f8fafc", border_color=COLOR_BORDER)
        self.entry_fondo.pack(side="left", padx=(0, 14))
        self.entry_fondo.bind("<Return>", lambda e: self.abrir_caja())

        ctk.CTkButton(
            form_row,
            text="Iniciar Turno / Abrir Caja",
            fg_color=COLOR_PRIMARY,
            hover_color="#1e293b",
            height=38,
            font=("Helvetica", 12, "bold"),
            command=self.abrir_caja
        ).pack(side="left")

    def abrir_caja(self):
        texto = self.entry_fondo.get().strip()
        try:
            fondo = float(texto)
            if fondo < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Dato inválido", "Ingresa un monto válido mayor o igual a $0.00 para el fondo inicial.")
            return

        user = self.sesion.get_usuario_actual()
        corte_id = self.db.ejecutar_consulta(
            "INSERT INTO corte (corteUsuarioId, corteFechaApertura, corteFondoInicial, corteEstado) VALUES (%s, NOW(), %s, 1)",
            (user["id"], fondo)
        )
        if corte_id is None:
            messagebox.showerror("Error", "No se pudo registrar la apertura de caja.")
            return

        messagebox.showinfo("Caja abierta", f"Turno iniciado correctamente (Corte #{corte_id}) con fondo inicial de ${fondo:.2f}.")
        self.refrescar_vistas_relacionadas()

    def _construir_vista_cierre(self):
        corte_id = self.corte_actual["corteId"]
        fondo_inicial = float(self.corte_actual["corteFondoInicial"])

        totales = self.db.ejecutar_consulta(
            """
            SELECT
                COUNT(*) AS num_ventas,
                COALESCE(SUM(CASE WHEN ventaMetodoPago = 'Efectivo' THEN ventaTotal ELSE 0 END), 0) AS total_efectivo,
                COALESCE(SUM(CASE WHEN ventaMetodoPago = 'Tarjeta' THEN ventaTotal ELSE 0 END), 0) AS total_tarjeta
            FROM venta
            WHERE ventaCorteId = %s
            """,
            (corte_id,),
            fetch=True
        )
        datos = totales[0] if totales else {"num_ventas": 0, "total_efectivo": 0, "total_tarjeta": 0}
        ventas_efectivo = float(datos["total_efectivo"])
        ventas_tarjeta = float(datos["total_tarjeta"])
        num_ventas = int(datos["num_ventas"])
        self.efectivo_esperado_actual = fondo_inicial + ventas_efectivo

        box = ctk.CTkFrame(self.panel_turno, fg_color="transparent")
        box.pack(fill="x", padx=24, pady=20)

        top_info = ctk.CTkFrame(box, fg_color="transparent")
        top_info.pack(fill="x", pady=(0, 14))

        badge = ctk.CTkFrame(top_info, fg_color=COLOR_SUCCESS_BG, corner_radius=10)
        badge.pack(side="left")
        ctk.CTkLabel(badge, text=f"● Turno Abierto — Corte #{corte_id}", font=("Helvetica", 11, "bold"), text_color=COLOR_SUCCESS_TXT).pack(padx=10, pady=3)

        ctk.CTkLabel(
            top_info,
            text=f"Cajero: {self.corte_actual['usuarioNombre']}   |   Apertura: {self.corte_actual['corteFechaApertura']}   |   Tickets emitidos: {num_ventas}",
            font=("Helvetica", 11),
            text_color=COLOR_TEXT_MUTED
        ).pack(side="right")

        # Tarjetas de resumen del corte
        cards_row = ctk.CTkFrame(box, fg_color="transparent")
        cards_row.pack(fill="x", pady=(0, 16))

        metricas = [
            ("Fondo Inicial", f"${fondo_inicial:.2f}", COLOR_PRIMARY),
            ("Ventas Efectivo", f"${ventas_efectivo:.2f}", COLOR_SUCCESS_TXT),
            ("Ventas Tarjeta", f"${ventas_tarjeta:.2f}", COLOR_PRIMARY),
            ("Efectivo Esperado en Caja", f"${self.efectivo_esperado_actual:.2f}", "#0f172a"),
        ]
        for idx, (titulo, val, col) in enumerate(metricas):
            c = ctk.CTkFrame(cards_row, fg_color=COLOR_BG_PANEL, border_width=1, border_color=COLOR_BORDER, corner_radius=8, height=72)
            c.pack(side="left", fill="both", expand=True, padx=(0, 10 if idx < 3 else 0))
            c.pack_propagate(False)
            ctk.CTkLabel(c, text=titulo, font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=14, pady=(10, 0))
            ctk.CTkLabel(c, text=val, font=("Helvetica", 18, "bold"), text_color=col).pack(anchor="w", padx=14)

        # Arqueo y cierre
        cierre_row = ctk.CTkFrame(box, fg_color="transparent")
        cierre_row.pack(fill="x")

        ctk.CTkLabel(cierre_row, text="Efectivo contado físicamente ($):", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(side="left", padx=(0, 10))
        self.entry_contado = ctk.CTkEntry(cierre_row, placeholder_text=f"{self.efectivo_esperado_actual:.2f}", width=170, height=38, fg_color="#f8fafc", border_color=COLOR_BORDER)
        self.entry_contado.pack(side="left", padx=(0, 14))
        self.entry_contado.bind("<KeyRelease>", self._actualizar_preview_diferencia)

        self.lbl_diferencia = ctk.CTkLabel(
            cierre_row,
            text="Diferencia: ingresa el conteo",
            font=("Helvetica", 12, "bold"),
            text_color=COLOR_TEXT_MUTED
        )
        self.lbl_diferencia.pack(side="left", padx=(0, 16))

        ctk.CTkButton(
            cierre_row,
            text="Cerrar Turno y Guardar Corte",
            fg_color="#991b1b",
            hover_color="#7f1d1d",
            text_color="white",
            height=38,
            font=("Helvetica", 12, "bold"),
            command=self.cerrar_caja
        ).pack(side="right")

    def _actualizar_preview_diferencia(self, event=None):
        texto = self.entry_contado.get().strip()
        if not texto:
            self.lbl_diferencia.configure(text="Diferencia: ingresa el conteo", text_color=COLOR_TEXT_MUTED)
            return
        try:
            contado = float(texto)
            dif = contado - self.efectivo_esperado_actual
            if abs(dif) < 0.005:
                self.lbl_diferencia.configure(text="Diferencia: $0.00 (Cuadrado exacto)", text_color=COLOR_SUCCESS_TXT)
            elif dif > 0:
                self.lbl_diferencia.configure(text=f"Diferencia: +${dif:.2f} (Sobrante)", text_color=COLOR_WARN_TXT)
            else:
                self.lbl_diferencia.configure(text=f"Diferencia: -${abs(dif):.2f} (Faltante)", text_color=COLOR_DANGER_TXT)
        except ValueError:
            self.lbl_diferencia.configure(text="Monto inválido", text_color=COLOR_DANGER_TXT)

    def cerrar_caja(self):
        texto = self.entry_contado.get().strip()
        try:
            contado = float(texto)
            if contado < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Dato inválido", "Ingresa una cantidad válida mayor o igual a $0.00 para el efectivo contado.")
            return

        diferencia = round(contado - self.efectivo_esperado_actual, 2)
        confirmar = messagebox.askyesno(
            "Confirmar cierre de turno",
            f"¿Deseas cerrar el Corte #{self.corte_actual['corteId']}?\n\n"
            f"• Efectivo esperado: ${self.efectivo_esperado_actual:.2f}\n"
            f"• Efectivo contado: ${contado:.2f}\n"
            f"• Diferencia: ${diferencia:+.2f}\n\n"
            "Esta acción finalizará el turno actual y no se puede deshacer."
        )
        if not confirmar:
            return

        res = self.db.ejecutar_consulta(
            """
            UPDATE corte
            SET corteFechaCierre = NOW(),
                corteEfectivoEsperado = %s,
                corteEfectivoContado = %s,
                corteDiferencia = %s,
                corteEstado = 0
            WHERE corteId = %s
            """,
            (self.efectivo_esperado_actual, contado, diferencia, self.corte_actual["corteId"])
        )
        if res is None:
            messagebox.showerror("Error", "No se pudo guardar el cierre de caja.")
            return

        messagebox.showinfo("Corte cerrado", f"El Corte #{self.corte_actual['corteId']} se cerró correctamente.")
        self.refrescar_vistas_relacionadas()

    def _cargar_historial(self, user):
        for w in self.hist_scroll.winfo_children():
            w.destroy()

        es_admin = (user["rol"] == "Administrador")
        self.lbl_alcance_hist.configure(
            text="Mostrando todos los empleados (Administrador)" if es_admin else f"Mostrando cortes de {user['nombre']}"
        )

        if es_admin:
            cortes = self.db.ejecutar_consulta(
                """
                SELECT c.*, u.usuarioNombre
                FROM corte c
                JOIN usuario u ON u.usuarioId = c.corteUsuarioId
                ORDER BY c.corteId DESC LIMIT 30
                """,
                fetch=True
            )
        else:
            cortes = self.db.ejecutar_consulta(
                """
                SELECT c.*, u.usuarioNombre
                FROM corte c
                JOIN usuario u ON u.usuarioId = c.corteUsuarioId
                WHERE c.corteUsuarioId = %s
                ORDER BY c.corteId DESC LIMIT 30
                """,
                (user["id"],),
                fetch=True
            )

        headers = ["Folio", "Empleado", "Apertura", "Cierre", "Fondo", "Esperado", "Contado", "Diferencia", "Estado"]
        for col_idx, titulo in enumerate(headers):
            ctk.CTkLabel(self.hist_scroll, text=titulo, font=("Helvetica", 11, "bold"), text_color=COLOR_TEXT_MUTED).grid(
                row=0, column=col_idx, padx=10, pady=8, sticky="w"
            )

        if not cortes:
            ctk.CTkLabel(self.hist_scroll, text="Aún no hay cortes registrados.", text_color=COLOR_TEXT_MUTED).grid(
                row=1, column=0, columnspan=9, pady=20
            )
            return

        for row_idx, c in enumerate(cortes, start=1):
            abierto = int(c["corteEstado"]) == 1
            esperado = f"${float(c['corteEfectivoEsperado']):.2f}" if c["corteEfectivoEsperado"] is not None else "—"
            contado = f"${float(c['corteEfectivoContado']):.2f}" if c["corteEfectivoContado"] is not None else "—"

            if c["corteDiferencia"] is not None:
                dif_val = float(c["corteDiferencia"])
                dif_txt = f"${dif_val:+.2f}"
                dif_col = COLOR_SUCCESS_TXT if abs(dif_val) < 0.005 else (COLOR_WARN_TXT if dif_val > 0 else COLOR_DANGER_TXT)
            else:
                dif_txt = "—"
                dif_col = COLOR_TEXT_MUTED

            valores = [
                (f"#{c['corteId']}", COLOR_PRIMARY, True),
                (c["usuarioNombre"], COLOR_PRIMARY, True),
                (str(c["corteFechaApertura"])[:16], COLOR_TEXT_MUTED, False),
                (str(c["corteFechaCierre"])[:16] if c["corteFechaCierre"] else "En curso", COLOR_TEXT_MUTED, False),
                (f"${float(c['corteFondoInicial']):.2f}", COLOR_PRIMARY, False),
                (esperado, COLOR_PRIMARY, False),
                (contado, COLOR_PRIMARY, False),
                (dif_txt, dif_col, True),
            ]
            for col_idx, (txt, col, negrita) in enumerate(valores):
                ctk.CTkLabel(
                    self.hist_scroll,
                    text=txt,
                    font=("Helvetica", 11, "bold" if negrita else "normal"),
                    text_color=col
                ).grid(row=row_idx, column=col_idx, padx=10, pady=7, sticky="w")

            badge = ctk.CTkFrame(
                self.hist_scroll,
                fg_color=COLOR_SUCCESS_BG if abierto else "#e2e8f0",
                corner_radius=10
            )
            badge.grid(row=row_idx, column=8, padx=10, pady=5, sticky="w")
            ctk.CTkLabel(
                badge,
                text="Abierto" if abierto else "Cerrado",
                font=("Helvetica", 10, "bold"),
                text_color=COLOR_SUCCESS_TXT if abierto else COLOR_PRIMARY
            ).pack(padx=8, pady=2)


# VISTA 4: ProductosView. Administra altas, consultas, cambios y bajas de productos.
class ProductosView(VistaBase):
    def construir_interfaz(self):
        main_box = ctk.CTkFrame(self, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=40, pady=30)

        header_frame = ctk.CTkFrame(main_box, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(header_frame, text="Productos", font=("Helvetica", 24, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(header_frame, text="Gestiona el inventario, revisa disponibilidad, stock mínimo y precios.", font=("Helvetica", 13), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        self.action_bar = ctk.CTkFrame(main_box, fg_color="transparent")
        self.action_bar.pack(fill="x", pady=(0, 20))
        self.btn_agregar_prod = ctk.CTkButton(
            self.action_bar, text="Agregar producto +", fg_color=COLOR_PRIMARY, text_color="white",
            corner_radius=6, height=38, font=("Helvetica", 12, "bold"),
            command=self.modal_agregar_producto
        )
        self.btn_agregar_prod.pack(side="right")

        ctk.CTkButton(
            self.action_bar, text="↻ Actualizar pantalla", fg_color=COLOR_PRIMARY, text_color="white",
            corner_radius=6, height=38, font=("Helvetica", 12),
            command=self.refrescar_vistas_relacionadas
        ).pack(side="right", padx=8)

        self.metrics_frame = ctk.CTkFrame(main_box, fg_color="transparent")
        self.metrics_frame.pack(fill="x", pady=(0, 20))
        table_container = ctk.CTkFrame(main_box, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=10)
        table_container.pack(fill="both", expand=True)
        self.table_frame = ctk.CTkScrollableFrame(table_container, fg_color="transparent")
        self.table_frame.pack(fill="both", expand=True, padx=5, pady=5)

    def actualizar_datos(self):
        user = self.sesion.get_usuario_actual()
        puede_editar = (user is not None and user["rol"] in ("Administrador", "Almacen"))

        if puede_editar:
            self.btn_agregar_prod.pack(side="right")
        else:
            self.btn_agregar_prod.pack_forget()

        for widget in self.metrics_frame.winfo_children():
            widget.destroy()

        stats = self.db.ejecutar_consulta(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN productoStockActual > 0 THEN 1 ELSE 0 END) AS en_stock,
                SUM(CASE WHEN productoStockActual <= productoStockMinimo THEN 1 ELSE 0 END) AS alerta_stock
            FROM producto
            """,
            fetch=True
        )
        if stats and stats[0]["total"] is not None:
            datos_metricas = [
                ("Total de productos", str(stats[0]["total"]), COLOR_PRIMARY),
                ("En stock", str(stats[0]["en_stock"] or 0), COLOR_SUCCESS_TXT),
                ("En stock mínimo / agotados", str(stats[0]["alerta_stock"] or 0), COLOR_WARN_TXT)
            ]
            for idx, (label, valor, color_val) in enumerate(datos_metricas):
                card = ctk.CTkFrame(self.metrics_frame, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=8, height=75)
                card.pack(side="left", padx=(0, 10 if idx < 2 else 0), expand=True, fill="both")
                card.pack_propagate(False)
                ctk.CTkLabel(card, text=label, font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=15, pady=(10, 0))
                ctk.CTkLabel(card, text=valor, font=("Helvetica", 18, "bold"), text_color=color_val).pack(anchor="w", padx=15)

        for widget in self.table_frame.winfo_children():
            widget.destroy()

        headers = ["Producto", "Código", "Precio", "Inventario", "Mínimo", "Estado"]
        if puede_editar:
            headers.append("Acciones")

        for idx, titulo in enumerate(headers):
            ctk.CTkLabel(self.table_frame, text=titulo, font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).grid(
                row=0, column=idx, padx=14, pady=15, sticky="w"
            )

        productos = self.db.ejecutar_consulta("SELECT * FROM producto ORDER BY productoNombre", fetch=True)
        if productos is None:
            ctk.CTkLabel(self.table_frame, text="No fue posible consultar los productos.", text_color=COLOR_DANGER_TXT).grid(
                row=1, column=0, columnspan=len(headers), pady=20
            )
            return
        if not productos:
            ctk.CTkLabel(self.table_frame, text="No hay productos registrados.", text_color=COLOR_TEXT_MUTED).grid(
                row=1, column=0, columnspan=len(headers), pady=20
            )
            return

        for i, producto in enumerate(productos, start=1):
            stock = int(producto["productoStockActual"])
            stock_min = int(producto.get("productoStockMinimo") or 0)

            ctk.CTkLabel(self.table_frame, text=producto["productoNombre"], font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY).grid(
                row=i, column=0, padx=14, pady=10, sticky="w"
            )
            ctk.CTkLabel(self.table_frame, text=str(producto["productoCodigoBarras"] or ""), font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(
                row=i, column=1, padx=14, sticky="w"
            )
            ctk.CTkLabel(self.table_frame, text=f"${float(producto['productoPrecioVenta']):.2f}", font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY).grid(
                row=i, column=2, padx=14, sticky="w"
            )
            ctk.CTkLabel(self.table_frame, text=f"{stock} pz", font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY).grid(
                row=i, column=3, padx=14, sticky="w"
            )
            ctk.CTkLabel(self.table_frame, text=f"{stock_min} pz", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(
                row=i, column=4, padx=14, sticky="w"
            )

            if stock <= 0:
                bg, fg, txt = COLOR_DANGER_BG, COLOR_DANGER_TXT, "Agotado"
            elif stock <= stock_min:
                bg, fg, txt = COLOR_WARN_BG, COLOR_WARN_TXT, "Stock bajo"
            else:
                bg, fg, txt = COLOR_SUCCESS_BG, COLOR_SUCCESS_TXT, "En stock"

            estado_frame = ctk.CTkFrame(self.table_frame, fg_color=bg, corner_radius=12)
            estado_frame.grid(row=i, column=5, padx=14, sticky="w")
            ctk.CTkLabel(estado_frame, text=txt, font=("Helvetica", 11, "bold"), text_color=fg).pack(padx=10, pady=2)

            if puede_editar:
                acciones = ctk.CTkFrame(self.table_frame, fg_color="transparent")
                acciones.grid(row=i, column=6, padx=10, sticky="w")
                ctk.CTkButton(
                    acciones, text="Editar", width=65, height=28,
                    fg_color="transparent", border_width=1, border_color=COLOR_BORDER, text_color=COLOR_PRIMARY,
                    command=lambda p=producto: self.modal_editar_producto(p)
                ).pack(side="left", padx=3)
                ctk.CTkButton(
                    acciones, text="Eliminar", width=70, height=28,
                    fg_color=COLOR_DANGER_BG, hover_color="#fecaca", text_color=COLOR_DANGER_TXT,
                    command=lambda p=producto: self.eliminar_producto(p)
                ).pack(side="left", padx=3)

    def modal_agregar_producto(self):
        self._abrir_formulario_producto()

    def modal_editar_producto(self, producto):
        self._abrir_formulario_producto(producto)

    def _abrir_formulario_producto(self, producto=None):
        es_edicion = producto is not None
        proveedores = self.db.ejecutar_consulta(
            "SELECT proveedorId, proveedorNombreEmpresa FROM proveedor ORDER BY proveedorNombreEmpresa",
            fetch=True
        ) or []

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
            "codigobarras": producto["productoCodigoBarras"] if es_edicion else "",
            "nombre": producto["productoNombre"] if es_edicion else "",
            "preciocompra": str(producto["productoPrecioCompra"]) if es_edicion and producto["productoPrecioCompra"] is not None else "",
            "precioventa": str(producto["productoPrecioVenta"]) if es_edicion else "",
            "stockactual": str(producto["productoStockActual"]) if es_edicion else "0",
            "stockminimo": str(producto.get("productoStockMinimo", 0)) if es_edicion else "0"
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

        mapa_proveedores = {f"{p['proveedorId']} | {p['proveedorNombreEmpresa']}": p["proveedorId"] for p in proveedores}

        ctk.CTkLabel(inner, text="Proveedor", font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(9, 2))
        combo_proveedor = ctk.CTkComboBox(inner, values=list(mapa_proveedores.keys()), height=35)
        combo_proveedor.pack(fill="x", pady=(0, 4))

        if es_edicion:
            for etiqueta, identificador in mapa_proveedores.items():
                if identificador == producto["productoProveedorId"]:
                    combo_proveedor.set(etiqueta)
                    break
        else:
            combo_proveedor.set(next(iter(mapa_proveedores)))

        def guardar():
            try:
                proveedor_id = mapa_proveedores.get(combo_proveedor.get())
                nuevo_producto = Producto(
                    producto["productoId"] if es_edicion else None,
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
                        """
                        UPDATE producto
                        SET productoCodigoBarras=%s, productoNombre=%s, productoProveedorId=%s,
                            productoPrecioCompra=%s, productoPrecioVenta=%s,
                            productoStockActual=%s, productoStockMinimo=%s
                        WHERE productoId=%s
                        """,
                        (
                            datos["productoCodigoBarras"], datos["productoNombre"], datos["productoProveedorId"],
                            datos["productoPrecioCompra"] if datos["productoPrecioCompra"] > 0 else None,
                            datos["productoPrecioVenta"], datos["productoStockActual"],
                            datos["productoStockMinimo"], datos["productoId"]
                        )
                    )
                else:
                    resultado = self.db.ejecutar_consulta(
                        """
                        INSERT INTO producto
                            (productoCodigoBarras, productoNombre, productoProveedorId,
                             productoPrecioCompra, productoPrecioVenta, productoStockActual, productoStockMinimo)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            datos["productoCodigoBarras"], datos["productoNombre"], datos["productoProveedorId"],
                            datos["productoPrecioCompra"] if datos["productoPrecioCompra"] > 0 else None,
                            datos["productoPrecioVenta"], datos["productoStockActual"], datos["productoStockMinimo"]
                        )
                    )

                if resultado is None:
                    messagebox.showerror("Error", "No se pudo guardar el producto. Verifica que el código de barras no esté repetido.")
                    return

                modal.destroy()
                self.refrescar_vistas_relacionadas()
                messagebox.showinfo("Producto guardado", "Los datos del producto se guardaron correctamente.")
            except (ValueError, TypeError) as error:
                messagebox.showerror("Datos inválidos", str(error))
            except Exception as error:
                messagebox.showerror("Error", f"No se pudo guardar el producto: {error}")

        ctk.CTkButton(
            inner, text="Guardar cambios" if es_edicion else "Guardar producto",
            fg_color=COLOR_PRIMARY, height=42, command=guardar
        ).pack(pady=20, fill="x")

    def eliminar_producto(self, producto):
        confirmar = messagebox.askyesno(
            "Eliminar producto",
            f"¿Seguro que deseas eliminar '{producto['productoNombre']}'? Esta acción no se puede deshacer."
        )
        if not confirmar:
            return

        resultado = self.db.ejecutar_consulta(
            "DELETE FROM producto WHERE productoId = %s", (producto["productoId"],)
        )
        if resultado is None:
            messagebox.showerror(
                "No se pudo eliminar",
                "El producto tiene registros de ventas o compras relacionadas. La base de datos impide borrarlo para conservar el historial."
            )
        elif resultado == 0:
            messagebox.showwarning("Sin cambios", "El producto ya no existe o no se encontró.")
        else:
            self.refrescar_vistas_relacionadas()
            messagebox.showinfo("Producto eliminado", "El producto se eliminó correctamente.")


# VISTA 5: ProveedoresView. Administra altas, consultas, cambios y bajas de proveedores.
class ProveedoresView(VistaBase):
    def construir_interfaz(self):
        main_box = ctk.CTkFrame(self, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=40, pady=30)

        header_frame = ctk.CTkFrame(main_box, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))
        titles = ctk.CTkFrame(header_frame, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(titles, text="Proveedores", font=("Helvetica", 24, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(titles, text="Gestiona empresas y teléfonos de proveedores.", font=("Helvetica", 13), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        actions = ctk.CTkFrame(header_frame, fg_color="transparent")
        actions.pack(side="right", fill="y")
        ctk.CTkButton(
            actions, text="Agregar proveedor +", fg_color=COLOR_PRIMARY,
            corner_radius=6, height=35, font=("Helvetica", 12, "bold"), command=self.modal_agregar
        ).pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            actions, text="↻ Actualizar pantalla", fg_color=COLOR_PRIMARY,
            corner_radius=6, height=35, command=self.refrescar_vistas_relacionadas
        ).pack(side="left", padx=8)

        table_container = ctk.CTkFrame(main_box, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=10)
        table_container.pack(fill="both", expand=True, pady=(20, 0))
        self.table_frame = ctk.CTkScrollableFrame(table_container, fg_color="transparent")
        self.table_frame.pack(fill="both", expand=True, padx=5, pady=5)

    def actualizar_datos(self):
        proveedores = self.db.ejecutar_consulta(
            "SELECT * FROM proveedor ORDER BY proveedorNombreEmpresa", fetch=True
        )
        for widget in self.table_frame.winfo_children():
            widget.destroy()

        headers = ["Empresa", "Teléfono", "Acciones"]
        for idx, titulo in enumerate(headers):
            ctk.CTkLabel(self.table_frame, text=titulo, font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).grid(
                row=0, column=idx, padx=20, pady=15, sticky="w"
            )

        if proveedores is None:
            ctk.CTkLabel(self.table_frame, text="No fue posible consultar los proveedores.", text_color=COLOR_DANGER_TXT).grid(
                row=1, column=0, columnspan=3, pady=20
            )
            return
        if not proveedores:
            ctk.CTkLabel(self.table_frame, text="No hay proveedores registrados.", text_color=COLOR_TEXT_MUTED).grid(
                row=1, column=0, columnspan=3, pady=20
            )
            return

        for i, proveedor in enumerate(proveedores, start=1):
            ctk.CTkLabel(self.table_frame, text=proveedor["proveedorNombreEmpresa"], font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY).grid(
                row=i, column=0, padx=20, pady=10, sticky="w"
            )
            ctk.CTkLabel(self.table_frame, text=proveedor.get("proveedorTelefono") or "—", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(
                row=i, column=1, padx=20, sticky="w"
            )

            acciones = ctk.CTkFrame(self.table_frame, fg_color="transparent")
            acciones.grid(row=i, column=2, padx=15, sticky="w")
            ctk.CTkButton(
                acciones, text="Editar", width=65, height=30,
                fg_color="transparent", border_width=1, border_color=COLOR_BORDER, text_color=COLOR_PRIMARY,
                command=lambda p=proveedor: self.modal_editar(p)
            ).pack(side="left", padx=3)
            ctk.CTkButton(
                acciones, text="Eliminar", width=70, height=30,
                fg_color=COLOR_DANGER_BG, hover_color="#fecaca", text_color=COLOR_DANGER_TXT,
                command=lambda p=proveedor: self.eliminar_proveedor(p)
            ).pack(side="left", padx=3)

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
            ("empresa", "Nombre de la Empresa", proveedor.get("proveedorNombreEmpresa", "") if es_edicion else ""),
            ("telefono", "Teléfono", proveedor.get("proveedorTelefono", "") if es_edicion else "")
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
                    "UPDATE proveedor SET proveedorNombreEmpresa=%s, proveedorTelefono=%s WHERE proveedorId=%s",
                    (empresa, telefono, proveedor["proveedorId"])
                )
            else:
                resultado = self.db.ejecutar_consulta(
                    "INSERT INTO proveedor (proveedorNombreEmpresa, proveedorTelefono) VALUES (%s, %s)",
                    (empresa, telefono)
                )

            if resultado is None:
                messagebox.showerror("Error", "No se pudieron guardar los datos del proveedor.")
                return
            modal.destroy()
            self.refrescar_vistas_relacionadas()
            messagebox.showinfo("Proveedor guardado", "Los datos del proveedor se guardaron correctamente.")

        ctk.CTkButton(
            inner, text="Guardar cambios" if es_edicion else "Guardar proveedor",
            fg_color=COLOR_PRIMARY, height=40, command=guardar
        ).pack(pady=25, fill="x")

    def eliminar_proveedor(self, proveedor):
        confirmar = messagebox.askyesno(
            "Eliminar proveedor",
            f"¿Seguro que deseas eliminar a '{proveedor['proveedorNombreEmpresa']}'?"
        )
        if not confirmar:
            return

        resultado = self.db.ejecutar_consulta(
            "DELETE FROM proveedor WHERE proveedorId=%s", (proveedor["proveedorId"],)
        )
        if resultado is None:
            messagebox.showerror("No se pudo eliminar", "Este proveedor está asociado a productos o compras existentes.")
        elif resultado == 0:
            messagebox.showwarning("Sin cambios", "El proveedor ya no existe o no se encontró.")
        else:
            self.refrescar_vistas_relacionadas()
            messagebox.showinfo("Proveedor eliminado", "El proveedor se eliminó correctamente.")


# VISTA 6: EmpleadosView. Gestión CRUD de empleados (tabla usuario) y monitoreo de turnos (tabla corte).
class EmpleadosView(VistaBase):
    def construir_interfaz(self):
        self.pestana_activa = "Empleados"
        self.pestana_botones = {}
        self.empleados_cache = []

        main_box = ctk.CTkFrame(self, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=36, pady=28)

        # Encabezado superior
        header_frame = ctk.CTkFrame(main_box, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 14))

        titles = ctk.CTkFrame(header_frame, fg_color="transparent")
        titles.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(titles, text="EMPLEADOS Y ROLES", font=("Helvetica", 10, "bold"), text_color=COLOR_TEXT_MUTED).pack(anchor="w")
        ctk.CTkLabel(titles, text="Gestión de Personal y Turnos", font=("Helvetica", 24, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(2, 2))
        ctk.CTkLabel(titles, text="Administra cuentas de acceso, roles, turnos y estado de actividad del equipo.", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        actions = ctk.CTkFrame(header_frame, fg_color="transparent")
        actions.pack(side="right", anchor="n")

        ctk.CTkButton(
            actions, text="↻ Actualizar", fg_color=COLOR_PRIMARY,
            corner_radius=8, height=38, font=("Helvetica", 12),
            command=self.actualizar_datos
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            actions, text="+ Agregar empleado", fg_color=COLOR_PRIMARY, hover_color="#1e293b",
            text_color="white", corner_radius=8, height=38, font=("Helvetica", 12, "bold"),
            command=self.modal_agregar_empleado
        ).pack(side="left")

        # Subpestañas funcionales
        tabs_bar = ctk.CTkFrame(main_box, fg_color="#e9eff5", corner_radius=8, height=38)
        tabs_bar.pack(fill="x", pady=(0, 16))
        tabs_bar.pack_propagate(False)

        for idx, nombre_tab in enumerate(["Empleados", "Turnos hoy"]):
            tabs_bar.grid_columnconfigure(idx, weight=1)
            btn = ctk.CTkButton(
                tabs_bar, text=nombre_tab, corner_radius=6, height=30,
                font=("Helvetica", 12, "bold"),
                command=lambda t=nombre_tab: self._seleccionar_pestana(t)
            )
            btn.grid(row=0, column=idx, padx=4, pady=4, sticky="nsew")
            self.pestana_botones[nombre_tab] = btn

        # Tarjetas de métricas reales desde MySQL
        self.metrics_row = ctk.CTkFrame(main_box, fg_color="transparent")
        self.metrics_row.pack(fill="x", pady=(0, 16))

        # Contenedor principal de tabla
        table_card = ctk.CTkFrame(main_box, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=12)
        table_card.pack(fill="both", expand=True)

        # Barra de búsqueda y filtro
        filter_row = ctk.CTkFrame(table_card, fg_color="transparent")
        filter_row.pack(fill="x", padx=18, pady=(16, 12))

        self.entrada_buscar = ctk.CTkEntry(
            filter_row,
            placeholder_text="Buscar por nombre, correo, rol o turno...",
            height=36,
            fg_color="#ffffff",
            border_color=COLOR_BORDER,
            corner_radius=8
        )
        self.entrada_buscar.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.entrada_buscar.bind("<KeyRelease>", lambda e: self._renderizar_contenido())

        self.combo_filtro_estado = ctk.CTkComboBox(
            filter_row,
            values=["Todos", "Activos", "Inactivos"],
            width=140,
            height=36,
            fg_color="#ffffff",
            border_color=COLOR_BORDER,
            command=lambda _: self._renderizar_contenido()
        )
        self.combo_filtro_estado.set("Todos")
        self.combo_filtro_estado.pack(side="right")

        self.filas_scroll = ctk.CTkScrollableFrame(table_card, fg_color="transparent")
        self.filas_scroll.pack(fill="both", expand=True, padx=18, pady=(4, 8))

        footer_row = ctk.CTkFrame(table_card, fg_color="transparent")
        footer_row.pack(fill="x", padx=18, pady=(4, 14))
        self.lbl_conteo_footer = ctk.CTkLabel(footer_row, text="", font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED)
        self.lbl_conteo_footer.pack(side="left")

        self._seleccionar_pestana("Empleados")

    def _seleccionar_pestana(self, nombre_tab):
        self.pestana_activa = nombre_tab
        for tab, btn in self.pestana_botones.items():
            activa = (tab == nombre_tab)
            btn.configure(
                fg_color=COLOR_CARD if activa else "transparent",
                text_color=COLOR_PRIMARY if activa else COLOR_TEXT_MUTED,
                hover_color=COLOR_CARD if activa else "#dce4f2"
            )
        self._renderizar_contenido()

    def actualizar_datos(self):
        usuarios = self.db.ejecutar_consulta(
            """
            SELECT u.usuarioId, u.usuarioNombre, u.usuarioCorreo, u.usuarioRol,
                   u.usuarioTurno, u.usuarioActivo,
                   (SELECT c.corteId FROM corte c WHERE c.corteUsuarioId = u.usuarioId AND c.corteEstado = 1 LIMIT 1) AS corte_abierto
            FROM usuario u
            ORDER BY u.usuarioActivo DESC, u.usuarioNombre ASC
            """,
            fetch=True
        )
        if usuarios is None:
            messagebox.showerror("Error", "No fue posible consultar los empleados en MySQL.")
            return

        self.empleados_cache = usuarios

        # Actualizar tarjetas métricas
        for w in self.metrics_row.winfo_children():
            w.destroy()

        total_emp = len(usuarios)
        activos = sum(1 for u in usuarios if int(u["usuarioActivo"]) == 1)
        en_turno = sum(1 for u in usuarios if u.get("corte_abierto") is not None)

        tarjetas = [
            ("Total empleados", str(total_emp), "Registrados en sistema", COLOR_PRIMARY),
            ("Cuentas activas", str(activos), "Con acceso habilitado", COLOR_SUCCESS_TXT),
            ("En turno (caja abierta)", str(en_turno), "Operando mostrador ahora", COLOR_WARN_TXT if en_turno == 0 else COLOR_SUCCESS_TXT),
        ]
        for idx, (titulo, val, sub, col) in enumerate(tarjetas):
            card = ctk.CTkFrame(self.metrics_row, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=10, height=88)
            card.pack(side="left", fill="both", expand=True, padx=(0, 12 if idx < 2 else 0))
            card.pack_propagate(False)
            ctk.CTkLabel(card, text=titulo, font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=16, pady=(10, 0))
            ctk.CTkLabel(card, text=val, font=("Helvetica", 20, "bold"), text_color=col).pack(anchor="w", padx=16)
            ctk.CTkLabel(card, text=sub, font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=16)

        self._renderizar_contenido()

    def _renderizar_contenido(self):
        for w in self.filas_scroll.winfo_children():
            w.destroy()

        if self.pestana_activa == "Turnos hoy":
            self._renderizar_turnos_hoy()
            return

        termino = self.entrada_buscar.get().strip().lower()
        filtro = self.combo_filtro_estado.get()

        filtrados = []
        for u in self.empleados_cache:
            activo = int(u["usuarioActivo"]) == 1
            if filtro == "Activos" and not activo:
                continue
            if filtro == "Inactivos" and activo:
                continue

            texto_busqueda = f"{u['usuarioNombre']} {u['usuarioCorreo']} {u['usuarioRol']} {u['usuarioTurno'] or ''}".lower()
            if termino and termino not in texto_busqueda:
                continue
            filtrados.append(u)

        headers = ["Empleado", "Correo", "Rol", "Turno", "Estado", "Acciones"]
        for col_idx, titulo in enumerate(headers):
            ctk.CTkLabel(self.filas_scroll, text=titulo, font=("Helvetica", 11, "bold"), text_color=COLOR_TEXT_MUTED).grid(
                row=0, column=col_idx, padx=12, pady=10, sticky="w"
            )

        if not filtrados:
            ctk.CTkLabel(self.filas_scroll, text="No se encontraron empleados con ese filtro.", text_color=COLOR_TEXT_MUTED).grid(
                row=1, column=0, columnspan=6, pady=24
            )
            self.lbl_conteo_footer.configure(text=f"Mostrando 0 de {len(self.empleados_cache)} empleados")
            return

        usuario_sesion = self.sesion.get_usuario_actual()
        id_actual = usuario_sesion["id"] if usuario_sesion else None

        for row_idx, emp in enumerate(filtrados, start=1):
            activo = int(emp["usuarioActivo"]) == 1
            en_caja = emp.get("corte_abierto") is not None

            ctk.CTkLabel(
                self.filas_scroll,
                text=f"{emp['usuarioNombre']} (ID #{emp['usuarioId']})",
                font=("Helvetica", 12, "bold"),
                text_color=COLOR_PRIMARY
            ).grid(row=row_idx, column=0, padx=12, pady=9, sticky="w")

            ctk.CTkLabel(self.filas_scroll, text=emp["usuarioCorreo"], font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(
                row=row_idx, column=1, padx=12, sticky="w"
            )
            ctk.CTkLabel(self.filas_scroll, text=emp["usuarioRol"], font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).grid(
                row=row_idx, column=2, padx=12, sticky="w"
            )
            ctk.CTkLabel(self.filas_scroll, text=emp["usuarioTurno"] or "Sin asignar", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(
                row=row_idx, column=3, padx=12, sticky="w"
            )

            if activo and en_caja:
                bg, fg, txt = COLOR_SUCCESS_BG, COLOR_SUCCESS_TXT, "• En turno (Caja)"
            elif activo:
                bg, fg, txt = "#e0f2fe", "#0369a1", "• Activo"
            else:
                bg, fg, txt = COLOR_DANGER_BG, COLOR_DANGER_TXT, "• Inactivo"

            badge = ctk.CTkFrame(self.filas_scroll, fg_color=bg, corner_radius=12)
            badge.grid(row=row_idx, column=4, padx=12, sticky="w")
            ctk.CTkLabel(badge, text=txt, font=("Helvetica", 11, "bold"), text_color=fg).pack(padx=10, pady=2)

            acciones = ctk.CTkFrame(self.filas_scroll, fg_color="transparent")
            acciones.grid(row=row_idx, column=5, padx=10, sticky="w")

            ctk.CTkButton(
                acciones, text="Editar", width=62, height=28,
                fg_color="transparent", border_width=1, border_color=COLOR_BORDER, text_color=COLOR_PRIMARY,
                command=lambda e=emp: self.modal_editar_empleado(e)
            ).pack(side="left", padx=3)

            if emp["usuarioId"] != id_actual:
                ctk.CTkButton(
                    acciones,
                    text="Desactivar" if activo else "Activar",
                    width=78,
                    height=28,
                    fg_color=COLOR_DANGER_BG if activo else COLOR_SUCCESS_BG,
                    hover_color="#fecaca" if activo else "#a7f3d0",
                    text_color=COLOR_DANGER_TXT if activo else COLOR_SUCCESS_TXT,
                    command=lambda e=emp: self.alternar_estado_empleado(e)
                ).pack(side="left", padx=3)

        self.lbl_conteo_footer.configure(text=f"Mostrando {len(filtrados)} de {len(self.empleados_cache)} empleados")

    def _renderizar_turnos_hoy(self):
        cortes_hoy = self.db.ejecutar_consulta(
            """
            SELECT c.corteId, u.usuarioNombre, u.usuarioRol, u.usuarioTurno,
                   c.corteFechaApertura, c.corteFechaCierre, c.corteEstado
            FROM corte c
            JOIN usuario u ON u.usuarioId = c.corteUsuarioId
            WHERE DATE(c.corteFechaApertura) = CURDATE()
            ORDER BY c.corteId DESC
            """,
            fetch=True
        ) or []

        headers = ["Empleado", "Rol / Turno", "Entrada (Apertura)", "Salida (Cierre)", "Estado"]
        for col_idx, titulo in enumerate(headers):
            ctk.CTkLabel(self.filas_scroll, text=titulo, font=("Helvetica", 11, "bold"), text_color=COLOR_TEXT_MUTED).grid(
                row=0, column=col_idx, padx=14, pady=10, sticky="w"
            )

        if not cortes_hoy:
            ctk.CTkLabel(
                self.filas_scroll,
                text="No hay aperturas de caja registradas el día de hoy.",
                text_color=COLOR_TEXT_MUTED
            ).grid(row=1, column=0, columnspan=5, pady=24)
            self.lbl_conteo_footer.configure(text="0 turnos registrados hoy")
            return

        for row_idx, c in enumerate(cortes_hoy, start=1):
            en_curso = int(c["corteEstado"]) == 1
            entrada = str(c["corteFechaApertura"])[11:16]
            salida = str(c["corteFechaCierre"])[11:16] if c["corteFechaCierre"] else "—"

            ctk.CTkLabel(self.filas_scroll, text=c["usuarioNombre"], font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).grid(
                row=row_idx, column=0, padx=14, pady=9, sticky="w"
            )
            ctk.CTkLabel(self.filas_scroll, text=f"{c['usuarioRol']} • {c['usuarioTurno'] or 'N/A'}", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(
                row=row_idx, column=1, padx=14, sticky="w"
            )
            ctk.CTkLabel(self.filas_scroll, text=entrada, font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).grid(
                row=row_idx, column=2, padx=14, sticky="w"
            )
            ctk.CTkLabel(self.filas_scroll, text=salida, font=("Helvetica", 12), text_color=COLOR_PRIMARY if salida != "—" else COLOR_TEXT_MUTED).grid(
                row=row_idx, column=3, padx=14, sticky="w"
            )

            badge = ctk.CTkFrame(
                self.filas_scroll,
                fg_color=COLOR_SUCCESS_BG if en_curso else "#e2e8f0",
                corner_radius=12
            )
            badge.grid(row=row_idx, column=4, padx=14, sticky="w")
            ctk.CTkLabel(
                badge,
                text="• En turno" if en_curso else "• Finalizado",
                font=("Helvetica", 11, "bold"),
                text_color=COLOR_SUCCESS_TXT if en_curso else COLOR_PRIMARY
            ).pack(padx=10, pady=2)

        self.lbl_conteo_footer.configure(text=f"Mostrando {len(cortes_hoy)} registros de turno hoy")

    def modal_agregar_empleado(self):
        self._abrir_formulario_empleado()

    def modal_editar_empleado(self, empleado):
        self._abrir_formulario_empleado(empleado)

    def _abrir_formulario_empleado(self, empleado=None):
        es_edicion = empleado is not None
        modal = ctk.CTkToplevel(self)
        modal.title("Editar empleado" if es_edicion else "Nuevo empleado")
        modal.geometry("430x540")
        modal.grab_set()

        inner = ctk.CTkScrollableFrame(modal, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=26, pady=20)

        ctk.CTkLabel(
            inner,
            text="Editar cuenta de empleado" if es_edicion else "Registrar nuevo empleado",
            font=("Helvetica", 16, "bold"),
            text_color=COLOR_PRIMARY
        ).pack(anchor="w", pady=(0, 12))

        ctk.CTkLabel(inner, text="Nombre completo", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(6, 2))
        ent_nombre = ctk.CTkEntry(inner, placeholder_text="Ej. Epifania Cruz García", height=35)
        ent_nombre.pack(fill="x")
        if es_edicion:
            ent_nombre.insert(0, empleado["usuarioNombre"])

        ctk.CTkLabel(inner, text="Correo electrónico (acceso)", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(10, 2))
        ent_correo = ctk.CTkEntry(inner, placeholder_text="Ej. cajero1@abarrotes.com", height=35)
        ent_correo.pack(fill="x")
        if es_edicion:
            ent_correo.insert(0, empleado["usuarioCorreo"])

        lbl_pass = "Nueva contraseña (dejar vacío para conservar actual)" if es_edicion else "Contraseña"
        ctk.CTkLabel(inner, text=lbl_pass, font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(10, 2))
        ent_pass = ctk.CTkEntry(inner, placeholder_text="********", show="*", height=35)
        ent_pass.pack(fill="x")

        ctk.CTkLabel(inner, text="Rol en el sistema", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(10, 2))
        combo_rol = ctk.CTkComboBox(inner, values=["Cajero", "Administrador", "Almacen"], height=35)
        combo_rol.pack(fill="x")
        combo_rol.set(empleado["usuarioRol"] if es_edicion else "Cajero")

        ctk.CTkLabel(inner, text="Turno asignado", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(10, 2))
        combo_turno = ctk.CTkComboBox(inner, values=["Matutino", "Vespertino", "Nocturno"], height=35)
        combo_turno.pack(fill="x")
        combo_turno.set(empleado["usuarioTurno"] if (es_edicion and empleado["usuarioTurno"]) else "Matutino")

        def guardar():
            nombre = ent_nombre.get().strip()
            correo = ent_correo.get().strip()
            password = ent_pass.get()
            rol = combo_rol.get()
            turno = combo_turno.get()

            if not nombre or not correo:
                messagebox.showwarning("Campos obligatorios", "El nombre y el correo electrónico son obligatorios.")
                return
            if "@" not in correo:
                messagebox.showwarning("Correo inválido", "Ingresa un correo electrónico válido.")
                return
            if not es_edicion and len(password) < 3:
                messagebox.showwarning("Contraseña corta", "La contraseña debe tener al menos 3 caracteres.")
                return

            if es_edicion:
                if password:
                    pwd_hash = generar_hash_password(password)
                    res = self.db.ejecutar_consulta(
                        """
                        UPDATE usuario
                        SET usuarioNombre=%s, usuarioCorreo=%s, `usuarioContraseña`=%s, usuarioRol=%s, usuarioTurno=%s
                        WHERE usuarioId=%s
                        """,
                        (nombre, correo, pwd_hash, rol, turno, empleado["usuarioId"])
                    )
                else:
                    res = self.db.ejecutar_consulta(
                        """
                        UPDATE usuario
                        SET usuarioNombre=%s, usuarioCorreo=%s, usuarioRol=%s, usuarioTurno=%s
                        WHERE usuarioId=%s
                        """,
                        (nombre, correo, rol, turno, empleado["usuarioId"])
                    )
            else:
                pwd_hash = generar_hash_password(password)
                res = self.db.ejecutar_consulta(
                    """
                    INSERT INTO usuario
                        (usuarioNombre, usuarioCorreo, `usuarioContraseña`, usuarioRol, usuarioTurno, usuarioActivo)
                    VALUES (%s, %s, %s, %s, %s, 1)
                    """,
                    (nombre, correo, pwd_hash, rol, turno)
                )

            if res is None:
                messagebox.showerror("Error", "No se pudo guardar el empleado. Verifica que el correo no esté duplicado.")
                return

            modal.destroy()
            self.actualizar_datos()
            messagebox.showinfo("Empleado guardado", "Los datos del empleado se guardaron correctamente.")

        ctk.CTkButton(
            inner, text="Guardar cambios" if es_edicion else "Guardar empleado",
            fg_color=COLOR_PRIMARY, hover_color="#1e293b", height=40,
            font=("Helvetica", 12, "bold"), command=guardar
        ).pack(fill="x", pady=(22, 0))

    def alternar_estado_empleado(self, empleado):
        nuevo_estado = 0 if int(empleado["usuarioActivo"]) == 1 else 1
        accion = "desactivar" if nuevo_estado == 0 else "activar"
        if not messagebox.askyesno("Confirmar acción", f"¿Seguro que deseas {accion} la cuenta de '{empleado['usuarioNombre']}'?"):
            return

        res = self.db.ejecutar_consulta(
            "UPDATE usuario SET usuarioActivo = %s WHERE usuarioId = %s",
            (nuevo_estado, empleado["usuarioId"])
        )
        if res is None:
            messagebox.showerror("Error", "No se pudo actualizar el estado del empleado.")
            return
        self.actualizar_datos()


# CLASE 5: MainDashboardView. Organiza la navegación y permisos por rol.
class MainDashboardView(VistaBase):
    PERMISOS_POR_ROL = {
        "Administrador": ["Punto de venta", "Corte de caja", "Productos", "Proveedores", "Empleados"],
        "Cajero": ["Punto de venta", "Corte de caja", "Productos"],
        "Almacen": ["Productos", "Proveedores"],
    }

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
            "Corte de caja": CorteCajaView(self.content_area, self.controller),
            "Productos": ProductosView(self.content_area, self.controller),
            "Proveedores": ProveedoresView(self.content_area, self.controller),
            "Empleados": EmpleadosView(self.content_area, self.controller),
        }
        for view in self.vistas.values():
            view.grid(row=0, column=0, sticky="nsew")

        self.nav_buttons = {}
        self.setup_sidebar()

    def setup_sidebar(self):
        title_box = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        title_box.pack(fill="x", pady=(30, 20), padx=20)
        ctk.CTkLabel(title_box, text="Abarrotes Lupita", font=("Helvetica", 18, "bold"), text_color=COLOR_PRIMARY).pack(side="left")
        ctk.CTkFrame(self.sidebar, fg_color="#475569", height=2).pack(fill="x", pady=(0, 16))

        self.menu_container = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.menu_container.pack(fill="x")

        self.btn_actualizar_todo = ctk.CTkButton(
            self.sidebar, text="↻ Actualizar todo", fg_color=COLOR_PRIMARY,
            text_color="white", hover_color="#1e293b", height=38,
            command=self.actualizar_catalogos
        )
        self.btn_actualizar_todo.pack(fill="x", padx=15, pady=(14, 0))

        self.footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.footer.pack(side="bottom", fill="x", padx=20, pady=28)
        ctk.CTkLabel(self.footer, text="Sesión activa", font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        self.lbl_usuario = ctk.CTkLabel(self.footer, text="", font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY)
        self.lbl_usuario.pack(anchor="w")

        self.lbl_rol = ctk.CTkLabel(self.footer, text="", font=("Helvetica", 11, "bold"), text_color="#1e293b")
        self.lbl_rol.pack(anchor="w", pady=(0, 6))

        ctk.CTkButton(
            self.footer,
            text="Cerrar sesión",
            fg_color="transparent",
            text_color="#ef4444",
            hover_color="#cbd5e1",
            anchor="w",
            command=self.cerrar_sesion
        ).pack(fill="x", pady=(6, 0))

    def _construir_menu_por_rol(self, rol):
        for w in self.menu_container.winfo_children():
            w.destroy()
        self.nav_buttons.clear()

        modulos_permitidos = self.PERMISOS_POR_ROL.get(rol, ["Punto de venta", "Corte de caja"])
        for titulo in modulos_permitidos:
            btn = ctk.CTkButton(
                self.menu_container,
                text=f"  {titulo}",
                fg_color="transparent",
                text_color=COLOR_PRIMARY,
                hover_color=COLOR_SIDEBAR_ACTIVE,
                anchor="w",
                height=46,
                font=("Helvetica", 14, "bold"),
                corner_radius=0,
                command=lambda t=titulo: self.cambiar_vista(t)
            )
            btn.pack(fill="x", pady=2)
            self.nav_buttons[titulo] = btn

        return modulos_permitidos[0]

    def actualizar_datos(self):
        user = self.sesion.get_usuario_actual()
        if not user:
            return
        self.lbl_usuario.configure(text=user["nombre"])
        self.lbl_rol.configure(text=f"Rol: {user['rol']}")
        vista_inicial = self._construir_menu_por_rol(user["rol"])
        self.cambiar_vista(vista_inicial)

    def actualizar_catalogos(self):
        user = self.sesion.get_usuario_actual()
        permitidas = self.PERMISOS_POR_ROL.get(user["rol"], []) if user else list(self.vistas.keys())
        errores = []
        for nombre in permitidas:
            vista = self.vistas.get(nombre)
            if vista is None:
                continue
            try:
                vista.actualizar_datos()
            except Exception as error:
                errores.append(f"{nombre}: {error}")
        if errores:
            messagebox.showwarning(
                "Actualización parcial",
                "No se pudieron actualizar todas las pantallas. Revisa la conexión a MySQL.\n\n" + "\n".join(errores)
            )

    def cambiar_vista(self, nombre_vista):
        user = self.sesion.get_usuario_actual()
        permitidas = self.PERMISOS_POR_ROL.get(user["rol"], []) if user else []
        if nombre_vista not in permitidas:
            messagebox.showwarning("Acceso restringido", f"Tu rol ({user['rol']}) no tiene permisos para acceder a '{nombre_vista}'.")
            return

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
        self.title("Sistema de Punto de Venta - Abarrotes Lupita")
        self.geometry("1220x760")
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