#Rodriguez Cardenas Irving Mauricio
#Lopez Garcia Ian Yeshua
#Macias Paredes Jorge Luis
#Piña Aguirre Angel Omar

import os
import hashlib
import hmac
from datetime import datetime
import tkinter as tk
import tkinter.messagebox as messagebox
from tkinter import filedialog
from abc import ABC, abstractmethod
import customtkinter as ctk
import mysql.connector
from mysql.connector import Error

# Intenta cargar bcrypt para hash lento estándar OWASP; si no está instalado, usa PBKDF2-SHA256
try:
    import bcrypt
    TIENE_BCRYPT = True
except ImportError:
    TIENE_BCRYPT = False

# Configuración global de apariencia de CustomTkinter
ctk.set_appearance_mode("Light")

# Paleta de colores institucional (alto contraste y legible para mostrador)
COLOR_BG_PANEL = "#f4f7f9"
COLOR_SIDEBAR = "#aebde6"
COLOR_SIDEBAR_ACTIVE = "#dce4f2"
COLOR_CARD = "#ffffff"
COLOR_PRIMARY = "#1e293b"
COLOR_TEXT_MUTED = "#475569"
COLOR_BORDER = "#cbd5e1"
COLOR_SUCCESS_BG = "#d1fae5"
COLOR_SUCCESS_TXT = "#065f46"
COLOR_WARN_BG = "#fef3c7"
COLOR_WARN_TXT = "#92400e"
COLOR_DANGER_BG = "#fee2e2"
COLOR_DANGER_TXT = "#991b1b"
COLOR_INFO_BG = "#e0f2fe"
COLOR_INFO_TXT = "#0369a1"

# ============================================================================
# LÍMITES OPERATIVOS DEL NEGOCIO (PREVENCIÓN DE ERRORES DE CAPTURA)
# ============================================================================
MAX_CANTIDAD_COMPRA = 10_000        # Máximo 10,000 piezas por producto en una compra
MAX_CANTIDAD_VENTA = 500            # Máximo 500 piezas por producto en una venta
MAX_STOCK_MINIMO = 5_000            # Máximo 5,000 piezas como alerta de stock mínimo
MAX_PRECIO_PRODUCTO = 50_000.00     # Máximo $50,000.00 por artículo
MAX_PAGO_CLIENTE = 100_000.00       # Máximo $100,000.00 en efectivo recibido
MAX_FONDO_CAJA = 50_000.00          # Máximo $50,000.00 de fondo inicial de turno
MAX_EFECTIVO_CONTADO = 500_000.00   # Máximo $500,000.00 en arqueo de cierre
MAX_DIGITOS_CODIGO = 30             # Máximo 30 dígitos en código de barras
MAX_DIGITOS_TELEFONO = 15           # Máximo 15 dígitos en teléfono de proveedor


# ============================================================================
# GESTOR DE ACCESIBILIDAD (ESCALADO MANUAL DE TAMAÑO DE LETRA)
# ============================================================================
class AccesibilidadManager:
    """
    Permite aumentar o disminuir manualmente el tamaño de letra en toda la
    interfaz para facilitar la lectura a personas de la tercera edad.
    """
    _instancia = None
    ESCALAS_DISPONIBLES = [0.90, 1.00, 1.15, 1.30, 1.45]

    def __new__(cls):
        if cls._instancia is None:
            cls._instancia = super(AccesibilidadManager, cls).__new__(cls)
            cls._instancia.indice_escala = 1  # 1.00 (100% por defecto)
            cls._instancia._observadores = []
        return cls._instancia

    @property
    def escala(self) -> float:
        return self.ESCALAS_DISPONIBLES[self.indice_escala]

    @property
    def porcentaje_texto(self) -> str:
        return f"{int(round(self.escala * 100))}%"

    def registrar_observador(self, callback):
        if callback not in self._observadores:
            self._observadores.append(callback)

    def aumentar_letra(self):
        if self.indice_escala < len(self.ESCALAS_DISPONIBLES) - 1:
            self.indice_escala += 1
            self._notificar()

    def disminuir_letra(self):
        if self.indice_escala > 0:
            self.indice_escala -= 1
            self._notificar()

    def restablecer_letra(self):
        self.indice_escala = 1
        self._notificar()

    def _notificar(self):
        for cb in list(self._observadores):
            try:
                cb()
            except Exception:
                pass

    def aplicar_a_widget(self, widget):
        """Recorre recursivamente los widgets y escala sus fuentes y alturas base."""
        if widget is None:
            return
        try:
            if not widget.winfo_exists():
                return
        except Exception:
            return

        factor = self.escala

        # Escalar fuente si el widget la soporta
        try:
            fuente_actual = widget.cget("font")
            if fuente_actual is not None:
                if not hasattr(widget, "_acc_base_font"):
                    if isinstance(fuente_actual, tuple):
                        familia = fuente_actual[0]
                        tamano = int(fuente_actual[1])
                        peso = fuente_actual[2] if len(fuente_actual) > 2 else "normal"
                        widget._acc_base_font = (familia, tamano, peso)
                    elif hasattr(fuente_actual, "cget"):
                        widget._acc_base_font = (
                            fuente_actual.cget("family"),
                            int(fuente_actual.cget("size")),
                            fuente_actual.cget("weight")
                        )

                if hasattr(widget, "_acc_base_font"):
                    fam, base_sz, peso = widget._acc_base_font
                    nuevo_sz = max(9, int(round(base_sz * factor)))
                    if peso and peso != "normal":
                        widget.configure(font=(fam, nuevo_sz, peso))
                    else:
                        widget.configure(font=(fam, nuevo_sz))
        except Exception:
            pass

        # Escalar altura de controles interactivos para que la letra grande no se recorte
        if isinstance(widget, (ctk.CTkButton, ctk.CTkEntry, ctk.CTkComboBox)):
            try:
                if not hasattr(widget, "_acc_base_height"):
                    h_actual = widget.cget("height")
                    if isinstance(h_actual, (int, float)) and h_actual > 0:
                        widget._acc_base_height = float(h_actual)
                if hasattr(widget, "_acc_base_height"):
                    nueva_h = int(round(widget._acc_base_height * (1.0 + (factor - 1.0) * 0.65)))
                    widget.configure(height=max(24, nueva_h))
            except Exception:
                pass

        for hijo in widget.winfo_children():
            self.aplicar_a_widget(hijo)


def crear_barra_accesibilidad(parent, fg_color="transparent") -> ctk.CTkFrame:
    """Construye un control visual accesible con botones A- y A+ para ajustar el tamaño de letra."""
    acc = AccesibilidadManager()
    barra = ctk.CTkFrame(parent, fg_color=fg_color, corner_radius=8)

    ctk.CTkLabel(
        barra,
        text="Tamaño letra:",
        font=("Helvetica", 12, "bold"),
        text_color=COLOR_PRIMARY
    ).pack(side="left", padx=(6, 6), pady=4)

    btn_menos = ctk.CTkButton(
        barra,
        text="A-",
        width=38,
        height=30,
        fg_color="#e2e8f0",
        hover_color="#cbd5e1",
        text_color=COLOR_PRIMARY,
        font=("Helvetica", 12, "bold"),
        command=acc.disminuir_letra
    )
    btn_menos.pack(side="left", padx=2, pady=4)

    lbl_porcentaje = ctk.CTkLabel(
        barra,
        text=acc.porcentaje_texto,
        width=48,
        font=("Helvetica", 12, "bold"),
        text_color=COLOR_PRIMARY
    )
    lbl_porcentaje.pack(side="left", padx=4, pady=4)

    btn_mas = ctk.CTkButton(
        barra,
        text="A+",
        width=38,
        height=30,
        fg_color=COLOR_PRIMARY,
        hover_color="#0f172a",
        text_color="white",
        font=("Helvetica", 12, "bold"),
        command=acc.aumentar_letra
    )
    btn_mas.pack(side="left", padx=(2, 6), pady=4)

    def actualizar_etiqueta():
        if lbl_porcentaje.winfo_exists():
            lbl_porcentaje.configure(text=acc.porcentaje_texto)

    acc.registrar_observador(actualizar_etiqueta)
    return barra


# ============================================================================
# UTILIDADES DE VALIDACIÓN NUMÉRICA Y COMAS AUTOMÁTICAS
# ============================================================================
def limpiar_numero_str(texto: str) -> str:
    """Elimina comas de miles y espacios de una cadena numérica."""
    return str(texto or "").replace(",", "").strip()


def formatear_con_comas_str(texto: str, permitir_decimales: bool = True) -> str:
    """
    Convierte una cadena numérica cruda en formato con comas de miles.
    Ejemplo: '2000' -> '2,000' | '12500.5' -> '12,500.5'
    """
    limpio = limpiar_numero_str(texto)
    if not limpio:
        return ""

    if permitir_decimales and "." in limpio:
        parte_ent, parte_dec = limpio.split(".", 1)
        entero_formateado = f"{int(parte_ent):,}" if parte_ent else "0"
        return f"{entero_formateado}.{parte_dec}"

    return f"{int(limpio):,}"


def parsear_flotante(texto: str) -> float:
    """Convierte un texto con comas (ej. '2,500.50') a float."""
    limpio = limpiar_numero_str(texto)
    if not limpio or limpio == ".":
        raise ValueError("Número vacío o inválido.")
    return float(limpio)


def parsear_entero(texto: str) -> int:
    """Convierte un texto con comas (ej. '2,000') a int."""
    limpio = limpiar_numero_str(texto)
    if not limpio or "." in limpio:
        raise ValueError("Entero vacío o inválido.")
    return int(limpio)


def configurar_entrada_numerica(
    entry: ctk.CTkEntry,
    permitir_decimales: bool = True,
    max_valor: float | None = None,
    con_comas: bool = True,
    max_digitos: int | None = None,
    callback_cambio=None
):
    """
    Configura un CTkEntry para que:
      1. Solo acepte caracteres numéricos (0-9 y '.' si permitir_decimales=True).
      2. Formatee automáticamente con comas de miles al escribir (ej. 2000 -> 2,000).
      3. Impida superar el límite máximo establecido (max_valor o max_digitos).
    """
    var = tk.StringVar()
    entry.configure(textvariable=var)
    estado = {"actualizando": False, "ultimo_valido": ""}

    def _contar_crudos(cadena: str, hasta_pos: int) -> int:
        cuenta = 0
        for ch in cadena[:hasta_pos]:
            if ch.isdigit() or (permitir_decimales and ch == "."):
                cuenta += 1
        return cuenta

    def _indice_desde_crudos(cadena: str, objetivo_crudos: int) -> int:
        if objetivo_crudos <= 0:
            return 0
        cuenta = 0
        for idx, ch in enumerate(cadena):
            if ch.isdigit() or (permitir_decimales and ch == "."):
                cuenta += 1
                if cuenta == objetivo_crudos:
                    return idx + 1
        return len(cadena)

    def _on_write(*_):
        if estado["actualizando"]:
            return
        estado["actualizando"] = True
        try:
            texto_actual = var.get()
            if texto_actual == "":
                estado["ultimo_valido"] = ""
                if callback_cambio:
                    callback_cambio()
                return

            try:
                pos_cursor = entry.index("insert")
            except Exception:
                pos_cursor = len(texto_actual)

            crudos_antes_cursor = _contar_crudos(texto_actual, pos_cursor)

            # Filtrar estrictamente caracteres permitidos
            filtrados = []
            punto_usado = False
            for ch in texto_actual:
                if ch.isdigit():
                    filtrados.append(ch)
                elif permitir_decimales and ch == "." and not punto_usado:
                    filtrados.append(".")
                    punto_usado = True

            crudo = "".join(filtrados)
            if not crudo:
                var.set("")
                estado["ultimo_valido"] = ""
                if callback_cambio:
                    callback_cambio()
                return

            # Normalizar parte entera y parte decimal (máximo 2 decimales)
            if permitir_decimales and "." in crudo:
                ent_str, dec_str = crudo.split(".", 1)
                dec_str = dec_str[:2]
                ent_str = str(int(ent_str)) if ent_str else "0"
                crudo_norm = f"{ent_str}.{dec_str}"
            else:
                ent_str = str(int(crudo)) if con_comas else crudo
                dec_str = None
                crudo_norm = ent_str

            # Verificar límite de dígitos (para códigos de barras / teléfonos)
            if max_digitos is not None and len(crudo_norm.replace(".", "")) > max_digitos:
                var.set(estado["ultimo_valido"])
                entry.after_idle(lambda: entry.icursor("end"))
                return

            # Verificar límite numérico máximo
            if max_valor is not None:
                try:
                    val_num = float(crudo_norm)
                    if val_num > max_valor:
                        var.set(estado["ultimo_valido"])
                        entry.after_idle(lambda: entry.icursor("end"))
                        return
                except ValueError:
                    var.set(estado["ultimo_valido"])
                    return

            # Aplicar comas de miles si corresponde
            if con_comas:
                ent_fmt = f"{int(ent_str):,}"
                formateado = f"{ent_fmt}.{dec_str}" if dec_str is not None else ent_fmt
            else:
                formateado = crudo_norm

            estado["ultimo_valido"] = formateado
            if formateado != texto_actual:
                var.set(formateado)
                nueva_pos = _indice_desde_crudos(formateado, crudos_antes_cursor)
                entry.after_idle(lambda p=nueva_pos: entry.icursor(p))

            if callback_cambio:
                callback_cambio()
        finally:
            estado["actualizando"] = False

    var.trace_add("write", _on_write)
    return var


# ============================================================================
# UTILIDADES DE SEGURIDAD (CIFRADO DE CONTRASEÑAS)
# ============================================================================
def generar_hash_password(password: str) -> str:
    """Genera un hash criptográfico seguro con sal aleatoria para guardar en MySQL."""
    password_bytes = password.encode("utf-8")
    if TIENE_BCRYPT:
        return bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12)).decode("utf-8")
    salt = os.urandom(16).hex()
    iteraciones = 260000
    dk = hashlib.pbkdf2_hmac("sha256", password_bytes, bytes.fromhex(salt), iteraciones).hex()
    return f"pbkdf2_sha256${iteraciones}${salt}${dk}"


def verificar_password(password: str, almacenada: str) -> tuple[bool, bool]:
    """
    Verifica la contraseña ingresada contra el valor guardado en la base de datos.
    Retorna (es_valida, requiere_rehash).
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

    if hmac.compare_digest(password, almacenada):
        return True, True
    return False, False


# ============================================================================
# CLASE 1: DatabaseHelper (Singleton de Conexión, Migración y Transacciones ACID)
# ============================================================================
class DatabaseHelper:
    """
    Centraliza el acceso a MySQL (XAMPP) usando una instancia compartida para evitar
    fugas de conexiones y garantiza integridad ACID en ventas, compras y cortes.
    """
    _instancia = None

    def __new__(cls):
        if cls._instancia is None:
            cls._instancia = super(DatabaseHelper, cls).__new__(cls)
            cls._instancia.__host = "localhost"
            cls._instancia.__ports = [3306, 3003]
            cls._instancia.__user = "root"
            cls._instancia.__password = ""
            cls._instancia.__database = "abarrotes"
            cls._instancia.__connection = None
        return cls._instancia

    def conectar(self) -> bool:
        if self.__connection and self.__connection.is_connected():
            return True
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

    def ejecutar_consulta(self, query: str, parametros=None, fetch: bool = False):
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

    def verificar_y_migrar_esquema(self):
        if not self.conectar():
            return False

        columnas_requeridas = [
            ("venta", "ventaMontoRecibido", "DECIMAL(10,2) NOT NULL DEFAULT 0.00 AFTER `ventaTotal`"),
            ("venta", "ventaCambio", "DECIMAL(10,2) NOT NULL DEFAULT 0.00 AFTER `ventaMontoRecibido`"),
            ("venta", "ventaEstado", "ENUM('Completada','Cancelada') NOT NULL DEFAULT 'Completada' AFTER `ventaCambio`"),
            ("compra", "compraCorteId", "INT DEFAULT NULL AFTER `compraUsuarioId`"),
            ("compra", "compraMetodoPago", "ENUM('Efectivo Caja','Transferencia / Externo') NOT NULL DEFAULT 'Efectivo Caja' AFTER `compraCorteId`"),
            ("compra", "compraNotas", "VARCHAR(255) DEFAULT NULL AFTER `compraTotal`"),
            ("detalle_compra", "detalleCompraSubtotal", "DECIMAL(10,2) NOT NULL DEFAULT 0.00 AFTER `detalleCompraCostoUnitario`"),
            ("corte", "corteVentasEfectivo", "DECIMAL(10,2) DEFAULT 0.00 AFTER `corteFondoInicial`"),
            ("corte", "corteVentasTarjeta", "DECIMAL(10,2) DEFAULT 0.00 AFTER `corteVentasEfectivo`"),
            ("corte", "corteComprasEfectivo", "DECIMAL(10,2) DEFAULT 0.00 AFTER `corteVentasTarjeta`"),
            ("corte", "corteObservaciones", "VARCHAR(255) DEFAULT NULL AFTER `corteEstado`"),
        ]

        for tabla, columna, definicion in columnas_requeridas:
            existe = self.ejecutar_consulta(
                """
                SELECT COUNT(*) AS total
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
                """,
                (self.__database, tabla, columna),
                fetch=True
            )
            if existe and int(existe[0]["total"]) == 0:
                self.ejecutar_consulta(f"ALTER TABLE `{tabla}` ADD COLUMN `{columna}` {definicion}")
        return True

    def inicializar_catalogos(self) -> bool:
        if not self.conectar():
            return False

        self.verificar_y_migrar_esquema()

        if not self.ejecutar_consulta("SELECT proveedorId FROM proveedor LIMIT 1", fetch=True):
            self.ejecutar_consulta(
                "INSERT INTO proveedor (proveedorNombreEmpresa, proveedorTelefono) VALUES (%s, %s)",
                ("Proveedor General", "0000000000")
            )

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

    def obtener_estado_corte_usuario(self, id_usuario: int) -> dict:
        res = self.ejecutar_consulta(
            """
            SELECT c.corteId, c.corteUsuarioId, c.corteFechaApertura, c.corteFondoInicial,
                   u.usuarioNombre,
                   (DATE(c.corteFechaApertura) = CURDATE()) AS es_hoy
            FROM corte c
            JOIN usuario u ON u.usuarioId = c.corteUsuarioId
            WHERE c.corteUsuarioId = %s AND c.corteEstado = 1
            ORDER BY c.corteId DESC LIMIT 1
            """,
            (id_usuario,),
            fetch=True
        )
        if not res:
            return {"estado": "CERRADO", "corte": None}

        corte = res[0]
        if int(corte["es_hoy"]) == 1:
            return {"estado": "ABIERTO_HOY", "corte": corte}
        return {"estado": "REZAGADO", "corte": corte}

    def calcular_balance_corte(self, corte_id: int) -> dict:
        corte_res = self.ejecutar_consulta(
            "SELECT corteFondoInicial FROM corte WHERE corteId = %s",
            (corte_id,),
            fetch=True
        )
        fondo_inicial = float(corte_res[0]["corteFondoInicial"]) if corte_res else 0.0

        ventas_res = self.ejecutar_consulta(
            """
            SELECT
                COUNT(*) AS num_ventas,
                COALESCE(SUM(CASE WHEN ventaMetodoPago = 'Efectivo' THEN ventaTotal ELSE 0 END), 0) AS ventas_efectivo,
                COALESCE(SUM(CASE WHEN ventaMetodoPago = 'Tarjeta' THEN ventaTotal ELSE 0 END), 0) AS ventas_tarjeta
            FROM venta
            WHERE ventaCorteId = %s AND ventaEstado = 'Completada'
            """,
            (corte_id,),
            fetch=True
        )
        v_datos = ventas_res[0] if ventas_res else {"num_ventas": 0, "ventas_efectivo": 0, "ventas_tarjeta": 0}
        ventas_efectivo = float(v_datos["ventas_efectivo"])
        ventas_tarjeta = float(v_datos["ventas_tarjeta"])
        num_ventas = int(v_datos["num_ventas"])

        compras_res = self.ejecutar_consulta(
            """
            SELECT
                COUNT(*) AS num_compras_caja,
                COALESCE(SUM(compraTotal), 0) AS compras_efectivo
            FROM compra
            WHERE compraCorteId = %s AND compraMetodoPago = 'Efectivo Caja'
            """,
            (corte_id,),
            fetch=True
        )
        c_datos = compras_res[0] if compras_res else {"num_compras_caja": 0, "compras_efectivo": 0}
        compras_efectivo = float(c_datos["compras_efectivo"])
        num_compras_caja = int(c_datos["num_compras_caja"])

        efectivo_esperado = round(fondo_inicial + ventas_efectivo - compras_efectivo, 2)

        return {
            "fondo_inicial": round(fondo_inicial, 2),
            "ventas_efectivo": round(ventas_efectivo, 2),
            "ventas_tarjeta": round(ventas_tarjeta, 2),
            "compras_efectivo": round(compras_efectivo, 2),
            "efectivo_esperado": efectivo_esperado,
            "num_ventas": num_ventas,
            "num_compras_caja": num_compras_caja,
        }

    def registrar_venta_transaccion(
        self,
        id_usuario: int,
        id_corte: int,
        metodo_pago: str,
        total: float,
        monto_recibido: float,
        cambio: float,
        items_carrito: dict
    ):
        """
        Registra una venta completa dentro de una transacción ACID y anota la
        SALIDA en la bitácora movimiento_inventario.
        """
        if not self.conectar():
            return None, "No hay conexión con la base de datos."

        cursor = self.__connection.cursor(dictionary=True)
        try:
            self.__connection.start_transaction()

            cursor.execute(
                """
                SELECT corteId, (DATE(corteFechaApertura) = CURDATE()) AS es_hoy
                FROM corte
                WHERE corteId = %s AND corteEstado = 1
                FOR UPDATE
                """,
                (id_corte,)
            )
            corte_fila = cursor.fetchone()
            if not corte_fila:
                self.__connection.rollback()
                return None, "El turno de caja ya fue cerrado."
            if int(corte_fila["es_hoy"]) != 1:
                self.__connection.rollback()
                return None, "El corte abierto pertenece a un día anterior. Ciérralo antes de registrar nuevas ventas."

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
                    return None, f"Stock insuficiente para '{fila['productoNombre']}' (disponible: {fila['productoStockActual']:,})."

            cursor.execute(
                """
                INSERT INTO venta
                    (ventaFecha, ventaUsuarioId, ventaCorteId, ventaMetodoPago,
                     ventaTotal, ventaMontoRecibido, ventaCambio, ventaEstado)
                VALUES (NOW(), %s, %s, %s, %s, %s, %s, 'Completada')
                """,
                (id_usuario, id_corte, metodo_pago, total, monto_recibido, cambio)
            )
            id_venta = cursor.lastrowid

            for id_p, item in items_carrito.items():
                subtotal = round(item["cantidad"] * item["precio"], 2)
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
            return None, f"Error SQL al procesar la venta: {e}"
        finally:
            cursor.close()

    def registrar_compra_transaccion(
        self,
        id_usuario: int,
        id_proveedor: int,
        id_corte: int | None,
        metodo_pago: str,
        total_compra: float,
        notas: str,
        items_compra: dict
    ):
        """
        Registra una compra/entrega de proveedor dentro de una transacción ACID y
        registra la ENTRADA en movimiento_inventario.
        """
        if not self.conectar():
            return None, "No hay conexión con la base de datos."

        if metodo_pago == "Efectivo Caja":
            if not id_corte:
                return None, "Para pagar al proveedor con efectivo de caja debes abrir tu turno de hoy primero."
            balance = self.calcular_balance_corte(id_corte)
            if balance["efectivo_esperado"] + 0.005 < total_compra:
                return None, (
                    f"Efectivo insuficiente en caja.\n"
                    f"Disponible en cajón: ${balance['efectivo_esperado']:,.2f}\n"
                    f"Total a pagar al proveedor: ${total_compra:,.2f}"
                )

        cursor = self.__connection.cursor(dictionary=True)
        try:
            self.__connection.start_transaction()

            cursor.execute(
                """
                INSERT INTO compra
                    (compraFecha, compraProveedorId, compraUsuarioId, compraCorteId,
                     compraMetodoPago, compraTotal, compraNotas)
                VALUES (NOW(), %s, %s, %s, %s, %s, %s)
                """,
                (
                    id_proveedor,
                    id_usuario,
                    id_corte if metodo_pago == "Efectivo Caja" else None,
                    metodo_pago,
                    total_compra,
                    notas.strip() if notas else None
                )
            )
            id_compra = cursor.lastrowid

            for id_p, item in items_compra.items():
                cant = int(item["cantidad"])
                costo = float(item["costo"])
                subtotal = round(cant * costo, 2)

                cursor.execute(
                    """
                    INSERT INTO detalle_compra
                        (detalleCompraCompraId, detalleCompraProductoId, detalleCompraCantidad,
                         detalleCompraCostoUnitario, detalleCompraSubtotal)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (id_compra, id_p, cant, costo, subtotal)
                )
                cursor.execute(
                    """
                    UPDATE producto
                    SET productoStockActual = productoStockActual + %s,
                        productoPrecioCompra = %s
                    WHERE productoId = %s
                    """,
                    (cant, costo, id_p)
                )
                cursor.execute(
                    """
                    INSERT INTO movimiento_inventario
                        (movimientoInventarioProductoId, movimientoInventarioTipo, movimientoInventarioCantidad,
                         movimientoInventarioFecha, movimientoInventarioUsuarioId, movimientoInventarioReferencia)
                    VALUES (%s, 'ENTRADA', %s, NOW(), %s, %s)
                    """,
                    (id_p, cant, id_usuario, f"compra #{id_compra}")
                )

            self.__connection.commit()
            return id_compra, None
        except Error as e:
            self.__connection.rollback()
            return None, f"Error SQL al registrar la compra: {e}"
        finally:
            cursor.close()


# ============================================================================
# CLASE 2: SesionUsuario (Singleton de Sesión y Validación de Permisos)
# ============================================================================
class SesionUsuario:
    _instancia = None

    def __new__(cls):
        if cls._instancia is None:
            cls._instancia = super(SesionUsuario, cls).__new__(cls)
            cls._instancia.__usuario_actual = None
        return cls._instancia

    def iniciar_sesion(self, id_usuario, nombre, rol, correo="", turno=None):
        if id_usuario is None:
            self.__usuario_actual = None
        else:
            self.__usuario_actual = {
                "id": id_usuario,
                "nombre": nombre,
                "rol": rol,
                "correo": correo,
                "turno": turno
            }

    def get_usuario_actual(self):
        return self.__usuario_actual

    def es_admin(self) -> bool:
        return bool(self.__usuario_actual and self.__usuario_actual.get("rol") == "Administrador")

    def cerrar_sesion(self):
        self.__usuario_actual = None


# ============================================================================
# CLASE 3: Producto (Modelo de Dominio con Encapsulación y Validaciones)
# ============================================================================
class Producto:
    def __init__(self, idproducto, codigobarras, nombre, idproveedor,
                 preciocompra, precioventa, stockactual=0, stockminimo=0):
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
        if not valor.isdigit():
            raise ValueError("El código de barras debe contener únicamente números.")
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
        limpio = limpiar_numero_str(valor)
        valor_f = 0.0 if limpio == "" else float(limpio)
        if valor_f < 0 or valor_f > MAX_PRECIO_PRODUCTO:
            raise ValueError(f"El costo de compra debe estar entre $0.00 y ${MAX_PRECIO_PRODUCTO:,.2f}.")
        self.__preciocompra = valor_f

    def get_precioventa(self):
        return self.__precioventa

    def set_precioventa(self, valor):
        limpio = limpiar_numero_str(valor)
        valor_f = float(limpio)
        if valor_f <= 0 or valor_f > MAX_PRECIO_PRODUCTO:
            raise ValueError(f"El precio de venta debe ser mayor a $0.00 y máximo ${MAX_PRECIO_PRODUCTO:,.2f}.")
        self.__precioventa = valor_f

    def get_stockactual(self):
        return self.__stockactual

    def set_stockactual(self, valor):
        valor_i = int(limpiar_numero_str(valor))
        if valor_i < 0:
            raise ValueError("El stock no puede ser negativo.")
        self.__stockactual = valor_i

    def get_stockminimo(self):
        return self.__stockminimo

    def set_stockminimo(self, valor):
        limpio = limpiar_numero_str(valor)
        valor_i = 0 if limpio == "" else int(limpio)
        if valor_i < 0 or valor_i > MAX_STOCK_MINIMO:
            raise ValueError(f"El stock mínimo debe estar entre 0 y {MAX_STOCK_MINIMO:,} piezas.")
        self.__stockminimo = valor_i

    def to_dict(self) -> dict:
        return {
            "productoId": self.get_idproducto(),
            "productoCodigoBarras": self.get_codigobarras(),
            "productoNombre": self.get_nombre(),
            "productoProveedorId": self.get_idproveedor(),
            "productoPrecioCompra": self.get_preciocompra(),
            "productoPrecioVenta": self.get_precioventa(),
            "productoStockActual": self.get_stockactual(),
            "productoStockMinimo": self.get_stockminimo(),
        }


# ============================================================================
# UTILIDAD DE VISUALIZACIÓN Y EXPORTACIÓN DE TICKETS (VENTAS Y COMPRAS)
# ============================================================================
def mostrar_modal_ticket(parent, titulo_ventana: str, texto_ticket: str, nombre_archivo_sugerido: str):
    acc = AccesibilidadManager()
    factor_ventana = min(acc.escala, 1.25)

    modal = ctk.CTkToplevel(parent)
    modal.title(titulo_ventana)
    modal.geometry(f"{int(470 * factor_ventana)}x{int(580 * factor_ventana)}")
    modal.grab_set()

    inner = ctk.CTkFrame(modal, fg_color=COLOR_BG_PANEL)
    inner.pack(fill="both", expand=True, padx=20, pady=20)

    ctk.CTkLabel(inner, text=titulo_ventana, font=("Helvetica", 16, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0, 10))

    textbox = ctk.CTkTextbox(
        inner,
        font=("Courier New", 12),
        fg_color="#ffffff",
        text_color="#0f172a",
        border_width=1,
        border_color=COLOR_BORDER
    )
    textbox.pack(fill="both", expand=True, pady=(0, 14))
    textbox.insert("1.0", texto_ticket)
    textbox.configure(state="disabled")

    btn_row = ctk.CTkFrame(inner, fg_color="transparent")
    btn_row.pack(fill="x")

    def exportar_txt():
        ruta = filedialog.asksaveasfilename(
            parent=modal,
            defaultextension=".txt",
            initialfile=nombre_archivo_sugerido,
            filetypes=[("Archivo de texto (Ticket)", "*.txt")]
        )
        if ruta:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(texto_ticket)
            messagebox.showinfo("Ticket guardado", f"El ticket se guardó correctamente en:\n{ruta}", parent=modal)

    ctk.CTkButton(
        btn_row, text="Guardar Ticket (.txt)", fg_color=COLOR_PRIMARY,
        hover_color="#0f172a", height=40, font=("Helvetica", 12, "bold"), command=exportar_txt
    ).pack(side="left", expand=True, fill="x", padx=(0, 6))

    ctk.CTkButton(
        btn_row, text="Cerrar", fg_color="#e2e8f0", text_color=COLOR_PRIMARY,
        hover_color="#cbd5e1", height=40, font=("Helvetica", 12, "bold"), command=modal.destroy
    ).pack(side="right", expand=True, fill="x", padx=(6, 0))

    acc.aplicar_a_widget(modal)


# ============================================================================
# CLASE 4: VistaBase (Clase Abstracta de Interfaz)
# ============================================================================
class VistaBase(ctk.CTkFrame, ABC):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=COLOR_BG_PANEL)
        self.controller = controller
        self.db = DatabaseHelper()
        self.sesion = SesionUsuario()
        self.acc = AccesibilidadManager()
        self.construir_interfaz()
        self.acc.aplicar_a_widget(self)

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


# ============================================================================
# VISTA 1: LoginView (Autenticación Segura + Control de Tamaño de Letra)
# ============================================================================
class LoginView(VistaBase):
    def construir_interfaz(self):
        if not self.db.inicializar_catalogos():
            messagebox.showerror(
                "Error crítico",
                "No se pudo conectar a MySQL. Enciende XAMPP (puerto 3306 o 3003) e importa 'abarrotes.sql'."
            )

        # Barra superior de accesibilidad para que el usuario pueda agrandar la letra antes de entrar
        top_acc = ctk.CTkFrame(self, fg_color="transparent")
        top_acc.pack(fill="x", padx=24, pady=16)
        barra_acc = crear_barra_accesibilidad(top_acc, fg_color=COLOR_CARD)
        barra_acc.pack(side="right")

        center_frame = ctk.CTkFrame(self, fg_color="transparent")
        center_frame.place(relx=0.5, rely=0.52, anchor="center")

        logo_box = ctk.CTkFrame(center_frame, fg_color="#e2e8f0", width=60, height=60, corner_radius=12)
        logo_box.pack(pady=(0, 12))
        logo_box.pack_propagate(False)
        ctk.CTkLabel(logo_box, text="A", font=("Helvetica", 26, "bold"), text_color=COLOR_PRIMARY).pack(expand=True)

        ctk.CTkLabel(
            center_frame,
            text="Abarrotes Lupita — Punto de Venta",
            font=("Helvetica", 20, "bold"),
            text_color=COLOR_PRIMARY
        ).pack(pady=(0, 18))

        card = ctk.CTkFrame(
            center_frame,
            fg_color=COLOR_CARD,
            corner_radius=16,
            border_width=1,
            border_color=COLOR_BORDER
        )
        card.pack()

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=36, pady=30)

        ctk.CTkLabel(inner, text="Iniciar sesión", font=("Helvetica", 18, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(inner, text="Ingresa tus credenciales de acceso.", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).pack(anchor="w", pady=(0, 18))

        ctk.CTkLabel(inner, text="Correo o Usuario", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0, 3))
        self.user = ctk.CTkEntry(inner, placeholder_text="ej. Juan o cajero@abarrotes.com", width=330, height=40, fg_color="#f8fafc", border_color=COLOR_BORDER)
        self.user.pack(fill="x", pady=(0, 14))
        self.user.bind("<Return>", lambda e: self.pwd.focus())

        ctk.CTkLabel(inner, text="Contraseña", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0, 3))
        self.pwd = ctk.CTkEntry(inner, placeholder_text="********", show="*", width=330, height=40, fg_color="#f8fafc", border_color=COLOR_BORDER)
        self.pwd.pack(fill="x", pady=(0, 22))
        self.pwd.bind("<Return>", lambda e: self.autenticar())

        ctk.CTkButton(
            inner,
            text="Ingresar al sistema",
            fg_color=COLOR_PRIMARY,
            hover_color="#0f172a",
            height=42,
            font=("Helvetica", 13, "bold"),
            command=self.autenticar
        ).pack(fill="x")

    def autenticar(self):
        correo_usuario = self.user.get().strip()
        password = self.pwd.get()

        if not correo_usuario or not password:
            messagebox.showwarning("Campos vacíos", "Ingresa tu usuario o correo y tu contraseña.")
            return

        res = self.db.ejecutar_consulta(
            """
            SELECT usuarioId, usuarioNombre, usuarioCorreo, `usuarioContraseña`,
                   usuarioRol, usuarioTurno, usuarioActivo
            FROM usuario
            WHERE LOWER(usuarioCorreo) = LOWER(%s) OR LOWER(usuarioNombre) = LOWER(%s)
            LIMIT 1
            """,
            (correo_usuario, correo_usuario),
            fetch=True
        )

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
        self.acc.aplicar_a_widget(self)


# ============================================================================
# VISTA 2: PuntoDeVentaView (Escáner, Método Protegido, Comas Automáticas)
# ============================================================================
class PuntoDeVentaView(VistaBase):
    def construir_interfaz(self):
        self.carrito = {}
        self.productos_cache = []
        self.total_venta = 0.0

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        left_pane = ctk.CTkFrame(self, fg_color="transparent")
        left_pane.grid(row=0, column=0, sticky="nsew", padx=28, pady=24)

        header = ctk.CTkFrame(left_pane, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        encabezado_textos = ctk.CTkFrame(header, fg_color="transparent")
        encabezado_textos.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(encabezado_textos, text="Punto de Venta", font=("Helvetica", 24, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(encabezado_textos, text="Escanea el código de barras o haz clic en un producto para agregarlo.", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        ctk.CTkButton(
            header, text="↻ Actualizar", width=115, height=36,
            fg_color=COLOR_PRIMARY, font=("Helvetica", 12, "bold"),
            command=self.refrescar_vistas_relacionadas
        ).pack(side="right")

        self.banner_turno = ctk.CTkFrame(left_pane, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=8)
        self.banner_turno.pack(fill="x", pady=(0, 12))
        self.lbl_estado_caja = ctk.CTkLabel(
            self.banner_turno,
            text="Verificando estado de caja...",
            font=("Helvetica", 12, "bold"),
            text_color=COLOR_TEXT_MUTED
        )
        self.lbl_estado_caja.pack(side="left", padx=14, pady=9)

        self.btn_ir_corte = ctk.CTkButton(
            self.banner_turno,
            text="Ir a Corte de Caja",
            width=135,
            height=30,
            fg_color=COLOR_PRIMARY,
            font=("Helvetica", 11, "bold"),
            command=self._ir_a_corte
        )

        # Barra de búsqueda (permite nombre o código de barras)
        search_bar = ctk.CTkFrame(left_pane, fg_color="transparent")
        search_bar.pack(fill="x", pady=(0, 10))
        self.entry_buscar = ctk.CTkEntry(
            search_bar,
            placeholder_text="Buscar por nombre o escanear código de barras + Enter...",
            height=40,
            fg_color="#ffffff",
            border_color=COLOR_BORDER,
            font=("Helvetica", 12)
        )
        self.entry_buscar.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry_buscar.bind("<KeyRelease>", lambda e: self._renderizar_catalogo())
        self.entry_buscar.bind("<Return>", self._procesar_escaneo_enter)

        ctk.CTkButton(
            search_bar, text="Limpiar", width=80, height=40,
            fg_color="#e2e8f0", text_color=COLOR_PRIMARY, hover_color="#cbd5e1",
            font=("Helvetica", 12, "bold"),
            command=self._limpiar_busqueda
        ).pack(side="right")

        self.products_grid = ctk.CTkScrollableFrame(left_pane, fg_color="transparent")
        self.products_grid.pack(fill="both", expand=True)

        # Panel derecho: Ticket, Método de pago (solo lectura) y Pago recibido
        right_pane = ctk.CTkFrame(self, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=0)
        right_pane.grid(row=0, column=1, sticky="nsew")

        ctk.CTkLabel(right_pane, text="Ticket de Venta", font=("Helvetica", 18, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", padx=20, pady=(20, 8))

        self.cart_frame = ctk.CTkScrollableFrame(right_pane, fg_color="transparent")
        self.cart_frame.pack(fill="both", expand=True, padx=10)

        bottom_box = ctk.CTkFrame(right_pane, fg_color="transparent")
        bottom_box.pack(side="bottom", fill="x", padx=20, pady=18)

        ctk.CTkFrame(bottom_box, fg_color=COLOR_BORDER, height=2).pack(fill="x", pady=(0, 12))

        total_frame = ctk.CTkFrame(bottom_box, fg_color="transparent")
        total_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(total_frame, text="Total a Pagar:", font=("Helvetica", 15, "bold"), text_color=COLOR_PRIMARY).pack(side="left")
        self.lbl_total = ctk.CTkLabel(total_frame, text="$0.00", font=("Helvetica", 24, "bold"), text_color=COLOR_SUCCESS_TXT)
        self.lbl_total.pack(side="right")

        # Selector de método de pago protegido (state="readonly" para que no se pueda borrar)
        ctk.CTkLabel(bottom_box, text="Método de pago (selecciona una opción)", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0, 4))
        self.combo_metodo = ctk.CTkComboBox(
            bottom_box,
            values=["Efectivo", "Tarjeta"],
            state="readonly",
            fg_color="#f8fafc",
            border_color=COLOR_BORDER,
            height=38,
            font=("Helvetica", 13, "bold"),
            command=self._al_cambiar_metodo_pago
        )
        self.combo_metodo.set("Efectivo")
        self.combo_metodo.pack(fill="x", pady=(0, 10))

        # Sección de pago recibido (solo números + comas automáticas + límite)
        self.panel_efectivo = ctk.CTkFrame(bottom_box, fg_color=COLOR_BG_PANEL, border_width=1, border_color=COLOR_BORDER, corner_radius=8)
        self.panel_efectivo.pack(fill="x", pady=(0, 12))

        pago_row = ctk.CTkFrame(self.panel_efectivo, fg_color="transparent")
        pago_row.pack(fill="x", padx=12, pady=(10, 6))
        ctk.CTkLabel(pago_row, text="Paga con ($):", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(side="left")
        self.entry_pago_con = ctk.CTkEntry(
            pago_row,
            placeholder_text="0.00",
            width=155,
            height=38,
            fg_color="#ffffff",
            border_color=COLOR_BORDER,
            font=("Helvetica", 14, "bold")
        )
        self.entry_pago_con.pack(side="right")
        configurar_entrada_numerica(
            self.entry_pago_con,
            permitir_decimales=True,
            max_valor=MAX_PAGO_CLIENTE,
            con_comas=True,
            callback_cambio=self._recalcular_feria
        )
        self.entry_pago_con.bind("<Return>", lambda e: self.procesar_pago())

        # Botones rápidos de denominación de billetes
        quick_row = ctk.CTkFrame(self.panel_efectivo, fg_color="transparent")
        quick_row.pack(fill="x", padx=12, pady=(0, 8))
        for etiqueta, monto in [("Exacto", None), ("$50", 50), ("$100", 100), ("$200", 200), ("$500", 500)]:
            ctk.CTkButton(
                quick_row,
                text=etiqueta,
                height=30,
                width=54,
                fg_color="#e2e8f0",
                hover_color="#cbd5e1",
                text_color=COLOR_PRIMARY,
                font=("Helvetica", 11, "bold"),
                command=lambda m=monto: self._establecer_pago_rapido(m)
            ).pack(side="left", expand=True, padx=2)

        feria_row = ctk.CTkFrame(self.panel_efectivo, fg_color="transparent")
        feria_row.pack(fill="x", padx=12, pady=(2, 10))
        ctk.CTkLabel(feria_row, text="Cambio (Feria):", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(side="left")
        self.lbl_feria = ctk.CTkLabel(feria_row, text="$0.00", font=("Helvetica", 16, "bold"), text_color=COLOR_TEXT_MUTED)
        self.lbl_feria.pack(side="right")

        self.btn_cobrar = ctk.CTkButton(
            bottom_box,
            text="Cobrar y Generar Ticket",
            fg_color=COLOR_PRIMARY,
            hover_color="#0f172a",
            text_color="white",
            height=46,
            font=("Helvetica", 14, "bold"),
            corner_radius=8,
            command=self.procesar_pago
        )
        self.btn_cobrar.pack(fill="x")

    def _ir_a_corte(self):
        dashboard = getattr(self.controller, "dashboard_view", None)
        if dashboard and "Corte de caja" in dashboard.vistas:
            dashboard.cambiar_vista("Corte de caja")

    def _al_cambiar_metodo_pago(self, metodo: str):
        if metodo == "Efectivo":
            self.panel_efectivo.pack(fill="x", pady=(0, 12), before=self.btn_cobrar)
            self._recalcular_feria()
        else:
            self.panel_efectivo.pack_forget()

    def _establecer_pago_rapido(self, monto):
        valor = self.total_venta if monto is None else float(monto)
        self.entry_pago_con.delete(0, "end")
        self.entry_pago_con.insert(0, f"{valor:,.2f}")
        self._recalcular_feria()

    def _recalcular_feria(self):
        if not hasattr(self, "lbl_feria"):
            return 0.0, False
        if self.combo_metodo.get() != "Efectivo":
            return 0.0, True

        texto = self.entry_pago_con.get().strip()
        if not texto:
            self.lbl_feria.configure(text="Ingresa pago", text_color=COLOR_TEXT_MUTED)
            return 0.0, False

        try:
            pagado = parsear_flotante(texto)
            if pagado < 0:
                raise ValueError
        except ValueError:
            self.lbl_feria.configure(text="Monto inválido", text_color=COLOR_DANGER_TXT)
            return 0.0, False

        dif = round(pagado - self.total_venta, 2)
        if dif < -0.005:
            self.lbl_feria.configure(text=f"Faltan ${abs(dif):,.2f}", text_color=COLOR_DANGER_TXT)
            return dif, False

        self.lbl_feria.configure(text=f"${dif:,.2f}", text_color=COLOR_SUCCESS_TXT)
        return dif, True

    def _limpiar_busqueda(self):
        self.entry_buscar.delete(0, "end")
        self._renderizar_catalogo()
        self.entry_buscar.focus()

    def _procesar_escaneo_enter(self, event=None):
        termino = self.entry_buscar.get().strip().lower()
        if not termino:
            return
        coincidencia_exacta = next(
            (p for p in self.productos_cache if str(p.get("productoCodigoBarras") or "").lower() == termino),
            None
        )
        if coincidencia_exacta:
            self.agregar_al_carrito(coincidencia_exacta)
            self.entry_buscar.delete(0, "end")
            self._renderizar_catalogo()

    def actualizar_datos(self):
        user = self.sesion.get_usuario_actual()
        if not user:
            return

        estado_info = self.db.obtener_estado_corte_usuario(user["id"])
        estado = estado_info["estado"]
        corte = estado_info["corte"]

        if estado == "ABIERTO_HOY":
            bal = self.db.calcular_balance_corte(corte["corteId"])
            self.banner_turno.configure(fg_color=COLOR_SUCCESS_BG, border_color="#a7f3d0")
            self.lbl_estado_caja.configure(
                text=(
                    f"● Turno #{corte['corteId']} (Hoy)  |  Fondo: ${bal['fondo_inicial']:,.2f}  |  "
                    f"Ventas Efec: +${bal['ventas_efectivo']:,.2f}  |  Compras Caja: -${bal['compras_efectivo']:,.2f}  |  "
                    f"Balance Cajón: ${bal['efectivo_esperado']:,.2f}"
                ),
                text_color=COLOR_SUCCESS_TXT
            )
            self.btn_ir_corte.pack_forget()
        elif estado == "REZAGADO":
            self.banner_turno.configure(fg_color=COLOR_DANGER_BG, border_color="#fca5a5")
            self.lbl_estado_caja.configure(
                text=f"⛔ Corte #{corte['corteId']} pendiente del {str(corte['corteFechaApertura'])[:10]}: ciérralo antes de vender hoy.",
                text_color=COLOR_DANGER_TXT
            )
            self.btn_ir_corte.configure(text="Cerrar Corte Anterior", fg_color="#991b1b")
            self.btn_ir_corte.pack(side="right", padx=12, pady=6)
        else:
            self.banner_turno.configure(fg_color=COLOR_WARN_BG, border_color="#fde68a")
            self.lbl_estado_caja.configure(
                text="⚠ Caja cerrada: abre tu turno de hoy antes de registrar ventas.",
                text_color=COLOR_WARN_TXT
            )
            self.btn_ir_corte.configure(text="Abrir Caja Hoy", fg_color=COLOR_PRIMARY)
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

        self.productos_cache = productos

        productos_por_id = {p["productoId"]: p for p in productos}
        for id_p in list(self.carrito.keys()):
            if id_p not in productos_por_id:
                del self.carrito[id_p]
                continue
            actual = productos_por_id[id_p]
            self.carrito[id_p]["nombre"] = actual["productoNombre"]
            self.carrito[id_p]["precio"] = float(actual["productoPrecioVenta"])
            self.carrito[id_p]["stock"] = int(actual["productoStockActual"])
            self.carrito[id_p]["obj"] = actual
            if int(actual["productoStockActual"]) <= 0:
                del self.carrito[id_p]
            elif self.carrito[id_p]["cantidad"] > int(actual["productoStockActual"]):
                self.carrito[id_p]["cantidad"] = int(actual["productoStockActual"])

        self.dibujar_carrito()
        self._renderizar_catalogo()
        self.acc.aplicar_a_widget(self)

    def _renderizar_catalogo(self):
        for w in self.products_grid.winfo_children():
            w.destroy()

        filtro = self.entry_buscar.get().strip().lower() if hasattr(self, "entry_buscar") else ""
        filtrados = [
            p for p in self.productos_cache
            if not filtro
            or filtro in p["productoNombre"].lower()
            or filtro in str(p.get("productoCodigoBarras") or "").lower()
        ]

        if not filtrados:
            ctk.CTkLabel(self.products_grid, text="No se encontraron productos.", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).pack(pady=24)
            self.acc.aplicar_a_widget(self.products_grid)
            return

        factor = self.acc.escala
        card_w = int(175 * (1 + (factor - 1) * 0.5))
        card_h = int(120 * (1 + (factor - 1) * 0.6))

        row, col = 0, 0
        for p in filtrados:
            stock = int(p["productoStockActual"])
            stock_min = int(p.get("productoStockMinimo") or 0)
            borde = "#fca5a5" if stock == 0 else ("#fcd34d" if stock <= stock_min else COLOR_BORDER)

            card = ctk.CTkFrame(
                self.products_grid,
                fg_color=COLOR_CARD,
                border_width=1,
                border_color=borde,
                corner_radius=8,
                width=card_w,
                height=card_h,
                cursor="hand2"
            )
            card.grid(row=row, column=col, padx=7, pady=7)
            card.grid_propagate(False)
            card.bind("<Button-1>", lambda e, prod=p: self.agregar_al_carrito(prod))

            lbl_nom = ctk.CTkLabel(card, text=p["productoNombre"][:18], font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY)
            lbl_nom.pack(anchor="w", padx=12, pady=(10, 0))
            lbl_nom.bind("<Button-1>", lambda e, prod=p: self.agregar_al_carrito(prod))

            lbl_cod = ctk.CTkLabel(card, text=str(p["productoCodigoBarras"] or ""), font=("Helvetica", 10), text_color=COLOR_TEXT_MUTED)
            lbl_cod.pack(anchor="w", padx=12)
            lbl_cod.bind("<Button-1>", lambda e, prod=p: self.agregar_al_carrito(prod))

            bottom = ctk.CTkFrame(card, fg_color="transparent")
            bottom.pack(fill="x", side="bottom", padx=12, pady=10)
            ctk.CTkLabel(bottom, text=f"${float(p['productoPrecioVenta']):,.2f}", font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY).pack(side="left")

            stock_color = COLOR_DANGER_TXT if stock <= 0 else (COLOR_WARN_TXT if stock <= stock_min else COLOR_SUCCESS_TXT)
            ctk.CTkLabel(bottom, text=f"{stock:,} pz", font=("Helvetica", 11, "bold"), text_color=stock_color).pack(side="right")

            col += 1
            if col > 2:
                col = 0
                row += 1

        self.acc.aplicar_a_widget(self.products_grid)

    def agregar_al_carrito(self, p):
        id_p = p["productoId"]
        stock = int(p["productoStockActual"])
        if stock <= 0:
            messagebox.showwarning("Sin stock", f"'{p['productoNombre']}' está agotado.")
            return

        cant_actual = self.carrito[id_p]["cantidad"] if id_p in self.carrito else 0
        if cant_actual >= stock:
            messagebox.showwarning("Límite de stock", f"Solo hay {stock:,} piezas disponibles en inventario.")
            return
        if cant_actual >= MAX_CANTIDAD_VENTA:
            messagebox.showwarning("Límite por venta", f"El máximo permitido por producto en una venta es de {MAX_CANTIDAD_VENTA:,} piezas.")
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
            item_frame.pack(fill="x", pady=4, padx=4)

            top_row = ctk.CTkFrame(item_frame, fg_color="transparent")
            top_row.pack(fill="x", padx=10, pady=(8, 4))
            ctk.CTkLabel(top_row, text=data["nombre"], font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(side="left")
            ctk.CTkButton(
                top_row, text="✕", width=28, height=28, fg_color="transparent",
                hover_color="#fee2e2", text_color="#ef4444", font=("Helvetica", 12, "bold"),
                command=lambda i=id_p: self.eliminar_del_carrito(i)
            ).pack(side="right")

            bot_row = ctk.CTkFrame(item_frame, fg_color="transparent")
            bot_row.pack(fill="x", padx=10, pady=(0, 8))

            ctrl_box = ctk.CTkFrame(bot_row, fg_color="transparent")
            ctrl_box.pack(side="left")
            ctk.CTkButton(ctrl_box, text="-", width=30, height=30, fg_color="#e2e8f0", text_color=COLOR_PRIMARY, font=("Helvetica", 14, "bold"), command=lambda i=id_p: self.restar_del_carrito(i)).pack(side="left", padx=2)
            ctk.CTkLabel(ctrl_box, text=f"{data['cantidad']:,}", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY, width=32).pack(side="left", padx=4)
            ctk.CTkButton(ctrl_box, text="+", width=30, height=30, fg_color="#e2e8f0", text_color=COLOR_PRIMARY, font=("Helvetica", 14, "bold"), command=lambda p=data["obj"]: self.agregar_al_carrito(p)).pack(side="left", padx=2)

            subtotal = round(data["cantidad"] * data["precio"], 2)
            self.total_venta = round(self.total_venta + subtotal, 2)
            ctk.CTkLabel(bot_row, text=f"${data['precio']:,.2f} c/u = ${subtotal:,.2f}", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(side="right")

        self.lbl_total.configure(text=f"${self.total_venta:,.2f}")
        self._recalcular_feria()
        self.acc.aplicar_a_widget(self.cart_frame)

    def procesar_pago(self):
        if not self.carrito:
            messagebox.showwarning("Ticket vacío", "Agrega productos al ticket antes de cobrar.")
            return

        user = self.sesion.get_usuario_actual()
        estado_info = self.db.obtener_estado_corte_usuario(user["id"])

        if estado_info["estado"] == "REZAGADO":
            messagebox.showerror(
                "Corte pendiente de día anterior",
                f"Tienes el Corte #{estado_info['corte']['corteId']} abierto desde el {str(estado_info['corte']['corteFechaApertura'])[:10]}.\n\n"
                "Por control diario debes cerrar ese corte antes de cobrar ventas hoy."
            )
            self._ir_a_corte()
            return

        if estado_info["estado"] != "ABIERTO_HOY":
            if messagebox.askyesno("Caja cerrada", "No tienes un turno abierto hoy. ¿Deseas ir a Corte de Caja para abrir turno?"):
                self._ir_a_corte()
            return

        corte = estado_info["corte"]
        metodo = self.combo_metodo.get()
        if metodo not in ("Efectivo", "Tarjeta"):
            messagebox.showwarning("Método inválido", "Selecciona un método de pago válido (Efectivo o Tarjeta).")
            return

        if metodo == "Efectivo":
            texto_pago = self.entry_pago_con.get().strip()
            try:
                monto_recibido = round(parsear_flotante(texto_pago), 2)
            except ValueError:
                messagebox.showwarning("Pago inválido", "Ingresa con cuánto efectivo está pagando el cliente.")
                self.entry_pago_con.focus()
                return

            if monto_recibido > MAX_PAGO_CLIENTE:
                messagebox.showwarning("Límite excedido", f"El pago recibido no puede superar ${MAX_PAGO_CLIENTE:,.2f}.")
                return

            if monto_recibido + 0.005 < self.total_venta:
                faltante = round(self.total_venta - monto_recibido, 2)
                messagebox.showwarning("Pago insuficiente", f"El monto recibido (${monto_recibido:,.2f}) es menor al total (${self.total_venta:,.2f}).\nFaltan ${faltante:,.2f}.")
                self.entry_pago_con.focus()
                return

            cambio = round(monto_recibido - self.total_venta, 2)
        else:
            monto_recibido = round(self.total_venta, 2)
            cambio = 0.0

        items_ticket = [
            {
                "nombre": d["nombre"],
                "cantidad": d["cantidad"],
                "precio": d["precio"],
                "subtotal": round(d["cantidad"] * d["precio"], 2)
            }
            for d in self.carrito.values()
        ]
        total_ticket = self.total_venta

        id_venta, error_msg = self.db.registrar_venta_transaccion(
            id_usuario=user["id"],
            id_corte=corte["corteId"],
            metodo_pago=metodo,
            total=total_ticket,
            monto_recibido=monto_recibido,
            cambio=cambio,
            items_carrito=self.carrito
        )

        if error_msg:
            messagebox.showerror("No se pudo procesar la venta", error_msg)
            self.actualizar_datos()
            return

        self.carrito.clear()
        self.entry_pago_con.delete(0, "end")
        self.dibujar_carrito()
        self.refrescar_vistas_relacionadas()

        fecha_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lineas = [
            "==========================================",
            "            ABARROTES LUPITA              ",
            "             TICKET DE VENTA              ",
            "==========================================",
            f"Folio Venta : #V-{id_venta:05d}",
            f"Fecha y Hora: {fecha_str}",
            f"Cajero      : {user['nombre']} (Corte #{corte['corteId']})",
            f"Método Pago : {metodo}",
            "------------------------------------------",
            "CANT  DESCRIPCIÓN            IMPORTE",
            "------------------------------------------",
        ]
        for it in items_ticket:
            nom = it["nombre"][:20].ljust(20)
            lineas.append(f"{it['cantidad']:>3}x  {nom}  ${it['subtotal']:>9,.2f}")
            lineas.append(f"      (${it['precio']:,.2f} c/u)")
        lineas.extend([
            "------------------------------------------",
            f"TOTAL A PAGAR :              ${total_ticket:>10,.2f}",
            f"PAGÓ CON      :              ${monto_recibido:>10,.2f}",
            f"CAMBIO (FERIA):              ${cambio:>10,.2f}",
            "==========================================",
            "        ¡Gracias por su compra!           ",
            "==========================================",
        ])
        mostrar_modal_ticket(
            self,
            f"Ticket de Venta #V-{id_venta:05d}",
            "\n".join(lineas),
            f"ticket_venta_{id_venta}.txt"
        )


# ============================================================================
# VISTA 3: CorteCajaView (Fondo Inicial, Balance con Compras, Cierre Diario)
# ============================================================================
class CorteCajaView(VistaBase):
    def construir_interfaz(self):
        self.corte_actual = None
        self.balance_actual = {}

        main_box = ctk.CTkFrame(self, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=32, pady=24)

        header = ctk.CTkFrame(main_box, fg_color="transparent")
        header.pack(fill="x", pady=(0, 14))
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(titles, text="Corte de Caja y Turno Diario", font=("Helvetica", 24, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(titles, text="Cada corte corresponde exclusivamente a un día natural e integra ventas y pagos a proveedores desde caja.", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        ctk.CTkButton(
            header, text="↻ Actualizar", width=115, height=36,
            fg_color=COLOR_PRIMARY, font=("Helvetica", 12, "bold"), command=self.actualizar_datos
        ).pack(side="right")

        self.panel_turno = ctk.CTkFrame(main_box, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=12)
        self.panel_turno.pack(fill="x", pady=(0, 14))

        self.panel_resumen_dia = ctk.CTkFrame(main_box, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=12)

        hist_card = ctk.CTkFrame(main_box, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=12)
        hist_card.pack(fill="both", expand=True)

        hist_header = ctk.CTkFrame(hist_card, fg_color="transparent")
        hist_header.pack(fill="x", padx=20, pady=(14, 8))
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

        estado_info = self.db.obtener_estado_corte_usuario(user["id"])
        self.corte_actual = estado_info["corte"]

        if estado_info["estado"] == "CERRADO":
            self._construir_vista_apertura()
        else:
            es_rezagado = (estado_info["estado"] == "REZAGADO")
            self._construir_vista_cierre(es_rezagado=es_rezagado)

        if self.sesion.es_admin():
            self.panel_resumen_dia.pack(fill="x", pady=(0, 14), before=self.panel_resumen_dia.master.winfo_children()[-1])
            self._construir_resumen_consolidado_dia()
        else:
            self.panel_resumen_dia.pack_forget()

        self._cargar_historial(user)
        self.acc.aplicar_a_widget(self)

    def _construir_vista_apertura(self):
        box = ctk.CTkFrame(self.panel_turno, fg_color="transparent")
        box.pack(fill="x", padx=24, pady=20)

        badge = ctk.CTkFrame(box, fg_color=COLOR_WARN_BG, corner_radius=10)
        badge.pack(anchor="w", pady=(0, 8))
        ctk.CTkLabel(badge, text="● Sin turno abierto hoy", font=("Helvetica", 11, "bold"), text_color=COLOR_WARN_TXT).pack(padx=10, pady=3)

        ctk.CTkLabel(box, text="Abrir turno de caja del día", font=("Helvetica", 17, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(
            box,
            text=f"Ingresa el fondo inicial en el cajón (solo números, máximo ${MAX_FONDO_CAJA:,.2f}).",
            font=("Helvetica", 12),
            text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w", pady=(2, 12))

        form_row = ctk.CTkFrame(box, fg_color="transparent")
        form_row.pack(fill="x")

        ctk.CTkLabel(form_row, text="Fondo inicial ($):", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(side="left", padx=(0, 10))
        self.entry_fondo = ctk.CTkEntry(form_row, placeholder_text="Ej. 500.00", width=190, height=40, fg_color="#f8fafc", border_color=COLOR_BORDER, font=("Helvetica", 13, "bold"))
        self.entry_fondo.pack(side="left", padx=(0, 14))
        configurar_entrada_numerica(
            self.entry_fondo,
            permitir_decimales=True,
            max_valor=MAX_FONDO_CAJA,
            con_comas=True
        )
        self.entry_fondo.bind("<Return>", lambda e: self.abrir_caja())

        ctk.CTkButton(
            form_row,
            text="Iniciar Turno de Hoy",
            fg_color=COLOR_PRIMARY,
            hover_color="#0f172a",
            height=40,
            font=("Helvetica", 12, "bold"),
            command=self.abrir_caja
        ).pack(side="left")

    def abrir_caja(self):
        user = self.sesion.get_usuario_actual()
        estado_previo = self.db.obtener_estado_corte_usuario(user["id"])
        if estado_previo["estado"] != "CERRADO":
            messagebox.showwarning("Turno existente", "Ya tienes un corte abierto. Ciérralo antes de abrir uno nuevo.")
            self.actualizar_datos()
            return

        texto = self.entry_fondo.get().strip()
        try:
            fondo = round(parsear_flotante(texto), 2)
            if fondo < 0 or fondo > MAX_FONDO_CAJA:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Dato inválido", f"Ingresa un monto numérico válido entre $0.00 y ${MAX_FONDO_CAJA:,.2f} para el fondo inicial.")
            return

        corte_id = self.db.ejecutar_consulta(
            "INSERT INTO corte (corteUsuarioId, corteFechaApertura, corteFondoInicial, corteEstado) VALUES (%s, NOW(), %s, 1)",
            (user["id"], fondo)
        )
        if corte_id is None:
            messagebox.showerror("Error", "No se pudo registrar la apertura de caja.")
            return

        messagebox.showinfo("Caja abierta", f"Turno #{corte_id} iniciado hoy con fondo inicial de ${fondo:,.2f}.")
        self.refrescar_vistas_relacionadas()

    def _construir_vista_cierre(self, es_rezagado: bool = False):
        corte_id = self.corte_actual["corteId"]
        self.balance_actual = self.db.calcular_balance_corte(corte_id)

        box = ctk.CTkFrame(self.panel_turno, fg_color="transparent")
        box.pack(fill="x", padx=24, pady=18)

        top_info = ctk.CTkFrame(box, fg_color="transparent")
        top_info.pack(fill="x", pady=(0, 12))

        if es_rezagado:
            badge = ctk.CTkFrame(top_info, fg_color=COLOR_DANGER_BG, corner_radius=10)
            badge.pack(side="left")
            ctk.CTkLabel(
                badge,
                text=f"⛔ CORTE REZAGADO #{corte_id} ({str(self.corte_actual['corteFechaApertura'])[:10]}) — Cierre obligatorio",
                font=("Helvetica", 11, "bold"),
                text_color=COLOR_DANGER_TXT
            ).pack(padx=10, pady=3)
        else:
            badge = ctk.CTkFrame(top_info, fg_color=COLOR_SUCCESS_BG, corner_radius=10)
            badge.pack(side="left")
            ctk.CTkLabel(
                badge,
                text=f"● Turno Abierto Hoy — Corte #{corte_id}",
                font=("Helvetica", 11, "bold"),
                text_color=COLOR_SUCCESS_TXT
            ).pack(padx=10, pady=3)

        ctk.CTkLabel(
            top_info,
            text=(
                f"Cajero: {self.corte_actual['usuarioNombre']}  |  Apertura: {self.corte_actual['corteFechaApertura']}  |  "
                f"Ventas: {self.balance_actual['num_ventas']:,}  |  Pagos Prov. Caja: {self.balance_actual['num_compras_caja']:,}"
            ),
            font=("Helvetica", 11),
            text_color=COLOR_TEXT_MUTED
        ).pack(side="right")

        cards_row = ctk.CTkFrame(box, fg_color="transparent")
        cards_row.pack(fill="x", pady=(0, 14))

        metricas = [
            ("Fondo Inicial (+)", f"${self.balance_actual['fondo_inicial']:,.2f}", COLOR_PRIMARY),
            ("Ventas Efectivo (+)", f"${self.balance_actual['ventas_efectivo']:,.2f}", COLOR_SUCCESS_TXT),
            ("Compras Efectivo (-)", f"-${self.balance_actual['compras_efectivo']:,.2f}", COLOR_DANGER_TXT),
            ("Balance Esperado Caja", f"${self.balance_actual['efectivo_esperado']:,.2f}", "#0f172a"),
            ("Ventas Tarjeta (Banco)", f"${self.balance_actual['ventas_tarjeta']:,.2f}", COLOR_INFO_TXT),
        ]
        for idx, (titulo, val, col) in enumerate(metricas):
            c = ctk.CTkFrame(cards_row, fg_color=COLOR_BG_PANEL, border_width=1, border_color=COLOR_BORDER, corner_radius=8, height=74)
            c.pack(side="left", fill="both", expand=True, padx=(0, 8 if idx < 4 else 0))
            c.pack_propagate(False)
            ctk.CTkLabel(c, text=titulo, font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=12, pady=(9, 0))
            ctk.CTkLabel(c, text=val, font=("Helvetica", 15, "bold"), text_color=col).pack(anchor="w", padx=12)

        cierre_row = ctk.CTkFrame(box, fg_color="transparent")
        cierre_row.pack(fill="x")

        ctk.CTkLabel(cierre_row, text="Efectivo contado físicamente ($):", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(side="left", padx=(0, 10))
        self.entry_contado = ctk.CTkEntry(
            cierre_row,
            placeholder_text=f"{self.balance_actual['efectivo_esperado']:,.2f}",
            width=175,
            height=40,
            fg_color="#f8fafc",
            border_color=COLOR_BORDER,
            font=("Helvetica", 13, "bold")
        )
        self.entry_contado.pack(side="left", padx=(0, 12))
        configurar_entrada_numerica(
            self.entry_contado,
            permitir_decimales=True,
            max_valor=MAX_EFECTIVO_CONTADO,
            con_comas=True,
            callback_cambio=self._actualizar_preview_diferencia
        )

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
            height=40,
            font=("Helvetica", 12, "bold"),
            command=self.cerrar_caja
        ).pack(side="right")

    def _actualizar_preview_diferencia(self):
        if not hasattr(self, "lbl_diferencia"):
            return
        texto = self.entry_contado.get().strip()
        if not texto:
            self.lbl_diferencia.configure(text="Diferencia: ingresa el conteo", text_color=COLOR_TEXT_MUTED)
            return
        try:
            contado = parsear_flotante(texto)
            esperado = self.balance_actual["efectivo_esperado"]
            dif = round(contado - esperado, 2)
            if abs(dif) < 0.005:
                self.lbl_diferencia.configure(text="Diferencia: $0.00 (Cuadrado exacto)", text_color=COLOR_SUCCESS_TXT)
            elif dif > 0:
                self.lbl_diferencia.configure(text=f"Diferencia: +${dif:,.2f} (Sobrante)", text_color=COLOR_WARN_TXT)
            else:
                self.lbl_diferencia.configure(text=f"Diferencia: -${abs(dif):,.2f} (Faltante)", text_color=COLOR_DANGER_TXT)
        except ValueError:
            self.lbl_diferencia.configure(text="Monto inválido", text_color=COLOR_DANGER_TXT)

    def cerrar_caja(self):
        texto = self.entry_contado.get().strip()
        try:
            contado = round(parsear_flotante(texto), 2)
            if contado < 0 or contado > MAX_EFECTIVO_CONTADO:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Dato inválido", f"Ingresa una cantidad numérica válida entre $0.00 y ${MAX_EFECTIVO_CONTADO:,.2f} para el efectivo contado.")
            return

        bal = self.db.calcular_balance_corte(self.corte_actual["corteId"])
        esperado = bal["efectivo_esperado"]
        diferencia = round(contado - esperado, 2)

        confirmar = messagebox.askyesno(
            "Confirmar cierre de turno",
            f"¿Deseas cerrar el Corte #{self.corte_actual['corteId']}?\n\n"
            f"• Fondo inicial: ${bal['fondo_inicial']:,.2f}\n"
            f"• Ventas en efectivo (+): ${bal['ventas_efectivo']:,.2f}\n"
            f"• Compras pagadas de caja (-): ${bal['compras_efectivo']:,.2f}\n"
            f"• Efectivo esperado: ${esperado:,.2f}\n"
            f"• Efectivo contado: ${contado:,.2f}\n"
            f"• Diferencia: ${diferencia:+,.2f}\n\n"
            "Esta acción cerrará el turno definitivamente."
        )
        if not confirmar:
            return

        res = self.db.ejecutar_consulta(
            """
            UPDATE corte
            SET corteFechaCierre = NOW(),
                corteVentasEfectivo = %s,
                corteVentasTarjeta = %s,
                corteComprasEfectivo = %s,
                corteEfectivoEsperado = %s,
                corteEfectivoContado = %s,
                corteDiferencia = %s,
                corteEstado = 0
            WHERE corteId = %s
            """,
            (
                bal["ventas_efectivo"],
                bal["ventas_tarjeta"],
                bal["compras_efectivo"],
                esperado,
                contado,
                diferencia,
                self.corte_actual["corteId"]
            )
        )
        if res is None:
            messagebox.showerror("Error", "No se pudo guardar el cierre de caja.")
            return

        messagebox.showinfo("Corte cerrado", f"El Corte #{self.corte_actual['corteId']} se cerró correctamente.")
        self.refrescar_vistas_relacionadas()

    def _construir_resumen_consolidado_dia(self):
        for w in self.panel_resumen_dia.winfo_children():
            w.destroy()

        ventas_hoy = self.db.ejecutar_consulta(
            """
            SELECT
                COALESCE(SUM(CASE WHEN ventaMetodoPago = 'Efectivo' THEN ventaTotal ELSE 0 END), 0) AS v_efec,
                COALESCE(SUM(CASE WHEN ventaMetodoPago = 'Tarjeta' THEN ventaTotal ELSE 0 END), 0) AS v_tarj,
                COALESCE(SUM(ventaTotal), 0) AS v_total
            FROM venta
            WHERE DATE(ventaFecha) = CURDATE() AND ventaEstado = 'Completada'
            """,
            fetch=True
        )[0]

        compras_hoy = self.db.ejecutar_consulta(
            """
            SELECT
                COALESCE(SUM(CASE WHEN compraMetodoPago = 'Efectivo Caja' THEN compraTotal ELSE 0 END), 0) AS c_caja,
                COALESCE(SUM(CASE WHEN compraMetodoPago = 'Transferencia / Externo' THEN compraTotal ELSE 0 END), 0) AS c_ext,
                COALESCE(SUM(compraTotal), 0) AS c_total
            FROM compra
            WHERE DATE(compraFecha) = CURDATE()
            """,
            fetch=True
        )[0]

        box = ctk.CTkFrame(self.panel_resumen_dia, fg_color="transparent")
        box.pack(fill="x", padx=20, pady=12)

        ctk.CTkLabel(
            box,
            text=f"Resumen Consolidado del Día ({datetime.now().strftime('%Y-%m-%d')}) — Vista Administrador",
            font=("Helvetica", 13, "bold"),
            text_color=COLOR_PRIMARY
        ).pack(anchor="w", pady=(0, 6))

        ctk.CTkLabel(
            box,
            text=(
                f"Total Vendido Hoy: ${float(ventas_hoy['v_total']):,.2f} "
                f"(Efectivo: ${float(ventas_hoy['v_efec']):,.2f} | Tarjeta: ${float(ventas_hoy['v_tarj']):,.2f})    •    "
                f"Total Comprado a Proveedores Hoy: ${float(compras_hoy['c_total']):,.2f} "
                f"(Efectivo Caja: ${float(compras_hoy['c_caja']):,.2f} | Externo/Transf.: ${float(compras_hoy['c_ext']):,.2f})"
            ),
            font=("Helvetica", 12, "bold"),
            text_color=COLOR_INFO_TXT
        ).pack(anchor="w")

    def _cargar_historial(self, user):
        for w in self.hist_scroll.winfo_children():
            w.destroy()

        es_admin = self.sesion.es_admin()
        self.lbl_alcance_hist.configure(
            text="Mostrando todos los turnos (Administrador)" if es_admin else f"Mostrando únicamente los cortes de {user['nombre']}"
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

        headers = ["Folio", "Empleado", "Apertura", "Cierre", "Fondo", "Compras Caja", "Esperado", "Contado", "Diferencia", "Estado"]
        for col_idx, titulo in enumerate(headers):
            ctk.CTkLabel(self.hist_scroll, text=titulo, font=("Helvetica", 11, "bold"), text_color=COLOR_TEXT_MUTED).grid(
                row=0, column=col_idx, padx=8, pady=8, sticky="w"
            )

        if not cortes:
            ctk.CTkLabel(self.hist_scroll, text="Aún no hay cortes registrados.", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(
                row=1, column=0, columnspan=10, pady=20
            )
            return

        for row_idx, c in enumerate(cortes, start=1):
            abierto = int(c["corteEstado"]) == 1
            compras_c = f"-${float(c.get('corteComprasEfectivo') or 0):,.2f}"
            esperado = f"${float(c['corteEfectivoEsperado']):,.2f}" if c["corteEfectivoEsperado"] is not None else "En curso"
            contado = f"${float(c['corteEfectivoContado']):,.2f}" if c["corteEfectivoContado"] is not None else "—"

            if c["corteDiferencia"] is not None:
                dif_val = float(c["corteDiferencia"])
                dif_txt = f"${dif_val:+,.2f}"
                dif_col = COLOR_SUCCESS_TXT if abs(dif_val) < 0.005 else (COLOR_WARN_TXT if dif_val > 0 else COLOR_DANGER_TXT)
            else:
                dif_txt = "—"
                dif_col = COLOR_TEXT_MUTED

            valores = [
                (f"#{c['corteId']}", COLOR_PRIMARY, True),
                (c["usuarioNombre"], COLOR_PRIMARY, True),
                (str(c["corteFechaApertura"])[:16], COLOR_TEXT_MUTED, False),
                (str(c["corteFechaCierre"])[:16] if c["corteFechaCierre"] else "Abierto", COLOR_TEXT_MUTED, False),
                (f"${float(c['corteFondoInicial']):,.2f}", COLOR_PRIMARY, False),
                (compras_c, COLOR_DANGER_TXT, False),
                (esperado, COLOR_PRIMARY, True),
                (contado, COLOR_PRIMARY, False),
                (dif_txt, dif_col, True),
            ]
            for col_idx, (txt, col, negrita) in enumerate(valores):
                ctk.CTkLabel(
                    self.hist_scroll,
                    text=txt,
                    font=("Helvetica", 11, "bold" if negrita else "normal"),
                    text_color=col
                ).grid(row=row_idx, column=col_idx, padx=8, pady=7, sticky="w")

            badge = ctk.CTkFrame(
                self.hist_scroll,
                fg_color=COLOR_SUCCESS_BG if abierto else "#e2e8f0",
                corner_radius=10
            )
            badge.grid(row=row_idx, column=9, padx=8, pady=5, sticky="w")
            ctk.CTkLabel(
                badge,
                text="Abierto" if abierto else "Cerrado",
                font=("Helvetica", 10, "bold"),
                text_color=COLOR_SUCCESS_TXT if abierto else COLOR_PRIMARY
            ).pack(padx=8, pady=2)


# ============================================================================
# VISTA 4: ComprasView (Surtido de Proveedores con Límites y Comas Automáticas)
# ============================================================================
class ComprasView(VistaBase):
    def construir_interfaz(self):
        self.orden_compra = {}
        self.proveedores_map = {}
        self.productos_map = {}
        self.total_compra = 0.0

        main_box = ctk.CTkFrame(self, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=32, pady=24)

        header = ctk.CTkFrame(main_box, fg_color="transparent")
        header.pack(fill="x", pady=(0, 12))
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(titles, text="Compras y Recepción de Proveedores", font=("Helvetica", 24, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(titles, text="Registra cuánto pagaste y cuántas piezas entregó el proveedor; genera ticket con fecha y actualiza inventario.", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        ctk.CTkButton(
            header, text="↻ Actualizar", width=115, height=36,
            fg_color=COLOR_PRIMARY, font=("Helvetica", 12, "bold"), command=self.actualizar_datos
        ).pack(side="right")

        tabs_bar = ctk.CTkFrame(main_box, fg_color="#e9eff5", corner_radius=8, height=40)
        tabs_bar.pack(fill="x", pady=(0, 14))
        tabs_bar.pack_propagate(False)

        self.pestana_activa = "Nueva Compra"
        self.tab_btns = {}
        for idx, nombre in enumerate(["Nueva Compra", "Historial de Tickets de Compra"]):
            tabs_bar.grid_columnconfigure(idx, weight=1)
            b = ctk.CTkButton(
                tabs_bar, text=nombre, corner_radius=6, height=32,
                font=("Helvetica", 12, "bold"),
                command=lambda n=nombre: self._cambiar_pestana(n)
            )
            b.grid(row=0, column=idx, padx=4, pady=4, sticky="nsew")
            self.tab_btns[nombre] = b

        self.contenedor_pestanas = ctk.CTkFrame(main_box, fg_color="transparent")
        self.contenedor_pestanas.pack(fill="both", expand=True)

        self.frame_nueva = ctk.CTkFrame(self.contenedor_pestanas, fg_color="transparent")
        self.frame_nueva.grid_columnconfigure(0, weight=3)
        self.frame_nueva.grid_columnconfigure(1, weight=2)
        self.frame_nueva.grid_rowconfigure(0, weight=1)

        form_card = ctk.CTkFrame(self.frame_nueva, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=12)
        form_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))

        f_inner = ctk.CTkFrame(form_card, fg_color="transparent")
        f_inner.pack(fill="both", expand=True, padx=22, pady=20)

        ctk.CTkLabel(f_inner, text="1. Datos de la Entrega del Proveedor", font=("Helvetica", 15, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0, 10))

        self.lbl_info_caja_compra = ctk.CTkLabel(f_inner, text="", font=("Helvetica", 11, "bold"), text_color=COLOR_INFO_TXT)
        self.lbl_info_caja_compra.pack(anchor="w", pady=(0, 10))

        row_prov = ctk.CTkFrame(f_inner, fg_color="transparent")
        row_prov.pack(fill="x", pady=(0, 10))
        col_p1 = ctk.CTkFrame(row_prov, fg_color="transparent")
        col_p1.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkLabel(col_p1, text="Proveedor que entrega:", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0, 3))
        self.combo_proveedor = ctk.CTkComboBox(col_p1, values=["Cargando..."], state="readonly", height=38, fg_color="#f8fafc", border_color=COLOR_BORDER, font=("Helvetica", 12))
        self.combo_proveedor.pack(fill="x")

        col_p2 = ctk.CTkFrame(row_prov, fg_color="transparent")
        col_p2.pack(side="right", fill="x", expand=True, padx=(8, 0))
        ctk.CTkLabel(col_p2, text="¿De dónde se paga?", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0, 3))
        self.combo_pago_compra = ctk.CTkComboBox(
            col_p2,
            values=["Efectivo Caja", "Transferencia / Externo"],
            state="readonly",
            height=38,
            fg_color="#f8fafc",
            border_color=COLOR_BORDER,
            font=("Helvetica", 12)
        )
        self.combo_pago_compra.set("Efectivo Caja")
        self.combo_pago_compra.pack(fill="x")

        ctk.CTkLabel(f_inner, text="Nota o folio de remisión del proveedor (opcional):", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(4, 3))
        self.entry_notas_compra = ctk.CTkEntry(f_inner, placeholder_text="Ej. Nota #4582 repartidor matutino", height=38, fg_color="#f8fafc", border_color=COLOR_BORDER, font=("Helvetica", 12))
        self.entry_notas_compra.pack(fill="x", pady=(0, 14))

        ctk.CTkFrame(f_inner, fg_color=COLOR_BORDER, height=2).pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(f_inner, text="2. Agregar Productos Recibidos", font=("Helvetica", 15, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(f_inner, text="Selecciona el producto:", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0, 3))
        self.combo_producto = ctk.CTkComboBox(
            f_inner,
            values=["Cargando..."],
            state="readonly",
            height=38,
            fg_color="#f8fafc",
            border_color=COLOR_BORDER,
            font=("Helvetica", 12),
            command=self._al_seleccionar_producto
        )
        self.combo_producto.pack(fill="x", pady=(0, 10))

        row_cant_costo = ctk.CTkFrame(f_inner, fg_color="transparent")
        row_cant_costo.pack(fill="x", pady=(0, 14))

        c_cant = ctk.CTkFrame(row_cant_costo, fg_color="transparent")
        c_cant.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkLabel(c_cant, text=f"Cantidad recibida (máx. {MAX_CANTIDAD_COMPRA:,} pz):", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0, 3))
        self.entry_cant_recibida = ctk.CTkEntry(c_cant, placeholder_text="Ej. 12", height=38, fg_color="#f8fafc", border_color=COLOR_BORDER, font=("Helvetica", 13, "bold"))
        self.entry_cant_recibida.pack(fill="x")
        configurar_entrada_numerica(
            self.entry_cant_recibida,
            permitir_decimales=False,
            max_valor=MAX_CANTIDAD_COMPRA,
            con_comas=True
        )

        c_costo = ctk.CTkFrame(row_cant_costo, fg_color="transparent")
        c_costo.pack(side="right", fill="x", expand=True, padx=(8, 0))
        ctk.CTkLabel(c_costo, text=f"Costo unitario $ (máx. ${MAX_PRECIO_PRODUCTO:,.0f}):", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(0, 3))
        self.entry_costo_unitario = ctk.CTkEntry(c_costo, placeholder_text="Ej. 34.00", height=38, fg_color="#f8fafc", border_color=COLOR_BORDER, font=("Helvetica", 13, "bold"))
        self.entry_costo_unitario.pack(fill="x")
        configurar_entrada_numerica(
            self.entry_costo_unitario,
            permitir_decimales=True,
            max_valor=MAX_PRECIO_PRODUCTO,
            con_comas=True
        )

        ctk.CTkButton(
            f_inner,
            text="+ Agregar a la Orden de Compra",
            fg_color=COLOR_PRIMARY,
            hover_color="#0f172a",
            height=42,
            font=("Helvetica", 12, "bold"),
            command=self.agregar_renglon_compra
        ).pack(fill="x")

        ticket_card = ctk.CTkFrame(self.frame_nueva, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=12)
        ticket_card.grid(row=0, column=1, sticky="nsew")

        ctk.CTkLabel(ticket_card, text="Detalle de Mercancía a Ingresar", font=("Helvetica", 16, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", padx=20, pady=(20, 8))

        self.orden_scroll = ctk.CTkScrollableFrame(ticket_card, fg_color="transparent")
        self.orden_scroll.pack(fill="both", expand=True, padx=12)

        bot_compra = ctk.CTkFrame(ticket_card, fg_color="transparent")
        bot_compra.pack(side="bottom", fill="x", padx=20, pady=18)
        ctk.CTkFrame(bot_compra, fg_color=COLOR_BORDER, height=2).pack(fill="x", pady=(0, 12))

        tot_c_row = ctk.CTkFrame(bot_compra, fg_color="transparent")
        tot_c_row.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(tot_c_row, text="Total Pagado:", font=("Helvetica", 15, "bold"), text_color=COLOR_PRIMARY).pack(side="left")
        self.lbl_total_compra = ctk.CTkLabel(tot_c_row, text="$0.00", font=("Helvetica", 22, "bold"), text_color=COLOR_DANGER_TXT)
        self.lbl_total_compra.pack(side="right")

        ctk.CTkButton(
            bot_compra,
            text="Guardar Compra y Generar Ticket",
            fg_color=COLOR_SUCCESS_TXT,
            hover_color="#047857",
            text_color="white",
            height=46,
            font=("Helvetica", 13, "bold"),
            command=self.confirmar_compra
        ).pack(fill="x")

        self.frame_historial = ctk.CTkFrame(self.contenedor_pestanas, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=12)
        self.hist_compras_scroll = ctk.CTkScrollableFrame(self.frame_historial, fg_color="transparent")
        self.hist_compras_scroll.pack(fill="both", expand=True, padx=16, pady=16)

        self._cambiar_pestana("Nueva Compra")

    def _cambiar_pestana(self, nombre: str):
        self.pestana_activa = nombre
        for tab, btn in self.tab_btns.items():
            activa = (tab == nombre)
            btn.configure(
                fg_color=COLOR_CARD if activa else "transparent",
                text_color=COLOR_PRIMARY if activa else COLOR_TEXT_MUTED
            )
        if nombre == "Nueva Compra":
            self.frame_historial.pack_forget()
            self.frame_nueva.pack(fill="both", expand=True)
        else:
            self.frame_nueva.pack_forget()
            self.frame_historial.pack(fill="both", expand=True)
            self._cargar_historial_compras()
        self.acc.aplicar_a_widget(self)

    def actualizar_datos(self):
        user = self.sesion.get_usuario_actual()
        if not user:
            return

        estado_corte = self.db.obtener_estado_corte_usuario(user["id"])
        if estado_corte["estado"] == "ABIERTO_HOY":
            bal = self.db.calcular_balance_corte(estado_corte["corte"]["corteId"])
            self.lbl_info_caja_compra.configure(
                text=f"● Corte #{estado_corte['corte']['corteId']} activo hoy — Efectivo disponible en caja: ${bal['efectivo_esperado']:,.2f}",
                text_color=COLOR_SUCCESS_TXT
            )
        else:
            self.lbl_info_caja_compra.configure(
                text="⚠ No tienes turno abierto hoy: solo podrás registrar compras con 'Transferencia / Externo' o abrir caja primero.",
                text_color=COLOR_WARN_TXT
            )

        proveedores = self.db.ejecutar_consulta(
            "SELECT proveedorId, proveedorNombreEmpresa FROM proveedor ORDER BY proveedorNombreEmpresa",
            fetch=True
        ) or []
        self.proveedores_map = {f"{p['proveedorId']} | {p['proveedorNombreEmpresa']}": p for p in proveedores}
        if self.proveedores_map:
            self.combo_proveedor.configure(values=list(self.proveedores_map.keys()))
            if self.combo_proveedor.get() not in self.proveedores_map:
                self.combo_proveedor.set(next(iter(self.proveedores_map)))

        productos = self.db.ejecutar_consulta(
            "SELECT productoId, productoCodigoBarras, productoNombre, productoPrecioCompra, productoStockActual FROM producto ORDER BY productoNombre",
            fetch=True
        ) or []
        self.productos_map = {
            f"{p['productoNombre']} (Stock: {int(p['productoStockActual']):,}) [#{p['productoId']}]": p
            for p in productos
        }
        if self.productos_map:
            self.combo_producto.configure(values=list(self.productos_map.keys()))
            if self.combo_producto.get() not in self.productos_map:
                primera = next(iter(self.productos_map))
                self.combo_producto.set(primera)
                self._al_seleccionar_producto(primera)

        self._dibujar_orden_compra()
        if self.pestana_activa == "Historial de Tickets de Compra":
            self._cargar_historial_compras()
        self.acc.aplicar_a_widget(self)

    def _al_seleccionar_producto(self, etiqueta: str):
        prod = self.productos_map.get(etiqueta)
        if prod and prod.get("productoPrecioCompra") is not None:
            self.entry_costo_unitario.delete(0, "end")
            self.entry_costo_unitario.insert(0, f"{float(prod['productoPrecioCompra']):,.2f}")

    def agregar_renglon_compra(self):
        if not self.sesion.es_admin():
            messagebox.showerror("Acceso denegado", "Solo el Administrador puede registrar compras de mercancía.")
            return

        prod = self.productos_map.get(self.combo_producto.get())
        if not prod:
            messagebox.showwarning("Producto requerido", "Selecciona un producto válido.")
            return

        try:
            cant = parsear_entero(self.entry_cant_recibida.get())
            costo = round(parsear_flotante(self.entry_costo_unitario.get()), 2)
            if cant <= 0 or cant > MAX_CANTIDAD_COMPRA:
                raise ValueError(f"La cantidad recibida debe ser entre 1 y {MAX_CANTIDAD_COMPRA:,} piezas.")
            if costo <= 0 or costo > MAX_PRECIO_PRODUCTO:
                raise ValueError(f"El costo unitario debe ser mayor a $0.00 y máximo ${MAX_PRECIO_PRODUCTO:,.2f}.")
        except ValueError as err:
            messagebox.showwarning("Datos inválidos", str(err) if str(err) else "Ingresa una cantidad entera válida y un costo unitario mayor a $0.00.")
            return

        id_p = prod["productoId"]
        cant_acumulada = cant + (self.orden_compra[id_p]["cantidad"] if id_p in self.orden_compra else 0)
        if cant_acumulada > MAX_CANTIDAD_COMPRA:
            messagebox.showwarning(
                "Límite de recepción excedido",
                f"No puedes ingresar más de {MAX_CANTIDAD_COMPRA:,} piezas de '{prod['productoNombre']}' en una sola orden."
            )
            return

        if id_p in self.orden_compra:
            self.orden_compra[id_p]["cantidad"] = cant_acumulada
            self.orden_compra[id_p]["costo"] = costo
        else:
            self.orden_compra[id_p] = {
                "nombre": prod["productoNombre"],
                "cantidad": cant,
                "costo": costo
            }

        self.entry_cant_recibida.delete(0, "end")
        self._dibujar_orden_compra()

    def _eliminar_renglon_compra(self, id_p: int):
        if id_p in self.orden_compra:
            del self.orden_compra[id_p]
        self._dibujar_orden_compra()

    def _dibujar_orden_compra(self):
        for w in self.orden_scroll.winfo_children():
            w.destroy()

        self.total_compra = 0.0
        if not self.orden_compra:
            ctk.CTkLabel(self.orden_scroll, text="Agrega productos recibidos del proveedor.", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).pack(pady=24)
            self.lbl_total_compra.configure(text="$0.00")
            self.acc.aplicar_a_widget(self.orden_scroll)
            return

        for id_p, item in self.orden_compra.items():
            sub = round(item["cantidad"] * item["costo"], 2)
            self.total_compra = round(self.total_compra + sub, 2)

            row = ctk.CTkFrame(self.orden_scroll, fg_color=COLOR_BG_PANEL, border_width=1, border_color=COLOR_BORDER, corner_radius=8)
            row.pack(fill="x", pady=4)

            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=10, pady=(8, 2))
            ctk.CTkLabel(top, text=item["nombre"], font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(side="left")
            ctk.CTkButton(
                top, text="✕", width=28, height=28, fg_color="transparent",
                hover_color="#fee2e2", text_color="#ef4444", font=("Helvetica", 12, "bold"),
                command=lambda i=id_p: self._eliminar_renglon_compra(i)
            ).pack(side="right")

            bot = ctk.CTkFrame(row, fg_color="transparent")
            bot.pack(fill="x", padx=10, pady=(0, 8))
            ctk.CTkLabel(bot, text=f"{item['cantidad']:,} pz × ${item['costo']:,.2f} c/u", font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED).pack(side="left")
            ctk.CTkLabel(bot, text=f"${sub:,.2f}", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(side="right")

        self.lbl_total_compra.configure(text=f"${self.total_compra:,.2f}")
        self.acc.aplicar_a_widget(self.orden_scroll)

    def confirmar_compra(self):
        if not self.sesion.es_admin():
            messagebox.showerror("Acceso denegado", "Solo el Administrador puede registrar compras.")
            return

        if not self.orden_compra:
            messagebox.showwarning("Orden vacía", "Agrega al menos un producto entregado por el proveedor.")
            return

        prov = self.proveedores_map.get(self.combo_proveedor.get())
        if not prov:
            messagebox.showwarning("Proveedor requerido", "Selecciona un proveedor.")
            return

        user = self.sesion.get_usuario_actual()
        metodo_pago = self.combo_pago_compra.get()
        if metodo_pago not in ("Efectivo Caja", "Transferencia / Externo"):
            messagebox.showwarning("Método inválido", "Selecciona un origen de pago válido.")
            return

        notas = self.entry_notas_compra.get().strip()

        estado_corte = self.db.obtener_estado_corte_usuario(user["id"])
        id_corte_hoy = estado_corte["corte"]["corteId"] if estado_corte["estado"] == "ABIERTO_HOY" else None

        items_ticket = [
            {
                "nombre": d["nombre"],
                "cantidad": d["cantidad"],
                "costo": d["costo"],
                "subtotal": round(d["cantidad"] * d["costo"], 2)
            }
            for d in self.orden_compra.values()
        ]
        total_ticket = self.total_compra

        id_compra, error_msg = self.db.registrar_compra_transaccion(
            id_usuario=user["id"],
            id_proveedor=prov["proveedorId"],
            id_corte=id_corte_hoy,
            metodo_pago=metodo_pago,
            total_compra=total_ticket,
            notas=notas,
            items_compra=self.orden_compra
        )

        if error_msg:
            messagebox.showerror("No se pudo registrar la compra", error_msg)
            return

        self.orden_compra.clear()
        self.entry_notas_compra.delete(0, "end")
        self._dibujar_orden_compra()
        self.refrescar_vistas_relacionadas()

        fecha_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lineas = [
            "==========================================",
            "            ABARROTES LUPITA              ",
            "        TICKET / RECEPCIÓN DE COMPRA      ",
            "==========================================",
            f"Folio Compra: #C-{id_compra:05d}",
            f"Fecha y Hora: {fecha_str}",
            f"Proveedor   : {prov['proveedorNombreEmpresa']}",
            f"Recibió     : {user['nombre']}",
            f"Método Pago : {metodo_pago}",
        ]
        if notas:
            lineas.append(f"Referencia  : {notas}")
        lineas.extend([
            "------------------------------------------",
            "CANT   PRODUCTO              COSTO TOT.",
            "------------------------------------------",
        ])
        for it in items_ticket:
            nom = it["nombre"][:20].ljust(20)
            lineas.append(f"{it['cantidad']:>5,}x {nom}  ${it['subtotal']:>9,.2f}")
            lineas.append(f"       (Costo unitario: ${it['costo']:,.2f})")
        lineas.extend([
            "------------------------------------------",
            f"TOTAL PAGADO AL PROVEEDOR:   ${total_ticket:>10,.2f}",
            "==========================================",
            "  Inventario actualizado automáticamente    ",
            "==========================================",
        ])
        mostrar_modal_ticket(
            self,
            f"Ticket de Compra #C-{id_compra:05d}",
            "\n".join(lineas),
            f"ticket_compra_{id_compra}.txt"
        )

    def _cargar_historial_compras(self):
        for w in self.hist_compras_scroll.winfo_children():
            w.destroy()

        compras = self.db.ejecutar_consulta(
            """
            SELECT co.compraId, co.compraFecha, pr.proveedorNombreEmpresa,
                   u.usuarioNombre, co.compraMetodoPago, co.compraTotal, co.compraNotas
            FROM compra co
            JOIN proveedor pr ON pr.proveedorId = co.compraProveedorId
            JOIN usuario u ON u.usuarioId = co.compraUsuarioId
            ORDER BY co.compraId DESC LIMIT 50
            """,
            fetch=True
        ) or []

        headers = ["Folio", "Fecha y Hora", "Proveedor", "Recibió", "Método Pago", "Total Pagado", "Comprobante"]
        for col_idx, titulo in enumerate(headers):
            ctk.CTkLabel(self.hist_compras_scroll, text=titulo, font=("Helvetica", 11, "bold"), text_color=COLOR_TEXT_MUTED).grid(
                row=0, column=col_idx, padx=10, pady=8, sticky="w"
            )

        if not compras:
            ctk.CTkLabel(self.hist_compras_scroll, text="No hay compras registradas aún.", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(
                row=1, column=0, columnspan=7, pady=24
            )
            self.acc.aplicar_a_widget(self.hist_compras_scroll)
            return

        for r_idx, c in enumerate(compras, start=1):
            ctk.CTkLabel(self.hist_compras_scroll, text=f"#C-{c['compraId']:05d}", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).grid(row=r_idx, column=0, padx=10, pady=7, sticky="w")
            ctk.CTkLabel(self.hist_compras_scroll, text=str(c["compraFecha"])[:19], font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED).grid(row=r_idx, column=1, padx=10, sticky="w")
            ctk.CTkLabel(self.hist_compras_scroll, text=c["proveedorNombreEmpresa"], font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).grid(row=r_idx, column=2, padx=10, sticky="w")
            ctk.CTkLabel(self.hist_compras_scroll, text=c["usuarioNombre"], font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED).grid(row=r_idx, column=3, padx=10, sticky="w")
            ctk.CTkLabel(self.hist_compras_scroll, text=c["compraMetodoPago"], font=("Helvetica", 11, "bold"), text_color=COLOR_DANGER_TXT if c["compraMetodoPago"] == "Efectivo Caja" else COLOR_INFO_TXT).grid(row=r_idx, column=4, padx=10, sticky="w")
            ctk.CTkLabel(self.hist_compras_scroll, text=f"${float(c['compraTotal']):,.2f}", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).grid(row=r_idx, column=5, padx=10, sticky="w")

            ctk.CTkButton(
                self.hist_compras_scroll, text="Ver Ticket", width=90, height=30,
                fg_color="transparent", border_width=1, border_color=COLOR_BORDER, text_color=COLOR_PRIMARY,
                font=("Helvetica", 11, "bold"),
                command=lambda comp=c: self._reabrir_ticket_compra(comp)
            ).grid(row=r_idx, column=6, padx=10, sticky="w")

        self.acc.aplicar_a_widget(self.hist_compras_scroll)

    def _reabrir_ticket_compra(self, compra: dict):
        detalles = self.db.ejecutar_consulta(
            """
            SELECT dc.detalleCompraCantidad, dc.detalleCompraCostoUnitario, dc.detalleCompraSubtotal,
                   p.productoNombre
            FROM detalle_compra dc
            JOIN producto p ON p.productoId = dc.detalleCompraProductoId
            WHERE dc.detalleCompraCompraId = %s
            """,
            (compra["compraId"],),
            fetch=True
        ) or []

        lineas = [
            "==========================================",
            "            ABARROTES LUPITA              ",
            "        TICKET / RECEPCIÓN DE COMPRA      ",
            "==========================================",
            f"Folio Compra: #C-{compra['compraId']:05d}",
            f"Fecha y Hora: {str(compra['compraFecha'])[:19]}",
            f"Proveedor   : {compra['proveedorNombreEmpresa']}",
            f"Recibió     : {compra['usuarioNombre']}",
            f"Método Pago : {compra['compraMetodoPago']}",
        ]
        if compra.get("compraNotas"):
            lineas.append(f"Referencia  : {compra['compraNotas']}")
        lineas.extend([
            "------------------------------------------",
            "CANT   PRODUCTO              COSTO TOT.",
            "------------------------------------------",
        ])
        for d in detalles:
            nom = d["productoNombre"][:20].ljust(20)
            sub = float(d["detalleCompraSubtotal"] or (d["detalleCompraCantidad"] * d["detalleCompraCostoUnitario"]))
            lineas.append(f"{int(d['detalleCompraCantidad']):>5,}x {nom}  ${sub:>9,.2f}")
            lineas.append(f"       (Costo unitario: ${float(d['detalleCompraCostoUnitario']):,.2f})")
        lineas.extend([
            "------------------------------------------",
            f"TOTAL PAGADO AL PROVEEDOR:   ${float(compra['compraTotal']):>10,.2f}",
            "==========================================",
        ])
        mostrar_modal_ticket(
            self,
            f"Ticket de Compra #C-{compra['compraId']:05d}",
            "\n".join(lineas),
            f"ticket_compra_{compra['compraId']}.txt"
        )


# ============================================================================
# VISTA 5: ProductosView (Catálogo sin Edición Manual de Stock — Solo Admin)
# ============================================================================
class ProductosView(VistaBase):
    def construir_interfaz(self):
        main_box = ctk.CTkFrame(self, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=36, pady=24)

        header_frame = ctk.CTkFrame(main_box, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(header_frame, text="Catálogo de Productos", font=("Helvetica", 24, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(header_frame, text="Administra códigos, precios y stock mínimo. Las entradas de mercancía se registran en Compras.", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        self.action_bar = ctk.CTkFrame(main_box, fg_color="transparent")
        self.action_bar.pack(fill="x", pady=(0, 16))
        self.btn_agregar_prod = ctk.CTkButton(
            self.action_bar, text="Agregar producto +", fg_color=COLOR_PRIMARY, text_color="white",
            corner_radius=6, height=38, font=("Helvetica", 12, "bold"),
            command=self.modal_agregar_producto
        )
        self.btn_agregar_prod.pack(side="right")

        ctk.CTkButton(
            self.action_bar, text="↻ Actualizar", fg_color=COLOR_PRIMARY, text_color="white",
            corner_radius=6, height=38, font=("Helvetica", 12, "bold"),
            command=self.refrescar_vistas_relacionadas
        ).pack(side="right", padx=8)

        self.metrics_frame = ctk.CTkFrame(main_box, fg_color="transparent")
        self.metrics_frame.pack(fill="x", pady=(0, 16))
        table_container = ctk.CTkFrame(main_box, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=10)
        table_container.pack(fill="both", expand=True)
        self.table_frame = ctk.CTkScrollableFrame(table_container, fg_color="transparent")
        self.table_frame.pack(fill="both", expand=True, padx=5, pady=5)

    def actualizar_datos(self):
        es_admin = self.sesion.es_admin()
        if es_admin:
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
                ("Total de productos", f"{int(stats[0]['total']):,}", COLOR_PRIMARY),
                ("Con existencias", f"{int(stats[0]['en_stock'] or 0):,}", COLOR_SUCCESS_TXT),
                ("Stock mínimo / agotados", f"{int(stats[0]['alerta_stock'] or 0):,}", COLOR_WARN_TXT)
            ]
            for idx, (label, valor, color_val) in enumerate(datos_metricas):
                card = ctk.CTkFrame(self.metrics_frame, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=8, height=74)
                card.pack(side="left", padx=(0, 10 if idx < 2 else 0), expand=True, fill="both")
                card.pack_propagate(False)
                ctk.CTkLabel(card, text=label, font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=15, pady=(9, 0))
                ctk.CTkLabel(card, text=valor, font=("Helvetica", 18, "bold"), text_color=color_val).pack(anchor="w", padx=15)

        for widget in self.table_frame.winfo_children():
            widget.destroy()

        headers = ["Producto", "Código", "Últ. Costo", "Precio Venta", "Inventario", "Mínimo", "Estado", "Acciones"]
        for idx, titulo in enumerate(headers):
            ctk.CTkLabel(self.table_frame, text=titulo, font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).grid(
                row=0, column=idx, padx=12, pady=12, sticky="w"
            )

        productos = self.db.ejecutar_consulta("SELECT * FROM producto ORDER BY productoNombre", fetch=True) or []
        if not productos:
            ctk.CTkLabel(self.table_frame, text="No hay productos registrados.", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(
                row=1, column=0, columnspan=len(headers), pady=20
            )
            self.acc.aplicar_a_widget(self)
            return

        for i, producto in enumerate(productos, start=1):
            stock = int(producto["productoStockActual"])
            stock_min = int(producto.get("productoStockMinimo") or 0)
            costo_txt = f"${float(producto['productoPrecioCompra']):,.2f}" if producto.get("productoPrecioCompra") is not None else "—"

            ctk.CTkLabel(self.table_frame, text=producto["productoNombre"], font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).grid(row=i, column=0, padx=12, pady=9, sticky="w")
            ctk.CTkLabel(self.table_frame, text=str(producto["productoCodigoBarras"] or ""), font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED).grid(row=i, column=1, padx=12, sticky="w")
            ctk.CTkLabel(self.table_frame, text=costo_txt, font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(row=i, column=2, padx=12, sticky="w")
            ctk.CTkLabel(self.table_frame, text=f"${float(producto['productoPrecioVenta']):,.2f}", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).grid(row=i, column=3, padx=12, sticky="w")
            ctk.CTkLabel(self.table_frame, text=f"{stock:,} pz", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).grid(row=i, column=4, padx=12, sticky="w")
            ctk.CTkLabel(self.table_frame, text=f"{stock_min:,} pz", font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED).grid(row=i, column=5, padx=12, sticky="w")

            if stock <= 0:
                bg, fg, txt = COLOR_DANGER_BG, COLOR_DANGER_TXT, "Agotado"
            elif stock <= stock_min:
                bg, fg, txt = COLOR_WARN_BG, COLOR_WARN_TXT, "Stock bajo"
            else:
                bg, fg, txt = COLOR_SUCCESS_BG, COLOR_SUCCESS_TXT, "En stock"

            estado_frame = ctk.CTkFrame(self.table_frame, fg_color=bg, corner_radius=12)
            estado_frame.grid(row=i, column=6, padx=12, sticky="w")
            ctk.CTkLabel(estado_frame, text=txt, font=("Helvetica", 11, "bold"), text_color=fg).pack(padx=10, pady=2)

            if es_admin:
                acciones = ctk.CTkFrame(self.table_frame, fg_color="transparent")
                acciones.grid(row=i, column=7, padx=10, sticky="w")
                ctk.CTkButton(
                    acciones, text="Editar", width=65, height=30,
                    fg_color="transparent", border_width=1, border_color=COLOR_BORDER, text_color=COLOR_PRIMARY,
                    font=("Helvetica", 11, "bold"),
                    command=lambda p=producto: self.modal_editar_producto(p)
                ).pack(side="left", padx=3)
                ctk.CTkButton(
                    acciones, text="Eliminar", width=72, height=30,
                    fg_color=COLOR_DANGER_BG, hover_color="#fecaca", text_color=COLOR_DANGER_TXT,
                    font=("Helvetica", 11, "bold"),
                    command=lambda p=producto: self.eliminar_producto(p)
                ).pack(side="left", padx=3)

        self.acc.aplicar_a_widget(self)

    def modal_agregar_producto(self):
        if not self.sesion.es_admin():
            messagebox.showerror("Acceso denegado", "Solo el Administrador puede dar de alta productos.")
            return
        self._abrir_formulario_producto()

    def modal_editar_producto(self, producto):
        if not self.sesion.es_admin():
            messagebox.showerror("Acceso denegado", "Solo el Administrador puede editar productos.")
            return
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

        factor_ventana = min(self.acc.escala, 1.25)
        modal = ctk.CTkToplevel(self)
        modal.title("Editar producto" if es_edicion else "Nuevo producto")
        modal.geometry(f"{int(480 * factor_ventana)}x{int(630 * factor_ventana)}")
        modal.grab_set()

        inner = ctk.CTkScrollableFrame(modal, fg_color="transparent")
        inner.pack(padx=25, pady=20, fill="both", expand=True)
        entradas = {}

        valores_iniciales = {
            "codigobarras": producto["productoCodigoBarras"] if es_edicion else "",
            "nombre": producto["productoNombre"] if es_edicion else "",
            "preciocompra": f"{float(producto['productoPrecioCompra']):,.2f}" if es_edicion and producto["productoPrecioCompra"] is not None else "",
            "precioventa": f"{float(producto['productoPrecioVenta']):,.2f}" if es_edicion else "",
            "stockminimo": f"{int(producto.get('productoStockMinimo', 0)):,}" if es_edicion else "0"
        }

        campos_config = [
            ("codigobarras", "Código de barras (solo números)", {"tipo": "codigo"}),
            ("nombre", "Nombre del producto", {"tipo": "texto"}),
            ("preciocompra", f"Costo de referencia $ (opcional, máx. ${MAX_PRECIO_PRODUCTO:,.0f})", {"tipo": "decimal", "max": MAX_PRECIO_PRODUCTO}),
            ("precioventa", f"Precio de venta al público $ (máx. ${MAX_PRECIO_PRODUCTO:,.0f})", {"tipo": "decimal", "max": MAX_PRECIO_PRODUCTO}),
            ("stockminimo", f"Stock mínimo para alerta (máx. {MAX_STOCK_MINIMO:,} pz)", {"tipo": "entero", "max": MAX_STOCK_MINIMO}),
        ]

        for key, titulo, cfg in campos_config:
            ctk.CTkLabel(inner, text=titulo, font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(9, 2))
            entrada = ctk.CTkEntry(inner, height=38, font=("Helvetica", 12))
            entrada.pack(fill="x", pady=(0, 4))

            if cfg["tipo"] == "codigo":
                configurar_entrada_numerica(entrada, permitir_decimales=False, max_valor=None, con_comas=False, max_digitos=MAX_DIGITOS_CODIGO)
            elif cfg["tipo"] == "decimal":
                configurar_entrada_numerica(entrada, permitir_decimales=True, max_valor=cfg["max"], con_comas=True)
            elif cfg["tipo"] == "entero":
                configurar_entrada_numerica(entrada, permitir_decimales=False, max_valor=cfg["max"], con_comas=True)

            val_init = str(valores_iniciales[key])
            if val_init:
                entrada.insert(0, val_init)
            entradas[key] = entrada

        stock_actual_val = int(producto["productoStockActual"]) if es_edicion else 0
        nota_stock = ctk.CTkFrame(inner, fg_color=COLOR_INFO_BG, corner_radius=8)
        nota_stock.pack(fill="x", pady=(10, 4))
        ctk.CTkLabel(
            nota_stock,
            text=f"Existencias actuales: {stock_actual_val:,} pz (Solo lectura).\nPara sumar inventario usa el módulo 'Compras'.",
            font=("Helvetica", 11, "bold"),
            text_color=COLOR_INFO_TXT,
            justify="left"
        ).pack(anchor="w", padx=12, pady=8)

        mapa_proveedores = {f"{p['proveedorId']} | {p['proveedorNombreEmpresa']}": p["proveedorId"] for p in proveedores}
        ctk.CTkLabel(inner, text="Proveedor principal", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(9, 2))
        combo_proveedor = ctk.CTkComboBox(inner, values=list(mapa_proveedores.keys()), state="readonly", height=38, font=("Helvetica", 12))
        combo_proveedor.pack(fill="x", pady=(0, 4))

        if es_edicion:
            for etiqueta, identificador in mapa_proveedores.items():
                if identificador == producto["productoProveedorId"]:
                    combo_proveedor.set(etiqueta)
                    break
        else:
            combo_proveedor.set(next(iter(mapa_proveedores)))

        def guardar():
            if not self.sesion.es_admin():
                messagebox.showerror("Acceso denegado", "Solo el Administrador puede guardar productos.")
                return
            try:
                proveedor_id = mapa_proveedores.get(combo_proveedor.get())
                nuevo_producto = Producto(
                    producto["productoId"] if es_edicion else None,
                    entradas["codigobarras"].get(),
                    entradas["nombre"].get(),
                    proveedor_id,
                    entradas["preciocompra"].get(),
                    entradas["precioventa"].get(),
                    stock_actual_val,
                    entradas["stockminimo"].get()
                )
                datos = nuevo_producto.to_dict()

                if es_edicion:
                    resultado = self.db.ejecutar_consulta(
                        """
                        UPDATE producto
                        SET productoCodigoBarras=%s, productoNombre=%s, productoProveedorId=%s,
                            productoPrecioCompra=%s, productoPrecioVenta=%s, productoStockMinimo=%s
                        WHERE productoId=%s
                        """,
                        (
                            datos["productoCodigoBarras"], datos["productoNombre"], datos["productoProveedorId"],
                            datos["productoPrecioCompra"] if datos["productoPrecioCompra"] > 0 else None,
                            datos["productoPrecioVenta"], datos["productoStockMinimo"], datos["productoId"]
                        )
                    )
                else:
                    resultado = self.db.ejecutar_consulta(
                        """
                        INSERT INTO producto
                            (productoCodigoBarras, productoNombre, productoProveedorId,
                             productoPrecioCompra, productoPrecioVenta, productoStockActual, productoStockMinimo)
                        VALUES (%s, %s, %s, %s, %s, 0, %s)
                        """,
                        (
                            datos["productoCodigoBarras"], datos["productoNombre"], datos["productoProveedorId"],
                            datos["productoPrecioCompra"] if datos["productoPrecioCompra"] > 0 else None,
                            datos["productoPrecioVenta"], datos["productoStockMinimo"]
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

        ctk.CTkButton(
            inner, text="Guardar cambios" if es_edicion else "Guardar producto",
            fg_color=COLOR_PRIMARY, height=42, font=("Helvetica", 12, "bold"), command=guardar
        ).pack(pady=18, fill="x")

        self.acc.aplicar_a_widget(modal)

    def eliminar_producto(self, producto):
        if not self.sesion.es_admin():
            messagebox.showerror("Acceso denegado", "Solo el Administrador puede dar de baja productos.")
            return

        if not messagebox.askyesno("Eliminar producto", f"¿Seguro que deseas eliminar '{producto['productoNombre']}'?"):
            return

        resultado = self.db.ejecutar_consulta(
            "DELETE FROM producto WHERE productoId = %s", (producto["productoId"],)
        )
        if resultado is None:
            messagebox.showerror(
                "No se pudo eliminar",
                "El producto tiene historial de ventas o compras. La base de datos impide borrarlo para conservar la auditoría."
            )
        else:
            self.refrescar_vistas_relacionadas()
            messagebox.showinfo("Producto eliminado", "El producto se eliminó correctamente.")


# ============================================================================
# VISTA 6: ProveedoresView (Gestión de Proveedores — Solo Administrador)
# ============================================================================
class ProveedoresView(VistaBase):
    def construir_interfaz(self):
        main_box = ctk.CTkFrame(self, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=36, pady=24)

        header_frame = ctk.CTkFrame(main_box, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 14))
        titles = ctk.CTkFrame(header_frame, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(titles, text="Proveedores", font=("Helvetica", 24, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(titles, text="Administra empresas y teléfonos de contacto de proveedores.", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        actions = ctk.CTkFrame(header_frame, fg_color="transparent")
        actions.pack(side="right")
        ctk.CTkButton(
            actions, text="Agregar proveedor +", fg_color=COLOR_PRIMARY,
            corner_radius=6, height=38, font=("Helvetica", 12, "bold"), command=self.modal_agregar
        ).pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            actions, text="↻ Actualizar", fg_color=COLOR_PRIMARY,
            corner_radius=6, height=38, font=("Helvetica", 12, "bold"), command=self.refrescar_vistas_relacionadas
        ).pack(side="left", padx=8)

        table_container = ctk.CTkFrame(main_box, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=10)
        table_container.pack(fill="both", expand=True, pady=(12, 0))
        self.table_frame = ctk.CTkScrollableFrame(table_container, fg_color="transparent")
        self.table_frame.pack(fill="both", expand=True, padx=5, pady=5)

    def actualizar_datos(self):
        proveedores = self.db.ejecutar_consulta(
            "SELECT * FROM proveedor ORDER BY proveedorNombreEmpresa", fetch=True
        ) or []
        for widget in self.table_frame.winfo_children():
            widget.destroy()

        headers = ["Empresa", "Teléfono", "Acciones"]
        for idx, titulo in enumerate(headers):
            ctk.CTkLabel(self.table_frame, text=titulo, font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).grid(
                row=0, column=idx, padx=20, pady=14, sticky="w"
            )

        if not proveedores:
            ctk.CTkLabel(self.table_frame, text="No hay proveedores registrados.", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(
                row=1, column=0, columnspan=3, pady=20
            )
            self.acc.aplicar_a_widget(self)
            return

        es_admin = self.sesion.es_admin()
        for i, proveedor in enumerate(proveedores, start=1):
            ctk.CTkLabel(self.table_frame, text=proveedor["proveedorNombreEmpresa"], font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY).grid(row=i, column=0, padx=20, pady=10, sticky="w")
            ctk.CTkLabel(self.table_frame, text=proveedor.get("proveedorTelefono") or "—", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(row=i, column=1, padx=20, sticky="w")

            if es_admin:
                acciones = ctk.CTkFrame(self.table_frame, fg_color="transparent")
                acciones.grid(row=i, column=2, padx=15, sticky="w")
                ctk.CTkButton(
                    acciones, text="Editar", width=68, height=30,
                    fg_color="transparent", border_width=1, border_color=COLOR_BORDER, text_color=COLOR_PRIMARY,
                    font=("Helvetica", 11, "bold"),
                    command=lambda p=proveedor: self.modal_editar(p)
                ).pack(side="left", padx=3)
                ctk.CTkButton(
                    acciones, text="Eliminar", width=72, height=30,
                    fg_color=COLOR_DANGER_BG, hover_color="#fecaca", text_color=COLOR_DANGER_TXT,
                    font=("Helvetica", 11, "bold"),
                    command=lambda p=proveedor: self.eliminar_proveedor(p)
                ).pack(side="left", padx=3)

        self.acc.aplicar_a_widget(self)

    def modal_agregar(self):
        if not self.sesion.es_admin():
            messagebox.showerror("Acceso denegado", "Solo el Administrador puede dar de alta proveedores.")
            return
        self._abrir_formulario_proveedor()

    def modal_editar(self, proveedor):
        if not self.sesion.es_admin():
            messagebox.showerror("Acceso denegado", "Solo el Administrador puede editar proveedores.")
            return
        self._abrir_formulario_proveedor(proveedor)

    def _abrir_formulario_proveedor(self, proveedor=None):
        es_edicion = proveedor is not None
        factor_ventana = min(self.acc.escala, 1.25)
        modal = ctk.CTkToplevel(self)
        modal.title("Editar proveedor" if es_edicion else "Nuevo proveedor")
        modal.geometry(f"{int(410 * factor_ventana)}x{int(340 * factor_ventana)}")
        modal.grab_set()

        inner = ctk.CTkFrame(modal, fg_color="transparent")
        inner.pack(padx=30, pady=20, fill="both", expand=True)

        ctk.CTkLabel(inner, text="Nombre de la Empresa", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(10, 2))
        ent_empresa = ctk.CTkEntry(inner, height=38, font=("Helvetica", 12))
        ent_empresa.pack(fill="x", pady=(0, 5))
        if es_edicion and proveedor.get("proveedorNombreEmpresa"):
            ent_empresa.insert(0, str(proveedor["proveedorNombreEmpresa"]))

        ctk.CTkLabel(inner, text="Teléfono (solo números)", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(10, 2))
        ent_telefono = ctk.CTkEntry(inner, height=38, font=("Helvetica", 12))
        ent_telefono.pack(fill="x", pady=(0, 5))
        configurar_entrada_numerica(
            ent_telefono,
            permitir_decimales=False,
            max_valor=None,
            con_comas=False,
            max_digitos=MAX_DIGITOS_TELEFONO
        )
        if es_edicion and proveedor.get("proveedorTelefono"):
            solo_digitos_tel = "".join(ch for ch in str(proveedor["proveedorTelefono"]) if ch.isdigit())
            ent_telefono.insert(0, solo_digitos_tel)

        def guardar():
            if not self.sesion.es_admin():
                messagebox.showerror("Acceso denegado", "Solo el Administrador puede guardar proveedores.")
                return
            empresa = ent_empresa.get().strip()
            telefono = ent_telefono.get().strip()
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
            fg_color=COLOR_PRIMARY, height=42, font=("Helvetica", 12, "bold"), command=guardar
        ).pack(pady=22, fill="x")

        self.acc.aplicar_a_widget(modal)

    def eliminar_proveedor(self, proveedor):
        if not self.sesion.es_admin():
            messagebox.showerror("Acceso denegado", "Solo el Administrador puede dar de baja proveedores.")
            return
        if not messagebox.askyesno("Eliminar proveedor", f"¿Seguro que deseas eliminar a '{proveedor['proveedorNombreEmpresa']}'?"):
            return

        resultado = self.db.ejecutar_consulta(
            "DELETE FROM proveedor WHERE proveedorId=%s", (proveedor["proveedorId"],)
        )
        if resultado is None:
            messagebox.showerror("No se pudo eliminar", "Este proveedor está asociado a productos o compras existentes.")
        else:
            self.refrescar_vistas_relacionadas()
            messagebox.showinfo("Proveedor eliminado", "El proveedor se eliminó correctamente.")


# ============================================================================
# VISTA 7: HistorialMovimientoInventarioView (Tickets de Venta y Movimiento Inventario)
# ============================================================================
class HistorialMovimientoInventarioView(VistaBase):
    """Permite auditar todos los tickets de venta emitidos y el Movimiento Inventario."""
    def construir_interfaz(self):
        main_box = ctk.CTkFrame(self, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=32, pady=24)

        header = ctk.CTkFrame(main_box, fg_color="transparent")
        header.pack(fill="x", pady=(0, 12))
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(titles, text="Historial de Ventas y Movimiento Inventario", font=("Helvetica", 24, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(titles, text="Consulta tickets históricos (pago recibido y feria) y movimientos de entrada/salida de inventario.", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        ctk.CTkButton(
            header, text="↻ Actualizar", width=115, height=36,
            fg_color=COLOR_PRIMARY, font=("Helvetica", 12, "bold"), command=self.actualizar_datos
        ).pack(side="right")

        tabs_bar = ctk.CTkFrame(main_box, fg_color="#e9eff5", corner_radius=8, height=40)
        tabs_bar.pack(fill="x", pady=(0, 14))
        tabs_bar.pack_propagate(False)

        self.pestana = "Tickets de Venta"
        self.tab_btns = {}
        for idx, nombre in enumerate(["Tickets de Venta", "Movimiento Inventario"]):
            tabs_bar.grid_columnconfigure(idx, weight=1)
            b = ctk.CTkButton(
                tabs_bar, text=nombre, corner_radius=6, height=32,
                font=("Helvetica", 12, "bold"),
                command=lambda n=nombre: self._seleccionar_tab(n)
            )
            b.grid(row=0, column=idx, padx=4, pady=4, sticky="nsew")
            self.tab_btns[nombre] = b

        card = ctk.CTkFrame(main_box, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=12)
        card.pack(fill="both", expand=True)
        self.scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=14, pady=14)

        self._seleccionar_tab("Tickets de Venta")

    def _seleccionar_tab(self, nombre: str):
        self.pestana = nombre
        for t, b in self.tab_btns.items():
            activa = (t == nombre)
            b.configure(fg_color=COLOR_CARD if activa else "transparent", text_color=COLOR_PRIMARY if activa else COLOR_TEXT_MUTED)
        self.actualizar_datos()

    def actualizar_datos(self):
        for w in self.scroll.winfo_children():
            w.destroy()

        if self.pestana == "Tickets de Venta":
            self._renderizar_ventas()
        else:
            self._renderizar_movimiento_inventario()
        self.acc.aplicar_a_widget(self)

    def _renderizar_ventas(self):
        ventas = self.db.ejecutar_consulta(
            """
            SELECT v.ventaId, v.ventaFecha, u.usuarioNombre, v.ventaCorteId,
                   v.ventaMetodoPago, v.ventaTotal, v.ventaMontoRecibido, v.ventaCambio, v.ventaEstado
            FROM venta v
            JOIN usuario u ON u.usuarioId = v.ventaUsuarioId
            ORDER BY v.ventaId DESC LIMIT 60
            """,
            fetch=True
        ) or []

        headers = ["Folio", "Fecha y Hora", "Cajero", "Método", "Total", "Pagó Con", "Cambio", "Ticket"]
        for c_idx, h in enumerate(headers):
            ctk.CTkLabel(self.scroll, text=h, font=("Helvetica", 11, "bold"), text_color=COLOR_TEXT_MUTED).grid(row=0, column=c_idx, padx=10, pady=8, sticky="w")

        if not ventas:
            ctk.CTkLabel(self.scroll, text="Aún no hay ventas registradas.", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(row=1, column=0, columnspan=8, pady=24)
            return

        for r_idx, v in enumerate(ventas, start=1):
            ctk.CTkLabel(self.scroll, text=f"#V-{v['ventaId']:05d}", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).grid(row=r_idx, column=0, padx=10, pady=7, sticky="w")
            ctk.CTkLabel(self.scroll, text=str(v["ventaFecha"])[:19], font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED).grid(row=r_idx, column=1, padx=10, sticky="w")
            ctk.CTkLabel(self.scroll, text=v["usuarioNombre"], font=("Helvetica", 11, "bold"), text_color=COLOR_PRIMARY).grid(row=r_idx, column=2, padx=10, sticky="w")
            ctk.CTkLabel(self.scroll, text=v["ventaMetodoPago"], font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED).grid(row=r_idx, column=3, padx=10, sticky="w")
            ctk.CTkLabel(self.scroll, text=f"${float(v['ventaTotal']):,.2f}", font=("Helvetica", 12, "bold"), text_color=COLOR_SUCCESS_TXT).grid(row=r_idx, column=4, padx=10, sticky="w")
            ctk.CTkLabel(self.scroll, text=f"${float(v['ventaMontoRecibido']):,.2f}", font=("Helvetica", 11), text_color=COLOR_PRIMARY).grid(row=r_idx, column=5, padx=10, sticky="w")
            ctk.CTkLabel(self.scroll, text=f"${float(v['ventaCambio']):,.2f}", font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED).grid(row=r_idx, column=6, padx=10, sticky="w")

            ctk.CTkButton(
                self.scroll, text="Ver Ticket", width=90, height=30,
                fg_color="transparent", border_width=1, border_color=COLOR_BORDER, text_color=COLOR_PRIMARY,
                font=("Helvetica", 11, "bold"),
                command=lambda venta=v: self._reabrir_ticket_venta(venta)
            ).grid(row=r_idx, column=7, padx=10, sticky="w")

    def _reabrir_ticket_venta(self, venta: dict):
        detalles = self.db.ejecutar_consulta(
            """
            SELECT dv.detalleVentaCantidadVendida, dv.detalleVentaPrecioUnitario, dv.detalleVentaSubtotal,
                   p.productoNombre
            FROM detalle_venta dv
            JOIN producto p ON p.productoId = dv.detalleVentaProductoId
            WHERE dv.detalleVentaVentaId = %s
            """,
            (venta["ventaId"],),
            fetch=True
        ) or []

        lineas = [
            "==========================================",
            "            ABARROTES LUPITA              ",
            "        REIMPRESIÓN TICKET DE VENTA       ",
            "==========================================",
            f"Folio Venta : #V-{venta['ventaId']:05d}",
            f"Fecha y Hora: {str(venta['ventaFecha'])[:19]}",
            f"Cajero      : {venta['usuarioNombre']} (Corte #{venta['ventaCorteId']})",
            f"Método Pago : {venta['ventaMetodoPago']}",
            "------------------------------------------",
            "CANT  DESCRIPCIÓN            IMPORTE",
            "------------------------------------------",
        ]
        for d in detalles:
            nom = d["productoNombre"][:20].ljust(20)
            lineas.append(f"{int(d['detalleVentaCantidadVendida']):>3}x  {nom}  ${float(d['detalleVentaSubtotal']):>9,.2f}")
            lineas.append(f"      (${float(d['detalleVentaPrecioUnitario']):,.2f} c/u)")
        lineas.extend([
            "------------------------------------------",
            f"TOTAL A PAGAR :              ${float(venta['ventaTotal']):>10,.2f}",
            f"PAGÓ CON      :              ${float(venta['ventaMontoRecibido']):>10,.2f}",
            f"CAMBIO (FERIA):              ${float(venta['ventaCambio']):>10,.2f}",
            "==========================================",
        ])
        mostrar_modal_ticket(
            self,
            f"Ticket de Venta #V-{venta['ventaId']:05d}",
            "\n".join(lineas),
            f"ticket_venta_{venta['ventaId']}.txt"
        )

    def _renderizar_movimiento_inventario(self):
        movs = self.db.ejecutar_consulta(
            """
            SELECT m.movimientoInventarioId, m.movimientoInventarioFecha, p.productoNombre,
                   m.movimientoInventarioTipo, m.movimientoInventarioCantidad,
                   u.usuarioNombre, m.movimientoInventarioReferencia
            FROM movimiento_inventario m
            JOIN producto p ON p.productoId = m.movimientoInventarioProductoId
            LEFT JOIN usuario u ON u.usuarioId = m.movimientoInventarioUsuarioId
            ORDER BY m.movimientoInventarioId DESC LIMIT 80
            """,
            fetch=True
        ) or []

        headers = ["ID", "Fecha y Hora", "Producto", "Tipo", "Cantidad", "Responsable", "Referencia"]
        for c_idx, h in enumerate(headers):
            ctk.CTkLabel(self.scroll, text=h, font=("Helvetica", 11, "bold"), text_color=COLOR_TEXT_MUTED).grid(row=0, column=c_idx, padx=10, pady=8, sticky="w")

        if not movs:
            ctk.CTkLabel(self.scroll, text="Sin movimientos de inventario registrados.", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(row=1, column=0, columnspan=7, pady=24)
            return

        for r_idx, m in enumerate(movs, start=1):
            es_entrada = (m["movimientoInventarioTipo"] == "ENTRADA")
            ctk.CTkLabel(self.scroll, text=f"#{m['movimientoInventarioId']}", font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED).grid(row=r_idx, column=0, padx=10, pady=6, sticky="w")
            ctk.CTkLabel(self.scroll, text=str(m["movimientoInventarioFecha"])[:19], font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED).grid(row=r_idx, column=1, padx=10, sticky="w")
            ctk.CTkLabel(self.scroll, text=m["productoNombre"], font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).grid(row=r_idx, column=2, padx=10, sticky="w")

            badge = ctk.CTkFrame(self.scroll, fg_color=COLOR_SUCCESS_BG if es_entrada else COLOR_WARN_BG, corner_radius=10)
            badge.grid(row=r_idx, column=3, padx=10, sticky="w")
            ctk.CTkLabel(badge, text=m["movimientoInventarioTipo"], font=("Helvetica", 10, "bold"), text_color=COLOR_SUCCESS_TXT if es_entrada else COLOR_WARN_TXT).pack(padx=8, pady=2)

            signo = "+" if es_entrada else "-"
            ctk.CTkLabel(self.scroll, text=f"{signo}{int(m['movimientoInventarioCantidad']):,} pz", font=("Helvetica", 12, "bold"), text_color=COLOR_SUCCESS_TXT if es_entrada else COLOR_DANGER_TXT).grid(row=r_idx, column=4, padx=10, sticky="w")
            ctk.CTkLabel(self.scroll, text=m["usuarioNombre"] or "Sistema", font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED).grid(row=r_idx, column=5, padx=10, sticky="w")
            ctk.CTkLabel(self.scroll, text=m["movimientoInventarioReferencia"] or "—", font=("Helvetica", 11, "bold"), text_color=COLOR_PRIMARY).grid(row=r_idx, column=6, padx=10, sticky="w")


# ============================================================================
# VISTA 8: EmpleadosView (Gestión de Cuentas y Roles — Solo Administrador)
# ============================================================================
class EmpleadosView(VistaBase):
    def construir_interfaz(self):
        self.pestana_activa = "Empleados"
        self.pestana_botones = {}
        self.empleados_cache = []

        main_box = ctk.CTkFrame(self, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=36, pady=24)

        header_frame = ctk.CTkFrame(main_box, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 14))

        titles = ctk.CTkFrame(header_frame, fg_color="transparent")
        titles.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(titles, text="Gestión de Personal y Turnos", font=("Helvetica", 24, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(titles, text="Administra cuentas de acceso, roles (Administrador / Cajero) y estado del equipo.", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        actions = ctk.CTkFrame(header_frame, fg_color="transparent")
        actions.pack(side="right", anchor="n")
        ctk.CTkButton(actions, text="↻ Actualizar", fg_color=COLOR_PRIMARY, corner_radius=8, height=38, font=("Helvetica", 12, "bold"), command=self.actualizar_datos).pack(side="left", padx=(0, 8))
        ctk.CTkButton(actions, text="+ Agregar empleado", fg_color=COLOR_PRIMARY, hover_color="#0f172a", text_color="white", corner_radius=8, height=38, font=("Helvetica", 12, "bold"), command=self.modal_agregar_empleado).pack(side="left")

        tabs_bar = ctk.CTkFrame(main_box, fg_color="#e9eff5", corner_radius=8, height=40)
        tabs_bar.pack(fill="x", pady=(0, 14))
        tabs_bar.pack_propagate(False)

        for idx, nombre_tab in enumerate(["Empleados", "Turnos hoy"]):
            tabs_bar.grid_columnconfigure(idx, weight=1)
            btn = ctk.CTkButton(
                tabs_bar, text=nombre_tab, corner_radius=6, height=32,
                font=("Helvetica", 12, "bold"),
                command=lambda t=nombre_tab: self._seleccionar_pestana(t)
            )
            btn.grid(row=0, column=idx, padx=4, pady=4, sticky="nsew")
            self.pestana_botones[nombre_tab] = btn

        self.metrics_row = ctk.CTkFrame(main_box, fg_color="transparent")
        self.metrics_row.pack(fill="x", pady=(0, 14))

        table_card = ctk.CTkFrame(main_box, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=12)
        table_card.pack(fill="both", expand=True)

        filter_row = ctk.CTkFrame(table_card, fg_color="transparent")
        filter_row.pack(fill="x", padx=18, pady=(14, 10))

        self.entrada_buscar = ctk.CTkEntry(filter_row, placeholder_text="Buscar por nombre, correo, rol o turno...", height=38, fg_color="#ffffff", border_color=COLOR_BORDER, font=("Helvetica", 12))
        self.entrada_buscar.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.entrada_buscar.bind("<KeyRelease>", lambda e: self._renderizar_contenido())

        self.combo_filtro_estado = ctk.CTkComboBox(
            filter_row, values=["Todos", "Activos", "Inactivos"], state="readonly", width=150, height=38,
            fg_color="#ffffff", border_color=COLOR_BORDER, font=("Helvetica", 12),
            command=lambda _: self._renderizar_contenido()
        )
        self.combo_filtro_estado.set("Todos")
        self.combo_filtro_estado.pack(side="right")

        self.filas_scroll = ctk.CTkScrollableFrame(table_card, fg_color="transparent")
        self.filas_scroll.pack(fill="both", expand=True, padx=18, pady=(4, 8))

        footer_row = ctk.CTkFrame(table_card, fg_color="transparent")
        footer_row.pack(fill="x", padx=18, pady=(4, 12))
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
        ) or []
        self.empleados_cache = usuarios

        for w in self.metrics_row.winfo_children():
            w.destroy()

        total_emp = len(usuarios)
        activos = sum(1 for u in usuarios if int(u["usuarioActivo"]) == 1)
        en_turno = sum(1 for u in usuarios if u.get("corte_abierto") is not None)

        tarjetas = [
            ("Total empleados", f"{total_emp:,}", COLOR_PRIMARY),
            ("Cuentas activas", f"{activos:,}", COLOR_SUCCESS_TXT),
            ("En turno (caja abierta)", f"{en_turno:,}", COLOR_WARN_TXT if en_turno == 0 else COLOR_SUCCESS_TXT),
        ]
        for idx, (titulo, val, col) in enumerate(tarjetas):
            card = ctk.CTkFrame(self.metrics_row, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=10, height=74)
            card.pack(side="left", fill="both", expand=True, padx=(0, 12 if idx < 2 else 0))
            card.pack_propagate(False)
            ctk.CTkLabel(card, text=titulo, font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=16, pady=(9, 0))
            ctk.CTkLabel(card, text=val, font=("Helvetica", 19, "bold"), text_color=col).pack(anchor="w", padx=16)

        self._renderizar_contenido()
        self.acc.aplicar_a_widget(self)

    def _renderizar_contenido(self):
        for w in self.filas_scroll.winfo_children():
            w.destroy()

        if self.pestana_activa == "Turnos hoy":
            self._renderizar_turnos_hoy()
            self.acc.aplicar_a_widget(self.filas_scroll)
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
            ctk.CTkLabel(self.filas_scroll, text=titulo, font=("Helvetica", 11, "bold"), text_color=COLOR_TEXT_MUTED).grid(row=0, column=col_idx, padx=12, pady=10, sticky="w")

        if not filtrados:
            ctk.CTkLabel(self.filas_scroll, text="No se encontraron empleados.", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(row=1, column=0, columnspan=6, pady=24)
            self.lbl_conteo_footer.configure(text=f"Mostrando 0 de {len(self.empleados_cache)} empleados")
            self.acc.aplicar_a_widget(self.filas_scroll)
            return

        usuario_sesion = self.sesion.get_usuario_actual()
        id_actual = usuario_sesion["id"] if usuario_sesion else None

        for row_idx, emp in enumerate(filtrados, start=1):
            activo = int(emp["usuarioActivo"]) == 1
            en_caja = emp.get("corte_abierto") is not None

            ctk.CTkLabel(self.filas_scroll, text=f"{emp['usuarioNombre']} (#{emp['usuarioId']})", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).grid(row=row_idx, column=0, padx=12, pady=9, sticky="w")
            ctk.CTkLabel(self.filas_scroll, text=emp["usuarioCorreo"], font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(row=row_idx, column=1, padx=12, sticky="w")
            ctk.CTkLabel(self.filas_scroll, text=emp["usuarioRol"], font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).grid(row=row_idx, column=2, padx=12, sticky="w")
            ctk.CTkLabel(self.filas_scroll, text=emp["usuarioTurno"] or "Sin asignar", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(row=row_idx, column=3, padx=12, sticky="w")

            if activo and en_caja:
                bg, fg, txt = COLOR_SUCCESS_BG, COLOR_SUCCESS_TXT, "• En turno (Caja)"
            elif activo:
                bg, fg, txt = COLOR_INFO_BG, COLOR_INFO_TXT, "• Activo"
            else:
                bg, fg, txt = COLOR_DANGER_BG, COLOR_DANGER_TXT, "• Inactivo"

            badge = ctk.CTkFrame(self.filas_scroll, fg_color=bg, corner_radius=12)
            badge.grid(row=row_idx, column=4, padx=12, sticky="w")
            ctk.CTkLabel(badge, text=txt, font=("Helvetica", 11, "bold"), text_color=fg).pack(padx=10, pady=2)

            acciones = ctk.CTkFrame(self.filas_scroll, fg_color="transparent")
            acciones.grid(row=row_idx, column=5, padx=10, sticky="w")

            ctk.CTkButton(
                acciones, text="Editar", width=65, height=30,
                fg_color="transparent", border_width=1, border_color=COLOR_BORDER, text_color=COLOR_PRIMARY,
                font=("Helvetica", 11, "bold"),
                command=lambda e=emp: self.modal_editar_empleado(e)
            ).pack(side="left", padx=3)

            if emp["usuarioId"] != id_actual:
                ctk.CTkButton(
                    acciones,
                    text="Desactivar" if activo else "Activar",
                    width=82,
                    height=30,
                    fg_color=COLOR_DANGER_BG if activo else COLOR_SUCCESS_BG,
                    hover_color="#fecaca" if activo else "#a7f3d0",
                    text_color=COLOR_DANGER_TXT if activo else COLOR_SUCCESS_TXT,
                    font=("Helvetica", 11, "bold"),
                    command=lambda e=emp: self.alternar_estado_empleado(e)
                ).pack(side="left", padx=3)

        self.lbl_conteo_footer.configure(text=f"Mostrando {len(filtrados)} de {len(self.empleados_cache)} empleados")
        self.acc.aplicar_a_widget(self.filas_scroll)

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
            ctk.CTkLabel(self.filas_scroll, text=titulo, font=("Helvetica", 11, "bold"), text_color=COLOR_TEXT_MUTED).grid(row=0, column=col_idx, padx=14, pady=10, sticky="w")

        if not cortes_hoy:
            ctk.CTkLabel(self.filas_scroll, text="No hay aperturas de caja registradas el día de hoy.", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(row=1, column=0, columnspan=5, pady=24)
            self.lbl_conteo_footer.configure(text="0 turnos registrados hoy")
            return

        for row_idx, c in enumerate(cortes_hoy, start=1):
            en_curso = int(c["corteEstado"]) == 1
            entrada = str(c["corteFechaApertura"])[11:16]
            salida = str(c["corteFechaCierre"])[11:16] if c["corteFechaCierre"] else "—"

            ctk.CTkLabel(self.filas_scroll, text=c["usuarioNombre"], font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).grid(row=row_idx, column=0, padx=14, pady=9, sticky="w")
            ctk.CTkLabel(self.filas_scroll, text=f"{c['usuarioRol']} • {c['usuarioTurno'] or 'N/A'}", font=("Helvetica", 12), text_color=COLOR_TEXT_MUTED).grid(row=row_idx, column=1, padx=14, sticky="w")
            ctk.CTkLabel(self.filas_scroll, text=entrada, font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).grid(row=row_idx, column=2, padx=14, sticky="w")
            ctk.CTkLabel(self.filas_scroll, text=salida, font=("Helvetica", 12), text_color=COLOR_PRIMARY if salida != "—" else COLOR_TEXT_MUTED).grid(row=row_idx, column=3, padx=14, sticky="w")

            badge = ctk.CTkFrame(self.filas_scroll, fg_color=COLOR_SUCCESS_BG if en_curso else "#e2e8f0", corner_radius=12)
            badge.grid(row=row_idx, column=4, padx=14, sticky="w")
            ctk.CTkLabel(badge, text="• En turno" if en_curso else "• Finalizado", font=("Helvetica", 11, "bold"), text_color=COLOR_SUCCESS_TXT if en_curso else COLOR_PRIMARY).pack(padx=10, pady=2)

        self.lbl_conteo_footer.configure(text=f"Mostrando {len(cortes_hoy)} registros de turno hoy")

    def modal_agregar_empleado(self):
        if not self.sesion.es_admin():
            messagebox.showerror("Acceso denegado", "Solo el Administrador puede registrar empleados.")
            return
        self._abrir_formulario_empleado()

    def modal_editar_empleado(self, empleado):
        if not self.sesion.es_admin():
            messagebox.showerror("Acceso denegado", "Solo el Administrador puede editar empleados.")
            return
        self._abrir_formulario_empleado(empleado)

    def _abrir_formulario_empleado(self, empleado=None):
        es_edicion = empleado is not None
        factor_ventana = min(self.acc.escala, 1.25)
        modal = ctk.CTkToplevel(self)
        modal.title("Editar empleado" if es_edicion else "Nuevo empleado")
        modal.geometry(f"{int(440 * factor_ventana)}x{int(560 * factor_ventana)}")
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
        ent_nombre = ctk.CTkEntry(inner, placeholder_text="Ej. Carlos Pérez", height=38, font=("Helvetica", 12))
        ent_nombre.pack(fill="x")
        if es_edicion:
            ent_nombre.insert(0, empleado["usuarioNombre"])

        ctk.CTkLabel(inner, text="Correo electrónico (acceso)", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(10, 2))
        ent_correo = ctk.CTkEntry(inner, placeholder_text="Ej. cajero1@abarrotes.com", height=38, font=("Helvetica", 12))
        ent_correo.pack(fill="x")
        if es_edicion:
            ent_correo.insert(0, empleado["usuarioCorreo"])

        lbl_pass = "Nueva contraseña (dejar vacío para conservar actual)" if es_edicion else "Contraseña"
        ctk.CTkLabel(inner, text=lbl_pass, font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(10, 2))
        ent_pass = ctk.CTkEntry(inner, placeholder_text="********", show="*", height=38, font=("Helvetica", 12))
        ent_pass.pack(fill="x")

        ctk.CTkLabel(inner, text="Rol en el sistema", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(10, 2))
        combo_rol = ctk.CTkComboBox(inner, values=["Cajero", "Administrador", "Almacen"], state="readonly", height=38, font=("Helvetica", 12))
        combo_rol.pack(fill="x")
        combo_rol.set(empleado["usuarioRol"] if es_edicion else "Cajero")

        ctk.CTkLabel(inner, text="Turno asignado", font=("Helvetica", 12, "bold"), text_color=COLOR_PRIMARY).pack(anchor="w", pady=(10, 2))
        combo_turno = ctk.CTkComboBox(inner, values=["Matutino", "Vespertino", "Nocturno"], state="readonly", height=38, font=("Helvetica", 12))
        combo_turno.pack(fill="x")
        combo_turno.set(empleado["usuarioTurno"] if (es_edicion and empleado["usuarioTurno"]) else "Matutino")

        def guardar():
            if not self.sesion.es_admin():
                messagebox.showerror("Acceso denegado", "Solo el Administrador puede guardar empleados.")
                return
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
            fg_color=COLOR_PRIMARY, hover_color="#0f172a", height=42,
            font=("Helvetica", 12, "bold"), command=guardar
        ).pack(fill="x", pady=(22, 0))

        self.acc.aplicar_a_widget(modal)

    def alternar_estado_empleado(self, empleado):
        if not self.sesion.es_admin():
            messagebox.showerror("Acceso denegado", "Solo el Administrador puede activar o desactivar cuentas.")
            return
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


# ============================================================================
# CLASE 5: MainDashboardView (Controlador de Navegación y Accesibilidad)
# ============================================================================
class MainDashboardView(VistaBase):
    PERMISOS_POR_ROL = {
        "Administrador": [
            "Punto de venta",
            "Corte de caja",
            "Compras",
            "Productos",
            "Proveedores",
            "Movimiento Inventario",
            "Empleados"
        ],
        "Cajero": [
            "Punto de venta",
            "Corte de caja"
        ],
        "Almacen": [
            "Productos",
            "Proveedores"
        ],
    }

    def construir_interfaz(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, fg_color=COLOR_SIDEBAR, width=255, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        self.content_area = ctk.CTkFrame(self, fg_color=COLOR_BG_PANEL, corner_radius=0)
        self.content_area.grid(row=0, column=1, sticky="nsew")
        self.content_area.grid_rowconfigure(0, weight=1)
        self.content_area.grid_columnconfigure(0, weight=1)

        self.vistas = {
            "Punto de venta": PuntoDeVentaView(self.content_area, self.controller),
            "Corte de caja": CorteCajaView(self.content_area, self.controller),
            "Compras": ComprasView(self.content_area, self.controller),
            "Productos": ProductosView(self.content_area, self.controller),
            "Proveedores": ProveedoresView(self.content_area, self.controller),
            "Movimiento Inventario": HistorialMovimientoInventarioView(self.content_area, self.controller),
            "Empleados": EmpleadosView(self.content_area, self.controller),
        }
        for view in self.vistas.values():
            view.grid(row=0, column=0, sticky="nsew")

        self.nav_buttons = {}
        self.setup_sidebar()

    def setup_sidebar(self):
        title_box = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        title_box.pack(fill="x", pady=(22, 12), padx=20)
        ctk.CTkLabel(title_box, text="Abarrotes Lupita", font=("Helvetica", 18, "bold"), text_color=COLOR_PRIMARY).pack(side="left")
        ctk.CTkFrame(self.sidebar, fg_color="#475569", height=2).pack(fill="x", pady=(0, 10))

        self.menu_container = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.menu_container.pack(fill="x")

        self.btn_actualizar_todo = ctk.CTkButton(
            self.sidebar, text="↻ Actualizar todo", fg_color=COLOR_PRIMARY,
            text_color="white", hover_color="#0f172a", height=38,
            font=("Helvetica", 12, "bold"),
            command=self.actualizar_catalogos
        )
        self.btn_actualizar_todo.pack(fill="x", padx=15, pady=(12, 8))

        # Control de accesibilidad de tamaño de letra en la barra lateral
        acc_card = ctk.CTkFrame(self.sidebar, fg_color="#dce4f2", corner_radius=8)
        acc_card.pack(fill="x", padx=15, pady=(4, 8))
        barra_acc = crear_barra_accesibilidad(acc_card, fg_color="transparent")
        barra_acc.pack(pady=4)

        self.footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.footer.pack(side="bottom", fill="x", padx=20, pady=20)
        ctk.CTkLabel(self.footer, text="Sesión activa", font=("Helvetica", 11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        self.lbl_usuario = ctk.CTkLabel(self.footer, text="", font=("Helvetica", 13, "bold"), text_color=COLOR_PRIMARY)
        self.lbl_usuario.pack(anchor="w")

        self.lbl_rol = ctk.CTkLabel(self.footer, text="", font=("Helvetica", 11, "bold"), text_color="#1e293b")
        self.lbl_rol.pack(anchor="w", pady=(0, 6))

        ctk.CTkButton(
            self.footer,
            text="Cerrar sesión",
            fg_color="transparent",
            text_color="#b91c1c",
            hover_color="#cbd5e1",
            anchor="w",
            font=("Helvetica", 12, "bold"),
            command=self.cerrar_sesion
        ).pack(fill="x", pady=(4, 0))

    def _construir_menu_por_rol(self, rol: str) -> str:
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
                height=42,
                font=("Helvetica", 13, "bold"),
                corner_radius=0,
                command=lambda t=titulo: self.cambiar_vista(t)
            )
            btn.pack(fill="x", pady=1)
            self.nav_buttons[titulo] = btn

        self.acc.aplicar_a_widget(self.menu_container)
        return modulos_permitidos[0]

    def actualizar_datos(self):
        user = self.sesion.get_usuario_actual()
        if not user:
            return
        self.lbl_usuario.configure(text=user["nombre"])
        self.lbl_rol.configure(text=f"Rol: {user['rol']}")
        vista_inicial = self._construir_menu_por_rol(user["rol"])
        self.cambiar_vista(vista_inicial)
        self.acc.aplicar_a_widget(self)

    def actualizar_catalogos(self):
        user = self.sesion.get_usuario_actual()
        permitidas = self.PERMISOS_POR_ROL.get(user["rol"], []) if user else list(self.vistas.keys())
        for nombre in permitidas:
            vista = self.vistas.get(nombre)
            if vista is not None:
                vista.actualizar_datos()
        self.acc.aplicar_a_widget(self)

    def cambiar_vista(self, nombre_vista: str):
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
        self.acc.aplicar_a_widget(self)

    def cerrar_sesion(self):
        self.sesion.cerrar_sesion()
        self.controller.mostrar_login()


# ============================================================================
# CLASE 6: SistemaAbarrotesApp (Ventana Principal de la Aplicación)
# ============================================================================
class SistemaAbarrotesApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Sistema de Punto de Venta - Abarrotes Lupita")
        self.geometry("1320x820")
        self.minsize(1100, 700)
        self.configure(fg_color=COLOR_BG_PANEL)

        self.acc = AccesibilidadManager()
        self.acc.registrar_observador(self._al_cambiar_escala_letra)

        # Atajos de teclado para aumentar/disminuir tamaño de letra (Ctrl + y Ctrl -)
        self.bind("<Control-plus>", lambda e: self.acc.aumentar_letra())
        self.bind("<Control-equal>", lambda e: self.acc.aumentar_letra())
        self.bind("<Control-minus>", lambda e: self.acc.disminuir_letra())

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.login_view = LoginView(self.container, self)
        self.dashboard_view = MainDashboardView(self.container, self)

        self.login_view.grid(row=0, column=0, sticky="nsew")
        self.dashboard_view.grid(row=0, column=0, sticky="nsew")

        self.mostrar_login()

    def _al_cambiar_escala_letra(self):
        """Reescala el ancho de la barra lateral y todas las fuentes activas."""
        nuevo_ancho_sidebar = int(round(255 * (1.0 + (self.acc.escala - 1.0) * 0.55)))
        self.dashboard_view.sidebar.configure(width=nuevo_ancho_sidebar)
        self.acc.aplicar_a_widget(self)

    def iniciar_dashboard(self):
        self.dashboard_view.actualizar_datos()
        self.dashboard_view.tkraise()

    def mostrar_login(self):
        self.login_view.actualizar_datos()
        self.login_view.tkraise()


if __name__ == "__main__":
    app = SistemaAbarrotesApp()
    app.mainloop()