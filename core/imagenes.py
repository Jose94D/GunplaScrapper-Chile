"""Imágenes de los productos: se toman de los listados de las tiendas, se descargan una vez y se guardan reducidas en WebP."""
import io
import os
import time

import requests
from PIL import Image

from config import BASE_DIR
from core.database import execute_query
from core.logger import registrar_log

CARPETA = os.path.join(BASE_DIR, 'static', 'productos')
ANCHO_MAXIMO = 400
CALIDAD_WEBP = 80
BYTES_MAXIMOS = 5 * 1024 * 1024
PAUSA_ENTRE_DESCARGAS = 1  # segundos, para no cargar los servidores de las tiendas
EXTENSIONES_SUBIDA = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def url_imagen(tarjeta, base_url):
    """
    URL absoluta de la primera imagen dentro de la tarjeta de un listado, o None.
    Entiende carga diferida (data-src), srcset (elige el tamaño más chico de al menos ANCHO_MAXIMO),
    URLs relativas y las que empiezan con // (sin protocolo).
    """
    img = tarjeta.find('img') if tarjeta else None
    if not img:
        return None

    candidata = None
    for atributo in ('data-srcset', 'srcset'):
        opciones = []
        for parte in (img.get(atributo) or '').split(','):
            trozos = parte.split()
            if len(trozos) == 2 and trozos[1].endswith('w') and trozos[1][:-1].isdigit():
                opciones.append((int(trozos[1][:-1]), trozos[0]))
        if opciones:
            opciones.sort()
            suficientes = [o for o in opciones if o[0] >= ANCHO_MAXIMO]
            candidata = (suficientes[0] if suficientes else opciones[-1])[1]
            break
    for atributo in ('data-src', 'data-original', 'src'):
        if candidata:
            break
        valor = (img.get(atributo) or '').strip()
        if valor and not valor.startswith('data:'):
            candidata = valor

    if not candidata or candidata.startswith('data:'):
        return None
    # PrestaShop (Hangar019, ChileRobots) lista miniaturas de ~250 px; la misma foto grande está en large_default
    candidata = candidata.replace('-home_default/', '-large_default/')
    if candidata.startswith('//'):
        return 'https:' + candidata
    if candidata.startswith('/'):
        return base_url.rstrip('/') + candidata
    return candidata if candidata.startswith(('http://', 'https://')) else None


def a_webp(datos):
    """Bytes de cualquier imagen -> bytes WebP de máximo ANCHO_MAXIMO px de ancho. Lanza error si no es una imagen."""
    with Image.open(io.BytesIO(datos)) as original:
        original.load()
        imagen = original.convert('RGBA')
    fondo = Image.new('RGB', imagen.size, (255, 255, 255))  # las transparencias quedan sobre blanco, como en las tiendas
    fondo.paste(imagen, mask=imagen.getchannel('A'))
    fondo.thumbnail((ANCHO_MAXIMO, ANCHO_MAXIMO * 2))
    salida = io.BytesIO()
    fondo.save(salida, 'WEBP', quality=CALIDAD_WEBP)
    return salida.getvalue()


def _guardar(producto_id, datos):
    webp = a_webp(datos)  # antes de escribir: si no es una imagen, no se toca la anterior
    os.makedirs(CARPETA, exist_ok=True)
    with open(os.path.join(CARPETA, f"{producto_id}.webp"), 'wb') as f:
        f.write(webp)
    ruta_relativa = f"productos/{producto_id}.webp"  # relativa a static/, para url_for
    execute_query("UPDATE productos SET imagen_producto = ? WHERE id = ?", (ruta_relativa, producto_id), commit=True)
    return ruta_relativa


def descargar(url):
    """Descarga una imagen de una tienda. La URL viene de HTML ajeno: solo http(s), con tiempo y tamaño máximos."""
    if not url.startswith(('http://', 'https://')):
        raise ValueError("URL no permitida")
    with requests.get(url, headers=HEADERS, timeout=15, stream=True) as respuesta:
        respuesta.raise_for_status()
        datos = b''
        for bloque in respuesta.iter_content(64 * 1024):
            datos += bloque
            if len(datos) > BYTES_MAXIMOS:
                raise ValueError("imagen demasiado grande")
    return datos


def descargar_pendientes():
    """
    Descarga la imagen de cada producto que aún no tiene, desde la primera de sus publicaciones que la traiga.
    Corre al final de cada escaneo; un producto que falla se reintenta en el siguiente.
    Los productos con imagen (descargada o subida a mano) no se tocan.
    """
    pendientes = execute_query("""
        SELECT p.id, (SELECT pp.imagen_url FROM publicacion_producto pp
                      WHERE pp.producto_id = p.id AND pp.imagen_url IS NOT NULL ORDER BY pp.es_url_activa DESC, pp.id LIMIT 1)
        FROM productos p
        WHERE p.imagen_producto IS NULL OR p.imagen_producto = ''
    """, fetchall=True)
    pendientes = [(pid, url) for pid, url in pendientes if url]

    guardadas, fallidas = 0, 0
    for producto_id, url in pendientes:
        try:
            _guardar(producto_id, descargar(url))
            guardadas += 1
        except Exception as e:
            fallidas += 1
            registrar_log(f"No se pudo descargar la imagen del producto {producto_id}: {str(e)[:120]}")
        time.sleep(PAUSA_ENTRE_DESCARGAS)
    if pendientes:
        registrar_log(f"Imágenes de productos: {guardadas} descargadas, {fallidas} con error.")
    return guardadas, fallidas


def guardar_subida(producto_id, archivo):
    """Reemplaza la imagen con una subida desde el panel (FileStorage). Retorna False si no es una imagen válida."""
    if not archivo or not archivo.filename or os.path.splitext(archivo.filename)[1].lower() not in EXTENSIONES_SUBIDA:
        return False
    try:
        _guardar(producto_id, archivo.read())
    except Exception:
        registrar_log(f"Imagen subida para el producto {producto_id} rechazada: no es una imagen válida.")
        return False
    registrar_log(f"Imagen del producto {producto_id} reemplazada desde el panel.")
    return True


def borrar_archivo(ruta_relativa):
    """Borra el WebP de un producto eliminado. Solo dentro de static/productos."""
    if ruta_relativa and ruta_relativa.startswith('productos/'):
        try:
            os.remove(os.path.join(CARPETA, os.path.basename(ruta_relativa)))
        except FileNotFoundError:
            pass
