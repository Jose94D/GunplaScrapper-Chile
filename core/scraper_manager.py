import os
import subprocess
import sys
import time
from datetime import datetime, timedelta

from scrapers.hangar import HangarScraper
from scrapers.blaster import BlasterScraper
from scrapers.chilerobots import ChileRobotsScraper
from scrapers.irion import IrionScraper
from scrapers.geekz import GeekzScraper
from scrapers.weplay import WeplayScraper
from scrapers.luffytoys import LuffyToysScraper
from scrapers.hobbytoys import HobbyToysScraper

import core.database
from config import BASE_DIR, TIENDAS_DESACTIVADAS
from core.database import execute_query, transaccion, actualizar_disponibilidad_productos
from core.logger import registrar_log
# Importamos el gestor de catálogo (ajusta la ruta según la ubicación exacta en tu estructura)
from core.catalog_manager import CatalogManager
from core.imagenes import descargar_pendientes as descargar_imagenes_pendientes

# Un escaneo con menos de la mitad de los productos del anterior no marca nada como agotado
FRACCION_MINIMA = 0.5
MINIMO_PARA_COMPARAR = 10  # tiendas con menos productos varían mucho de un escaneo a otro
DIAS_TOLERANCIA = 7
# Nombre interno (el de la tabla tiendas) -> (scraper, URL base, nombre que se muestra en el sitio)
TIENDAS = {
    "Hangar019": (HangarScraper, "https://www.hangar019.cl", "Hangar019"),
    "Blaster": (BlasterScraper, "https://www.blasterchile.cl", "Blaster Chile"),
    "ChileRobots": (ChileRobotsScraper, "https://www.chilerobots.cl", "ChileRobots"),
    "Irion": (IrionScraper, "https://irion.cl", "Irion Juguetería"),
    "Geekz": (GeekzScraper, "https://geekz.cl", "Geekz"),
    "Weplay": (WeplayScraper, "https://www.weplay.cl", "Weplay"),
    "LuffyToys": (LuffyToysScraper, "https://luffytoys.cl", "LuffyToys"),
    "HobbyToys": (HobbyToysScraper, "https://www.hobbytoys.cl", "HobbyToys"),
}


def tiendas_habilitadas():
    """Nombres para mostrar de las tiendas que escanea este servidor (las de TIENDAS menos TIENDAS_DESACTIVADAS)."""
    return [visible for nombre, (_, _, visible) in TIENDAS.items() if nombre not in TIENDAS_DESACTIVADAS]


MINUTOS_CANDADO = 30  # un escaneo dura minutos: un candado más viejo es de un proceso que murió sin soltarlo


def _ruta_candado():
    # Un archivo y no un candado en memoria: el panel, el cron y el scheduler pueden ser procesos distintos.
    # Va junto a la base (en las pruebas, junto a la temporal).
    return core.database.DB_NAME + "-escaneo"


def _python():
    """Intérprete del entorno de la app. Bajo LiteSpeed, sys.executable puede ser el servidor y no Python."""
    for ruta in (os.path.join(sys.prefix, "bin", "python"), os.path.join(sys.prefix, "Scripts", "python.exe")):
        if os.path.exists(ruta):
            return ruta
    return sys.executable


class ScraperManager:
    def __init__(self):
        self.scrapers = {nombre: (clase(), url) for nombre, (clase, url, _) in TIENDAS.items() if nombre not in TIENDAS_DESACTIVADAS}
        # La tabla tiendas refleja el .env: una desactivada no cuenta en el sitio ni aparece en el panel, y sus publicaciones
        # dejan de estar activas (si no, mostraría para siempre su último precio). Al reactivarla, el escaneo las recupera.
        with transaccion() as conn:
            for nombre in TIENDAS:
                desactivada = nombre in TIENDAS_DESACTIVADAS
                conn.execute("UPDATE tiendas SET es_activa = ? WHERE nombre = ?", (0 if desactivada else 1, nombre))
                if desactivada:
                    conn.execute("UPDATE publicacion_producto SET es_url_activa = 0 WHERE tienda_id IN "
                                 "(SELECT id FROM tiendas WHERE nombre = ?)", (nombre,))
        if TIENDAS_DESACTIVADAS & TIENDAS.keys():
            actualizar_disponibilidad_productos()

    def en_curso(self):
        try:
            return time.time() - os.path.getmtime(_ruta_candado()) < MINUTOS_CANDADO * 60
        except OSError:
            return False

    def _tomar_candado(self):
        """Un solo escaneo a la vez, entre todos los procesos. Retorna False si ya hay uno en curso."""
        if self.en_curso():
            return False
        self.soltar_candado()  # si quedó uno vencido
        try:
            os.close(os.open(_ruta_candado(), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return True
        except FileExistsError:  # otro proceso lo tomó en este mismo instante
            return False

    def soltar_candado(self):
        try:
            os.remove(_ruta_candado())
        except FileNotFoundError:
            pass

    def escaneo_incompleto(self, nombre_tienda, cantidad):
        """Productos del escaneo anterior si este trajo menos de la mitad (posible cambio en la página de la tienda), o None.

        No aplica a tiendas chicas ni a la primera vez. Si la tienda lleva DIAS_TOLERANCIA días sin un escaneo
        aceptado, la cantidad nueva se toma como real: el aviso estuvo todo ese tiempo en el panel.
        """
        fila = execute_query("SELECT productos_ultimo_escaneo, ultimo_exito FROM tiendas WHERE nombre = ?", (nombre_tienda,), fetchone=True)
        if not fila or not fila[0] or fila[0] < MINIMO_PARA_COMPARAR or not fila[1]:
            return None
        limite = (datetime.now() - timedelta(days=DIAS_TOLERANCIA)).strftime("%Y-%m-%d %H:%M:%S")
        return fila[0] if cantidad < fila[0] * FRACCION_MINIMA and fila[1] >= limite else None

    def guardar_datos(self, nombre_tienda, url_base, datos, desactivar_faltantes=True):
        """Procesa y guarda los datos de publicaciones e historial en la base de datos.

        Todo va en una sola transacción y una sola conexión: si algo falla a mitad, se revierte
        completo y la tienda no queda con sus publicaciones desactivadas y solo algunas reactivadas.
        Con desactivar_faltantes=False (escaneo incompleto) se actualiza lo que vino, sin marcar el resto como agotado.
        """
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with transaccion() as conn:
            c = conn.cursor()

            # 1. Asegurar la existencia de la tienda en DB y obtener su ID
            fila = c.execute("SELECT id FROM tiendas WHERE nombre = ?", (nombre_tienda,)).fetchone()
            tienda_id = fila[0] if fila else c.execute(
                "INSERT INTO tiendas (nombre, url_base) VALUES (?, ?)", (nombre_tienda, url_base)
            ).lastrowid

            # 2. Desactivar URLs de esta tienda para identificar publicaciones agotadas o retiradas
            if desactivar_faltantes:
                c.execute("UPDATE publicacion_producto SET es_url_activa = 0 WHERE tienda_id = ?", (tienda_id,))

            for item in datos:
                nombre_orig = item['nombre_original']
                url = item['url']
                precio = item['precio']
                imagen = item.get('imagen')

                # 3. Buscar si la publicación existe usando su URL única
                fila = c.execute("SELECT id FROM publicacion_producto WHERE url = ?", (url,)).fetchone()
                if fila:
                    pub_id = fila[0]
                    # Reactivar URL y actualizar precio y título original
                    c.execute(
                        # Si esta vez no vino imagen, se conserva la anterior
                        "UPDATE publicacion_producto SET precio = ?, es_url_activa = 1, nombre_original = ?, imagen_url = COALESCE(?, imagen_url) WHERE id = ?",
                        (precio, nombre_orig, imagen, pub_id)
                    )
                else:
                    # 4. Crear publicación nueva dejando producto_id en NULL.
                    # CatalogManager se encargará de normalizar el nombre y asignarle un producto.
                    pub_id = c.execute(
                        "INSERT INTO publicacion_producto (producto_id, tienda_id, nombre_original, url, precio, es_url_activa, imagen_url) VALUES (NULL, ?, ?, ?, ?, 1, ?)",
                        (tienda_id, nombre_orig, url, precio, imagen)
                    ).lastrowid

                # 5. Insertar registro en el historial de precios
                c.execute(
                    "INSERT INTO historial_precios (publicacion_producto_id, precio, fecha_registro) VALUES (?, ?, ?)",
                    (pub_id, precio, fecha_actual)
                )

        return len(datos)

    def registrar_estado(self, nombre_tienda, url_base, productos=None, error=None):
        """Anota el resultado del último escaneo de la tienda (lo muestra el panel).
        Sin error es un éxito; con error se conserva la fecha del último éxito."""
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with transaccion() as conn:
            fila = conn.execute("SELECT id FROM tiendas WHERE nombre = ?", (nombre_tienda,)).fetchone()
            tienda_id = fila[0] if fila else conn.execute(
                "INSERT INTO tiendas (nombre, url_base) VALUES (?, ?)", (nombre_tienda, url_base)
            ).lastrowid
            if error is None:
                conn.execute("UPDATE tiendas SET ultimo_intento = ?, ultimo_exito = ?, productos_ultimo_escaneo = ?, ultimo_error = NULL WHERE id = ?",
                             (ahora, ahora, productos, tienda_id))
            else:
                conn.execute("UPDATE tiendas SET ultimo_intento = ?, ultimo_error = ? WHERE id = ?", (ahora, error[:300], tienda_id))

    def ejecutar_todos(self):
        """Escaneo completo en este hilo (lo usa el scheduler).
        Si ya hay uno en curso no inicia otro: lo registra y retorna None."""
        if not self._tomar_candado():
            registrar_log("Escaneo omitido: ya hay uno en curso.")
            return None
        return self.ejecutar_ya_bloqueado()

    def ejecutar_ya_bloqueado(self):
        """Escaneo cuyo candado ya tomó quien lo lanzó (el panel); lo suelta al terminar, falle o no."""
        try:
            return self._ejecutar()
        finally:
            self.soltar_candado()

    def iniciar_en_segundo_plano(self):
        """Lanza el escaneo en un proceso aparte y retorna enseguida (lo usa Forzar escaneo: tarda minutos y la
        petición HTTP vencería antes). Retorna False si ya hay uno en curso.

        Proceso y no hilo: servidores como LiteSpeed cierran el proceso de la app al terminar de responder, y un hilo
        moría con él a mitad de la primera tienda. El candado se toma aquí, para que en_curso() sea verdadero apenas
        responde la petición; el proceso nuevo lo suelta al terminar.
        """
        if not self._tomar_candado():
            return False
        try:
            with open(os.path.join(BASE_DIR, "escaneo.log"), "ab") as salida:
                subprocess.Popen([_python(), os.path.join(BASE_DIR, "tareas.py"), "escaneo-forzado"], cwd=BASE_DIR,
                                 stdin=subprocess.DEVNULL, stdout=salida, stderr=subprocess.STDOUT,
                                 env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"},  # log en vivo
                                 start_new_session=True)  # sigue vivo aunque el servidor cierre el proceso que lo lanzó
        except Exception:
            self.soltar_candado()
            raise
        return True

    def _ejecutar(self):
        """Ejecuta los scrapers en secuencia, guarda datos y ejecuta la estandarización de catálogo."""
        inicio = time.time()
        total_items = 0

        for nombre_tienda, (scraper_obj, url_base) in self.scrapers.items():
            try:
                registrar_log(f"Iniciando recolección en: {nombre_tienda}")
                datos = scraper_obj.extraer_datos()
                
                if datos:
                    antes = self.escaneo_incompleto(nombre_tienda, len(datos))
                    total_items += self.guardar_datos(nombre_tienda, url_base, datos, desactivar_faltantes=antes is None)
                    if antes is None:
                        self.registrar_estado(nombre_tienda, url_base, productos=len(datos))
                        registrar_log(f"Scraper {nombre_tienda} completado. {len(datos)} items procesados.")
                    else:
                        aviso = f"Trajo {len(datos)} productos (antes {antes}): posible cambio en la página. No se marcó nada sin stock."
                        self.registrar_estado(nombre_tienda, url_base, error=aviso)
                        registrar_log(f"Advertencia: {nombre_tienda} {aviso[0].lower()}{aviso[1:]}")
                else:
                    self.registrar_estado(nombre_tienda, url_base, error="No devolvió productos")
                    registrar_log(f"Advertencia: {nombre_tienda} no devolvió productos.")
            except Exception as e:
                self.registrar_estado(nombre_tienda, url_base, error=str(e))
                registrar_log(f"FALLO CRÍTICO en scraper {nombre_tienda}: {str(e)}")

        duracion = time.time() - inicio
        registrar_log(f"Escaneo masivo finalizado. Tiempo: {duracion:.1f}s, Total registros historizados: {total_items}")

        # 6. Invocar el algoritmo de normalización y vinculación de catálogo
        try:
            catalog_mgr = CatalogManager()
            catalog_mgr.procesar_pendientes()
        except Exception as e:
            registrar_log(f"Error durante el procesamiento de catálogo: {str(e)}")

        # 6.1 Imagen de los productos que aún no tienen (una descarga por producto, nunca se repite)
        try:
            descargar_imagenes_pendientes()
        except Exception as e:
            registrar_log(f"Error al descargar imágenes de productos: {str(e)}")

        # 7. Recalcular el estado "No disponible" según la disponibilidad real por tienda,
        # ahora que ya se actualizó es_url_activa en todas las tiendas de esta corrida.
        try:
            actualizar_disponibilidad_productos()
        except Exception as e:
            registrar_log(f"Error al recalcular disponibilidad de productos: {str(e)}")

        return total_items, duracion