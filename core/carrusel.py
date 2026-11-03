"""Imágenes del carrusel de inicio: archivos en static/carrusel y filas en la tabla banners."""
import os

from werkzeug.utils import secure_filename

from core.database import execute_query, transaccion
from core.logger import registrar_log

CARRUSEL_FOLDER = os.path.join('static', 'carrusel')
EXTENSIONES_CARRUSEL = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}


def listar_imagenes():
    """[(id, nombre_archivo, enlace), ...] en el orden elegido en el panel (las que nunca se movieron, por fecha de subida)."""
    return execute_query("SELECT id, nombre_archivo, enlace FROM banners ORDER BY COALESCE(orden, id), id", fetchall=True)


def agregar_imagen(archivo, enlace=''):
    """Guarda un archivo subido (FileStorage de Flask). Retorna False si no es una imagen permitida."""
    if not archivo or not archivo.filename:
        return False
    nombre = secure_filename(archivo.filename)
    # La carpeta es pública en /static: un .html o .svg ahí ejecutaría código en nuestro dominio
    if os.path.splitext(nombre)[1].lower() not in EXTENSIONES_CARRUSEL:
        registrar_log(f"Imagen de carrusel rechazada por su tipo: {archivo.filename}")
        return False
    os.makedirs(CARRUSEL_FOLDER, exist_ok=True)
    archivo.save(os.path.join(CARRUSEL_FOLDER, nombre))
    # Al final del carrusel
    execute_query("INSERT INTO banners (nombre_archivo, enlace, orden) VALUES (?, ?, (SELECT COALESCE(MAX(COALESCE(orden, id)), 0) + 1 FROM banners))",
                  (nombre, enlace), commit=True)
    registrar_log(f"Imagen subida a banners con enlace: {nombre}")
    return True


def actualizar_enlace(id, enlace):
    execute_query("UPDATE banners SET enlace = ? WHERE id = ?", (enlace, id), commit=True)
    registrar_log(f"Enlace actualizado en banner (ID imagen: {id})")


def eliminar_imagen(id):
    """Borra la fila y el archivo. Si el archivo ya no estaba, borra igual la fila."""
    fila = execute_query("SELECT nombre_archivo FROM banners WHERE id = ?", (id,), fetchone=True)
    if not fila:
        return
    try:
        os.remove(os.path.join(CARRUSEL_FOLDER, fila[0]))
    except FileNotFoundError:
        pass
    execute_query("DELETE FROM banners WHERE id = ?", (id,), commit=True)
    registrar_log(f"Imagen eliminada de banners: {fila[0]}")


def mover_imagen(id, paso):
    """Cambia de lugar la imagen con su vecina (paso -1: antes, +1: después) y renumera el orden de todas."""
    ids = [fila[0] for fila in listar_imagenes()]
    if id not in ids:
        return
    i = ids.index(id)
    j = i + paso
    if not 0 <= j < len(ids):
        return
    ids[i], ids[j] = ids[j], ids[i]
    with transaccion() as conn:
        conn.executemany("UPDATE banners SET orden = ? WHERE id = ?", [(posicion, id_imagen) for posicion, id_imagen in enumerate(ids, 1)])
    registrar_log(f"Orden del carrusel cambiado (ID imagen: {id}, posición {j + 1})")
