"""Operaciones sobre los productos del catálogo que hace el panel de administración."""
from datetime import datetime

from core.database import execute_query, transaccion
from core.imagenes import borrar_archivo
from core.logger import registrar_log


def obtener_producto(id):
    """(id, nombre_estandar, grado, imagen_producto) o None si no existe."""
    return execute_query("SELECT id, nombre_estandar, grado, imagen_producto FROM productos WHERE id = ?", (id,), fetchone=True)


def actualizar_producto(id, nombre, grado):
    execute_query("UPDATE productos SET nombre_estandar = ?, grado = ? WHERE id = ?", (nombre, grado, id), commit=True)
    registrar_log(f"Producto ID {id} modificado en catálogo.")


def alternar_visibilidad(id):
    """Cambia Visible ↔ Oculto. Retorna el nuevo es_visible, o None si el producto no existe."""
    fila = execute_query("SELECT es_visible FROM productos WHERE id = ?", (id,), fetchone=True)
    if not fila:
        return None
    nuevo_estado = 0 if fila[0] == 1 else 1
    execute_query("UPDATE productos SET es_visible = ? WHERE id = ?", (nuevo_estado, id), commit=True)
    registrar_log(f"Visibilidad modificada: Producto ID {id} ahora está {'Oculto' if nuevo_estado == 0 else 'Visible'}")
    return nuevo_estado


def eliminar_producto(id):
    """Borra el producto con sus publicaciones, historial e imagen, todo o nada."""
    fila = execute_query("SELECT imagen_producto FROM productos WHERE id = ?", (id,), fetchone=True)
    with transaccion() as conn:
        conn.execute("DELETE FROM historial_precios WHERE publicacion_producto_id IN (SELECT id FROM publicacion_producto WHERE producto_id = ?)", (id,))
        conn.execute("DELETE FROM publicacion_producto WHERE producto_id = ?", (id,))
        conn.execute("DELETE FROM productos WHERE id = ?", (id,))
    if fila:
        borrar_archivo(fila[0])
    registrar_log(f"Producto eliminado completamente del catálogo ID: {id}")


def fusionar_productos(id_principal, id_duplicado):
    """
    Mueve todas las publicaciones (con su historial) del producto duplicado al principal
    y borra el duplicado. Retorna (ok, mensaje).
    """
    try:
        with transaccion() as conn:
            conn.execute("UPDATE publicacion_producto SET producto_id = ? WHERE producto_id = ?", (id_principal, id_duplicado))
            # Si el principal no tenía imagen, hereda la del duplicado
            conn.execute("""UPDATE productos SET imagen_producto = (SELECT imagen_producto FROM productos WHERE id = ?)
                            WHERE id = ? AND (imagen_producto IS NULL OR imagen_producto = '')""", (id_duplicado, id_principal))
            conn.execute("DELETE FROM productos WHERE id = ?", (id_duplicado,))
        registrar_log(f"Fusión exitosa: El producto {id_duplicado} fue fusionado hacia {id_principal}")
        return True, "Productos fusionados exitosamente."
    except Exception as e:
        registrar_log(f"Error al fusionar productos: {str(e)}")
        return False, f"Error en la base de datos: {str(e)}"


def crear_producto_manual(nombre, grado, precio, url=None):
    """
    Crea un producto con una publicación en la tienda 'Manual' y su primer precio.
    url puede ser None (la columna es UNIQUE y SQLite admite varios NULL).
    Retorna False sin crear nada si faltan datos o la URL ya está registrada.
    """
    if url and execute_query("SELECT id FROM publicacion_producto WHERE url = ?", (url,), fetchone=True):
        registrar_log(f"Producto manual no creado: la URL ya está registrada ({url})")
        return False
    if not nombre or precio <= 0:
        return False

    with transaccion() as conn:
        producto_id = conn.execute("INSERT INTO productos (nombre_estandar, grado) VALUES (?, ?)", (nombre, grado)).lastrowid
        # tiendas.nombre no es UNIQUE, así que INSERT OR IGNORE creaba una tienda 'Manual' por producto
        fila = conn.execute("SELECT id FROM tiendas WHERE nombre = 'Manual'").fetchone()
        tienda_id = fila[0] if fila else conn.execute("INSERT INTO tiendas (nombre, url_base) VALUES ('Manual', '#')").lastrowid
        pub_id = conn.execute(
            "INSERT INTO publicacion_producto (producto_id, tienda_id, nombre_original, url, precio, es_url_activa) VALUES (?, ?, ?, ?, ?, 1)",
            (producto_id, tienda_id, nombre, url, precio)
        ).lastrowid
        conn.execute(
            "INSERT INTO historial_precios (publicacion_producto_id, precio, fecha_registro) VALUES (?, ?, ?)",
            (pub_id, precio, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
    registrar_log(f"Producto creado manualmente en catálogo: {nombre}")
    return True
