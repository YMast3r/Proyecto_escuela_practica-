-- Base de datos simplificada: abarrotes
-- Objetivos: inventario, corte de caja y control de empleados
-- Tablas: 9 (antes 15)

CREATE DATABASE IF NOT EXISTS `abarrotes` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE `abarrotes`;

-- ============================================================
-- EMPLEADOS
-- (rol y turno se integran como columnas; se eliminan tablas rol y turno)
-- ============================================================
CREATE TABLE `usuario` (
  `idusuario`    INT AUTO_INCREMENT PRIMARY KEY,
  `nombre`       VARCHAR(100) NOT NULL,
  `correo`       VARCHAR(100) NOT NULL UNIQUE,
  `passwordhash` VARCHAR(255) NOT NULL,            -- guardar con password_hash(), nunca texto plano
  `rol`          ENUM('Administrador','Cajero','Almacen') NOT NULL DEFAULT 'Cajero',
  `turno`        ENUM('Matutino','Vespertino','Nocturno') DEFAULT NULL,
  `activo`       TINYINT(1) NOT NULL DEFAULT 1     -- 1 = activo, 0 = inactivo
) ENGINE=InnoDB;

-- ============================================================
-- INVENTARIO
-- (se eliminan categoria, cliente y metodo_pago)
-- ============================================================
CREATE TABLE `proveedor` (
  `idproveedor`   INT AUTO_INCREMENT PRIMARY KEY,
  `nombreempresa` VARCHAR(100) NOT NULL,
  `telefono`      VARCHAR(20) DEFAULT NULL
) ENGINE=InnoDB;

CREATE TABLE `producto` (
  `idproducto`   INT AUTO_INCREMENT PRIMARY KEY,
  `codigobarras` VARCHAR(50) UNIQUE,
  `nombre`       VARCHAR(100) NOT NULL,
  `idproveedor`  INT DEFAULT NULL,
  `preciocompra` DECIMAL(10,2) DEFAULT NULL,
  `precioventa`  DECIMAL(10,2) NOT NULL,
  `stockactual`  INT NOT NULL DEFAULT 0,
  `stockminimo`  INT NOT NULL DEFAULT 0,
  FOREIGN KEY (`idproveedor`) REFERENCES `proveedor`(`idproveedor`)
) ENGINE=InnoDB;

-- Compras (entradas de mercancía)
CREATE TABLE `compra` (
  `idcompra`    INT AUTO_INCREMENT PRIMARY KEY,
  `fecha`       DATETIME NOT NULL,
  `idproveedor` INT NOT NULL,
  `idusuario`   INT NOT NULL,
  `total`       DECIMAL(10,2) DEFAULT NULL,
  FOREIGN KEY (`idproveedor`) REFERENCES `proveedor`(`idproveedor`),
  FOREIGN KEY (`idusuario`)   REFERENCES `usuario`(`idusuario`)
) ENGINE=InnoDB;

CREATE TABLE `detalle_compra` (
  `iddetallecompra` INT AUTO_INCREMENT PRIMARY KEY,
  `idcompra`        INT NOT NULL,
  `idproducto`      INT NOT NULL,
  `cantidad`        INT NOT NULL,
  `costounitario`   DECIMAL(10,2) NOT NULL,
  FOREIGN KEY (`idcompra`)   REFERENCES `compra`(`idcompra`) ON DELETE CASCADE,
  FOREIGN KEY (`idproducto`) REFERENCES `producto`(`idproducto`)
) ENGINE=InnoDB;

-- Bitácora de entradas y salidas de inventario
-- tipo: ENTRADA (compra, ajuste +) / SALIDA (venta, merma, ajuste -)
CREATE TABLE `movimiento_inventario` (
  `idmovimiento` INT AUTO_INCREMENT PRIMARY KEY,
  `idproducto`   INT NOT NULL,
  `tipo`         ENUM('ENTRADA','SALIDA') NOT NULL,
  `cantidad`     INT NOT NULL,
  `fecha`        DATETIME NOT NULL,
  `idusuario`    INT DEFAULT NULL,
  `referencia`   VARCHAR(100) DEFAULT NULL,        -- ej. 'compra #3', 'venta #12', 'merma'
  FOREIGN KEY (`idproducto`) REFERENCES `producto`(`idproducto`),
  FOREIGN KEY (`idusuario`)  REFERENCES `usuario`(`idusuario`)
) ENGINE=InnoDB;

-- ============================================================
-- CORTE DE CAJA
-- (turno se quita; el corte queda ligado al empleado)
-- ============================================================
CREATE TABLE `corte` (
  `idcorte`          INT AUTO_INCREMENT PRIMARY KEY,
  `idusuario`        INT NOT NULL,
  `fechaapertura`    DATETIME NOT NULL,
  `fechacierre`      DATETIME DEFAULT NULL,
  `fondoinicial`     DECIMAL(10,2) NOT NULL,
  `efectivoesperado` DECIMAL(10,2) DEFAULT NULL,   -- fondo + ventas en efectivo
  `efectivocontado`  DECIMAL(10,2) DEFAULT NULL,
  `diferencia`       DECIMAL(10,2) DEFAULT NULL,   -- contado - esperado
  `estado`           TINYINT(1) NOT NULL DEFAULT 1, -- 1 = abierto, 0 = cerrado
  FOREIGN KEY (`idusuario`) REFERENCES `usuario`(`idusuario`)
) ENGINE=InnoDB;

-- ============================================================
-- VENTAS
-- (metodo de pago como ENUM; sin cliente)
-- ============================================================
CREATE TABLE `venta` (
  `idventa`    INT AUTO_INCREMENT PRIMARY KEY,
  `fecha`      DATETIME NOT NULL,
  `idusuario`  INT NOT NULL,
  `idcorte`    INT DEFAULT NULL,
  `metodopago` ENUM('Efectivo','Tarjeta') NOT NULL DEFAULT 'Efectivo',
  `total`      DECIMAL(10,2) NOT NULL,
  FOREIGN KEY (`idusuario`) REFERENCES `usuario`(`idusuario`),
  FOREIGN KEY (`idcorte`)   REFERENCES `corte`(`idcorte`)
) ENGINE=InnoDB;

CREATE TABLE `detalle_venta` (
  `iddetalle`       INT AUTO_INCREMENT PRIMARY KEY,
  `idventa`         INT NOT NULL,
  `idproducto`      INT NOT NULL,
  `cantidadvendida` INT NOT NULL,
  `preciounitario`  DECIMAL(10,2) NOT NULL,
  `subtotal`        DECIMAL(10,2) NOT NULL,
  FOREIGN KEY (`idventa`)    REFERENCES `venta`(`idventa`) ON DELETE CASCADE,
  FOREIGN KEY (`idproducto`) REFERENCES `producto`(`idproducto`)
) ENGINE=InnoDB;

-- ============================================================
-- DATOS DE EJEMPLO (tomados de tu dump)
-- ============================================================
INSERT INTO `usuario` (`nombre`,`correo`,`passwordhash`,`rol`,`turno`,`activo`) VALUES
('Juan','Juan@Gmail.com','123','Administrador','Matutino',1);

INSERT INTO `proveedor` (`nombreempresa`,`telefono`) VALUES ('Pepsi','4491774574');

INSERT INTO `producto` (`codigobarras`,`nombre`,`idproveedor`,`preciocompra`,`precioventa`,`stockactual`,`stockminimo`) VALUES
('123456789','Pepsi 3L',1,34.00,40.00,2,0);

-- ============================================================
-- CONSULTAS ÚTILES
-- ============================================================
-- Empleados y su estado:
--   SELECT nombre, rol, turno, IF(activo=1,'Activo','Inactivo') AS estado FROM usuario;
-- Productos bajo stock mínimo:
--   SELECT nombre, stockactual, stockminimo FROM producto WHERE stockactual <= stockminimo;
-- Efectivo esperado de un corte:
--   SELECT c.fondoinicial + COALESCE(SUM(v.total),0)
--   FROM corte c LEFT JOIN venta v ON v.idcorte=c.idcorte AND v.metodopago='Efectivo'
--   WHERE c.idcorte = ? GROUP BY c.idcorte;
