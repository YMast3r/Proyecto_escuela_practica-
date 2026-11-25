-- ============================================================================
-- BASE DE DATOS: abarrotes (Sistema Punto de Venta - Abarrotes Lupita)
-- Compatible con MySQL / MariaDB en XAMPP
-- ============================================================================
-- Reglas de negocio implementadas en el esquema:
--   1. Control de acceso por roles (Administrador, Cajero, Almacen).
--   2. Corte de caja diario con fondo inicial, ventas en efectivo/tarjeta y
--      descuento automático de compras pagadas con efectivo de la caja.
--   3. Registro de ventas con monto recibido ("Paga con") y cambio ("Feria").
--   4. Registro de compras a proveedores con ticket, fecha, método de pago y
--      trazabilidad completa en la bitácora (movimiento_inventario).
-- ============================================================================

CREATE DATABASE IF NOT EXISTS `abarrotes`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;

USE `abarrotes`;

-- ============================================================================
-- 1. EMPLEADOS Y USUARIOS DEL SISTEMA
-- ============================================================================
CREATE TABLE IF NOT EXISTS `usuario` (
  `usuarioId`         INT AUTO_INCREMENT PRIMARY KEY,
  `usuarioNombre`     VARCHAR(100) NOT NULL,
  `usuarioCorreo`     VARCHAR(100) NOT NULL UNIQUE,
  `usuarioContraseña` VARCHAR(255) NOT NULL, -- Almacenar siempre con hash seguro (bcrypt / PBKDF2)
  `usuarioRol`        ENUM('Administrador', 'Cajero', 'Almacen') NOT NULL DEFAULT 'Cajero',
  `usuarioTurno`      ENUM('Matutino', 'Vespertino', 'Nocturno') DEFAULT NULL,
  `usuarioActivo`     TINYINT(1) NOT NULL DEFAULT 1 -- 1 = activo, 0 = inactivo
) ENGINE=InnoDB;

-- ============================================================================
-- 2. PROVEEDORES E INVENTARIO
-- ============================================================================
CREATE TABLE IF NOT EXISTS `proveedor` (
  `proveedorId`            INT AUTO_INCREMENT PRIMARY KEY,
  `proveedorNombreEmpresa` VARCHAR(100) NOT NULL,
  `proveedorTelefono`      VARCHAR(20) DEFAULT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `producto` (
  `productoId`           INT AUTO_INCREMENT PRIMARY KEY,
  `productoCodigoBarras` VARCHAR(50) UNIQUE,
  `productoNombre`       VARCHAR(100) NOT NULL,
  `productoProveedorId`  INT DEFAULT NULL,
  `productoPrecioCompra` DECIMAL(10,2) DEFAULT NULL,
  `productoPrecioVenta`  DECIMAL(10,2) NOT NULL,
  `productoStockActual`  INT NOT NULL DEFAULT 0, -- Solo aumenta mediante Compras o Cancelaciones
  `productoStockMinimo`  INT NOT NULL DEFAULT 0,
  FOREIGN KEY (`productoProveedorId`) REFERENCES `proveedor`(`proveedorId`)
) ENGINE=InnoDB;

-- ============================================================================
-- 3. CORTE DE CAJA (Turnos diarios)
-- ============================================================================
-- Fórmula del efectivo esperado al cierre:
--   corteEfectivoEsperado = corteFondoInicial + corteVentasEfectivo - corteComprasEfectivo
CREATE TABLE IF NOT EXISTS `corte` (
  `corteId`               INT AUTO_INCREMENT PRIMARY KEY,
  `corteUsuarioId`        INT NOT NULL,
  `corteFechaApertura`    DATETIME NOT NULL,
  `corteFechaCierre`      DATETIME DEFAULT NULL,
  `corteFondoInicial`     DECIMAL(10,2) NOT NULL,
  `corteVentasEfectivo`   DECIMAL(10,2) DEFAULT 0.00, -- Acumulado de ventas en efectivo del turno
  `corteVentasTarjeta`    DECIMAL(10,2) DEFAULT 0.00, -- Acumulado de ventas con tarjeta del turno
  `corteComprasEfectivo`  DECIMAL(10,2) DEFAULT 0.00, -- Compras pagadas sacando efectivo de la caja
  `corteEfectivoEsperado` DECIMAL(10,2) DEFAULT NULL, -- Fondo + Ventas Efectivo - Compras Efectivo
  `corteEfectivoContado`  DECIMAL(10,2) DEFAULT NULL, -- Dinero físico contado al cerrar
  `corteDiferencia`       DECIMAL(10,2) DEFAULT NULL, -- Contado - Esperado (0 = cuadrado)
  `corteEstado`           TINYINT(1) NOT NULL DEFAULT 1, -- 1 = abierto, 0 = cerrado
  `corteObservaciones`    VARCHAR(255) DEFAULT NULL,
  FOREIGN KEY (`corteUsuarioId`) REFERENCES `usuario`(`usuarioId`)
) ENGINE=InnoDB;

-- ============================================================================
-- 4. COMPRAS / SURTIDO DE PROVEEDORES (Entradas de mercancía con ticket y fecha)
-- ============================================================================
CREATE TABLE IF NOT EXISTS `compra` (
  `compraId`          INT AUTO_INCREMENT PRIMARY KEY,
  `compraFecha`       DATETIME NOT NULL,
  `compraProveedorId` INT NOT NULL,
  `compraUsuarioId`   INT NOT NULL,
  `compraCorteId`     INT DEFAULT NULL, -- Se vincula al corte abierto si se pagó con 'Efectivo Caja'
  `compraMetodoPago`  ENUM('Efectivo Caja', 'Transferencia / Externo') NOT NULL DEFAULT 'Efectivo Caja',
  `compraTotal`       DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  `compraNotas`       VARCHAR(255) DEFAULT NULL,
  FOREIGN KEY (`compraProveedorId`) REFERENCES `proveedor`(`proveedorId`),
  FOREIGN KEY (`compraUsuarioId`)   REFERENCES `usuario`(`usuarioId`),
  FOREIGN KEY (`compraCorteId`)     REFERENCES `corte`(`corteId`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `detalle_compra` (
  `detalleCompraId`            INT AUTO_INCREMENT PRIMARY KEY,
  `detalleCompraCompraId`      INT NOT NULL,
  `detalleCompraProductoId`    INT NOT NULL,
  `detalleCompraCantidad`      INT NOT NULL,
  `detalleCompraCostoUnitario` DECIMAL(10,2) NOT NULL,
  `detalleCompraSubtotal`      DECIMAL(10,2) NOT NULL,
  FOREIGN KEY (`detalleCompraCompraId`)   REFERENCES `compra`(`compraId`) ON DELETE CASCADE,
  FOREIGN KEY (`detalleCompraProductoId`) REFERENCES `producto`(`productoId`)
) ENGINE=InnoDB;

-- ============================================================================
-- 5. BITÁCORA DE MOVIMIENTOS DE INVENTARIO (Kardex)
-- ============================================================================
-- Tipo: ENTRADA (compra a proveedor, cancelación de venta)
--       SALIDA  (venta en mostrador)
CREATE TABLE IF NOT EXISTS `movimiento_inventario` (
  `movimientoInventarioId`         INT AUTO_INCREMENT PRIMARY KEY,
  `movimientoInventarioProductoId` INT NOT NULL,
  `movimientoInventarioTipo`       ENUM('ENTRADA', 'SALIDA') NOT NULL,
  `movimientoInventarioCantidad`   INT NOT NULL,
  `movimientoInventarioFecha`      DATETIME NOT NULL,
  `movimientoInventarioUsuarioId`  INT DEFAULT NULL,
  `movimientoInventarioReferencia` VARCHAR(100) DEFAULT NULL, -- ej. 'compra #1', 'venta #12'
  FOREIGN KEY (`movimientoInventarioProductoId`) REFERENCES `producto`(`productoId`),
  FOREIGN KEY (`movimientoInventarioUsuarioId`)  REFERENCES `usuario`(`usuarioId`)
) ENGINE=InnoDB;

-- ============================================================================
-- 6. VENTAS EN MOSTRADOR (Con pago recibido y cálculo de cambio / feria)
-- ============================================================================
CREATE TABLE IF NOT EXISTS `venta` (
  `ventaId`            INT AUTO_INCREMENT PRIMARY KEY,
  `ventaFecha`         DATETIME NOT NULL,
  `ventaUsuarioId`     INT NOT NULL,
  `ventaCorteId`       INT NOT NULL,
  `ventaMetodoPago`    ENUM('Efectivo', 'Tarjeta') NOT NULL DEFAULT 'Efectivo',
  `ventaTotal`         DECIMAL(10,2) NOT NULL,
  `ventaMontoRecibido` DECIMAL(10,2) NOT NULL DEFAULT 0.00, -- Con cuánto pagó el cliente
  `ventaCambio`        DECIMAL(10,2) NOT NULL DEFAULT 0.00, -- Cambio (feria) devuelto
  `ventaEstado`        ENUM('Completada', 'Cancelada') NOT NULL DEFAULT 'Completada',
  FOREIGN KEY (`ventaUsuarioId`) REFERENCES `usuario`(`usuarioId`),
  FOREIGN KEY (`ventaCorteId`)   REFERENCES `corte`(`corteId`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `detalle_venta` (
  `detalleVentaId`              INT AUTO_INCREMENT PRIMARY KEY,
  `detalleVentaVentaId`         INT NOT NULL,
  `detalleVentaProductoId`      INT NOT NULL,
  `detalleVentaCantidadVendida` INT NOT NULL,
  `detalleVentaPrecioUnitario`  DECIMAL(10,2) NOT NULL,
  `detalleVentaSubtotal`        DECIMAL(10,2) NOT NULL,
  FOREIGN KEY (`detalleVentaVentaId`)    REFERENCES `venta`(`ventaId`) ON DELETE CASCADE,
  FOREIGN KEY (`detalleVentaProductoId`) REFERENCES `producto`(`productoId`)
) ENGINE=InnoDB;

-- ============================================================================
-- 7. DATOS INICIALES DE EJEMPLO
-- ============================================================================
-- Nota: Al iniciar sesión por primera vez con contraseña '123', tienda.py la
-- migrará automáticamente a un hash seguro (bcrypt / PBKDF2-SHA256).
INSERT INTO `usuario` (`usuarioNombre`, `usuarioCorreo`, `usuarioContraseña`, `usuarioRol`, `usuarioTurno`, `usuarioActivo`) VALUES
('Juan', 'Juan@Gmail.com', '123', 'Administrador', 'Matutino', 1),
('Carlos Cajero', 'cajero@abarrotes.com', '123', 'Cajero', 'Matutino', 1);

INSERT INTO `proveedor` (`proveedorNombreEmpresa`, `proveedorTelefono`) VALUES
('Pepsi', '4491774574'),
('Bimbo', '4491234567');

INSERT INTO `producto` (`productoCodigoBarras`, `productoNombre`, `productoProveedorId`, `productoPrecioCompra`, `productoPrecioVenta`, `productoStockActual`, `productoStockMinimo`) VALUES
('123456789', 'Pepsi 3L', 1, 34.00, 40.00, 10, 3),
('7501000111222', 'Pan Blanco Grande Bimbo', 2, 38.00, 46.00, 8, 2);

INSERT INTO `compra` (`compraFecha`, `compraProveedorId`, `compraUsuarioId`, `compraCorteId`, `compraMetodoPago`, `compraTotal`, `compraNotas`) VALUES
(NOW(), 1, 1, NULL, 'Transferencia / Externo', 340.00, 'Inventario inicial Pepsi'),
(NOW(), 2, 1, NULL, 'Transferencia / Externo', 304.00, 'Inventario inicial Bimbo');

INSERT INTO `detalle_compra` (`detalleCompraCompraId`, `detalleCompraProductoId`, `detalleCompraCantidad`, `detalleCompraCostoUnitario`, `detalleCompraSubtotal`) VALUES
(1, 1, 10, 34.00, 340.00),
(2, 2, 8, 38.00, 304.00);

INSERT INTO `movimiento_inventario` (`movimientoInventarioProductoId`, `movimientoInventarioTipo`, `movimientoInventarioCantidad`, `movimientoInventarioFecha`, `movimientoInventarioUsuarioId`, `movimientoInventarioReferencia`) VALUES
(1, 'ENTRADA', 10, NOW(), 1, 'compra #1'),
(2, 'ENTRADA', 8, NOW(), 1, 'compra #2');
