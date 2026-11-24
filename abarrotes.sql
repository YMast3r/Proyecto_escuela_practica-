-- Base de datos simplificada: abarrotes
-- Objetivos: inventario, corte de caja y control de empleados
-- Tablas: 9
-- Convención: cada columna = nombre de la tabla + Campo en camelCase
--   ej. usuarioId, usuarioContraseña, productoPrecioVenta
--   Las llaves foráneas llevan el prefijo de su propia tabla + tabla referenciada
--   ej. compraUsuarioId (en compra, apunta a usuario.usuarioId)

CREATE DATABASE IF NOT EXISTS `abarrotes` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE `abarrotes`;

-- ============================================================
-- EMPLEADOS
-- ============================================================
CREATE TABLE `usuario` (
  `usuarioId`         INT AUTO_INCREMENT PRIMARY KEY,
  `usuarioNombre`     VARCHAR(100) NOT NULL,
  `usuarioCorreo`     VARCHAR(100) NOT NULL UNIQUE,
  `usuarioContraseña` VARCHAR(255) NOT NULL,       -- guardar con password_hash(), nunca texto plano
  `usuarioRol`        ENUM('Administrador','Cajero','Almacen') NOT NULL DEFAULT 'Cajero',
  `usuarioTurno`      ENUM('Matutino','Vespertino','Nocturno') DEFAULT NULL,
  `usuarioActivo`     TINYINT(1) NOT NULL DEFAULT 1 -- 1 = activo, 0 = inactivo
) ENGINE=InnoDB;

-- ============================================================
-- INVENTARIO
-- ============================================================
CREATE TABLE `proveedor` (
  `proveedorId`            INT AUTO_INCREMENT PRIMARY KEY,
  `proveedorNombreEmpresa` VARCHAR(100) NOT NULL,
  `proveedorTelefono`      VARCHAR(20) DEFAULT NULL
) ENGINE=InnoDB;

CREATE TABLE `producto` (
  `productoId`           INT AUTO_INCREMENT PRIMARY KEY,
  `productoCodigoBarras` VARCHAR(50) UNIQUE,
  `productoNombre`       VARCHAR(100) NOT NULL,
  `productoProveedorId`  INT DEFAULT NULL,
  `productoPrecioCompra` DECIMAL(10,2) DEFAULT NULL,
  `productoPrecioVenta`  DECIMAL(10,2) NOT NULL,
  `productoStockActual`  INT NOT NULL DEFAULT 0,
  `productoStockMinimo`  INT NOT NULL DEFAULT 0,
  FOREIGN KEY (`productoProveedorId`) REFERENCES `proveedor`(`proveedorId`)
) ENGINE=InnoDB;

-- Compras (entradas de mercancía)
CREATE TABLE `compra` (
  `compraId`          INT AUTO_INCREMENT PRIMARY KEY,
  `compraFecha`       DATETIME NOT NULL,
  `compraProveedorId` INT NOT NULL,
  `compraUsuarioId`   INT NOT NULL,
  `compraTotal`       DECIMAL(10,2) DEFAULT NULL,
  FOREIGN KEY (`compraProveedorId`) REFERENCES `proveedor`(`proveedorId`),
  FOREIGN KEY (`compraUsuarioId`)   REFERENCES `usuario`(`usuarioId`)
) ENGINE=InnoDB;

CREATE TABLE `detalle_compra` (
  `detalleCompraId`            INT AUTO_INCREMENT PRIMARY KEY,
  `detalleCompraCompraId`      INT NOT NULL,
  `detalleCompraProductoId`    INT NOT NULL,
  `detalleCompraCantidad`      INT NOT NULL,
  `detalleCompraCostoUnitario` DECIMAL(10,2) NOT NULL,
  FOREIGN KEY (`detalleCompraCompraId`)   REFERENCES `compra`(`compraId`) ON DELETE CASCADE,
  FOREIGN KEY (`detalleCompraProductoId`) REFERENCES `producto`(`productoId`)
) ENGINE=InnoDB;

-- Bitácora de entradas y salidas de inventario
-- tipo: ENTRADA (compra, ajuste +) / SALIDA (venta, merma, ajuste -)
CREATE TABLE `movimiento_inventario` (
  `movimientoInventarioId`         INT AUTO_INCREMENT PRIMARY KEY,
  `movimientoInventarioProductoId` INT NOT NULL,
  `movimientoInventarioTipo`       ENUM('ENTRADA','SALIDA') NOT NULL,
  `movimientoInventarioCantidad`   INT NOT NULL,
  `movimientoInventarioFecha`      DATETIME NOT NULL,
  `movimientoInventarioUsuarioId`  INT DEFAULT NULL,
  `movimientoInventarioReferencia` VARCHAR(100) DEFAULT NULL, -- ej. 'compra #3', 'venta #12', 'merma'
  FOREIGN KEY (`movimientoInventarioProductoId`) REFERENCES `producto`(`productoId`),
  FOREIGN KEY (`movimientoInventarioUsuarioId`)  REFERENCES `usuario`(`usuarioId`)
) ENGINE=InnoDB;

-- ============================================================
-- CORTE DE CAJA
-- ============================================================
CREATE TABLE `corte` (
  `corteId`               INT AUTO_INCREMENT PRIMARY KEY,
  `corteUsuarioId`        INT NOT NULL,
  `corteFechaApertura`    DATETIME NOT NULL,
  `corteFechaCierre`      DATETIME DEFAULT NULL,
  `corteFondoInicial`     DECIMAL(10,2) NOT NULL,
  `corteEfectivoEsperado` DECIMAL(10,2) DEFAULT NULL,  -- fondo + ventas en efectivo
  `corteEfectivoContado`  DECIMAL(10,2) DEFAULT NULL,
  `corteDiferencia`       DECIMAL(10,2) DEFAULT NULL,  -- contado - esperado
  `corteEstado`           TINYINT(1) NOT NULL DEFAULT 1, -- 1 = abierto, 0 = cerrado
  FOREIGN KEY (`corteUsuarioId`) REFERENCES `usuario`(`usuarioId`)
) ENGINE=InnoDB;

-- ============================================================
-- VENTAS
-- ============================================================
CREATE TABLE `venta` (
  `ventaId`         INT AUTO_INCREMENT PRIMARY KEY,
  `ventaFecha`      DATETIME NOT NULL,
  `ventaUsuarioId`  INT NOT NULL,
  `ventaCorteId`    INT DEFAULT NULL,
  `ventaMetodoPago` ENUM('Efectivo','Tarjeta') NOT NULL DEFAULT 'Efectivo',
  `ventaTotal`      DECIMAL(10,2) NOT NULL,
  FOREIGN KEY (`ventaUsuarioId`) REFERENCES `usuario`(`usuarioId`),
  FOREIGN KEY (`ventaCorteId`)   REFERENCES `corte`(`corteId`)
) ENGINE=InnoDB;

CREATE TABLE `detalle_venta` (
  `detalleVentaId`              INT AUTO_INCREMENT PRIMARY KEY,
  `detalleVentaVentaId`         INT NOT NULL,
  `detalleVentaProductoId`      INT NOT NULL,
  `detalleVentaCantidadVendida` INT NOT NULL,
  `detalleVentaPrecioUnitario`  DECIMAL(10,2) NOT NULL,
  `detalleVentaSubtotal`        DECIMAL(10,2) NOT NULL,
  FOREIGN KEY (`detalleVentaVentaId`)    REFERENCES `venta`(`ventaId`) ON DELETE CASCADE,
  FOREIGN KEY (`detalleVentaProductoId`) REFERENCES `producto`(`productoId`)
) ENGINE=InnoDB;

-- ============================================================
-- DATOS DE EJEMPLO
-- ============================================================
INSERT INTO `usuario` (`usuarioNombre`,`usuarioCorreo`,`usuarioContraseña`,`usuarioRol`,`usuarioTurno`,`usuarioActivo`) VALUES
('Juan','Juan@Gmail.com','123','Administrador','Matutino',1);

INSERT INTO `proveedor` (`proveedorNombreEmpresa`,`proveedorTelefono`) VALUES ('Pepsi','4491774574');

INSERT INTO `producto` (`productoCodigoBarras`,`productoNombre`,`productoProveedorId`,`productoPrecioCompra`,`productoPrecioVenta`,`productoStockActual`,`productoStockMinimo`) VALUES
('123456789','Pepsi 3L',1,34.00,40.00,2,0);

-- ============================================================
-- CONSULTAS ÚTILES
-- ============================================================
-- Empleados y su estado:
--   SELECT usuarioNombre, usuarioRol, usuarioTurno,
--          IF(usuarioActivo=1,'Activo','Inactivo') AS estado
--   FROM usuario;
-- Productos bajo stock mínimo:
--   SELECT productoNombre, productoStockActual, productoStockMinimo
--   FROM producto WHERE productoStockActual <= productoStockMinimo;
-- Efectivo esperado de un corte:
--   SELECT c.corteFondoInicial + COALESCE(SUM(v.ventaTotal),0)
--   FROM corte c
--   LEFT JOIN venta v ON v.ventaCorteId = c.corteId AND v.ventaMetodoPago = 'Efectivo'
--   WHERE c.corteId = ? GROUP BY c.corteId;
