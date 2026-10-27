import threading
import time
from datetime import datetime

from scrapers.hangar import HangarScraper
from scrapers.blaster import BlasterScraper
from scrapers.chilerobots import ChileRobotsScraper
from scrapers.irion import IrionScraper
from scrapers.geekz import GeekzScraper
from scrapers.weplay import WeplayScraper
from scrapers.luffytoys import LuffyToysScraper
from scrapers.hobbytoys import HobbyToysScraper

from core.database import transaccion, actualizar_disponibilidad_productos
from core.logger import registrar_log
# Importamos el gestor de catálogo (ajusta la ruta según la ubicación exacta en tu estructura)
from core.catalog_manager import CatalogManager
from core.imagenes import descargar_pendientes as descargar_imagenes_pendientes


class ScraperManager:
    def __init__(self):
        # Instanciamos los motores de extracción con sus URLs base
        self.scrapers = {
            "Hangar019": (HangarScraper(), "https://www.hangar019.cl"),
            "Blaster": (BlasterScraper(), "https://www.blasterchile.cl"),
            "ChileRobots": (ChileRobotsScraper(), "https://www.chilerobots.cl"),
            "Irion": (IrionScraper(), "https://irion.cl"),
            "Geekz": (GeekzScraper(), "https://geekz.cl"),
            "Weplay": (WeplayScraper(), "https://www.weplay.cl"),
            "LuffyToys": (LuffyToysScraper(), "https://luffytoys.cl"),
            "HobbyToys": (HobbyToysScraper(), "https://www.hobbytoys.cl")
        }
        # Un solo escaneo a la vez: el programado y uno forzado desde el panel no deben cruzarse
        self._candado = threading.Lock()

    def en_curso(self):
        return self._candado.locked()

    def guardar_datos(self, nombre_tienda, url_base, datos):
        """Procesa y guarda los datos de publicaciones e historial en la base de datos.

        Todo va en una sola transacción y una sola conexión: si algo falla a mitad, se revierte
        completo y la tienda no queda con sus publicaciones desactivadas y solo algunas reactivadas.
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
        if not self._candado.acquire(blocking=False):
            registrar_log("Escaneo omitido: ya hay uno en curso.")
            return None
        try:
            return self._ejecutar()
        finally:
            self._candado.release()

    def iniciar_en_segundo_plano(self):
        """Lanza el escaneo en otro hilo y retorna enseguida (lo usa Forzar Escaneo: tarda minutos
        y la petición HTTP vencería antes). Retorna False si ya hay uno en curso.
        El candado se toma aquí y no en el hilo, para que en_curso() sea verdadero apenas responde la petición."""
        if not self._candado.acquire(blocking=False):
            return False

        def correr():
            try:
                self._ejecutar()
            finally:
                self._candado.release()

        threading.Thread(target=correr, daemon=True).start()
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
                    items_guardados = self.guardar_datos(nombre_tienda, url_base, datos)
                    total_items += items_guardados
                    self.registrar_estado(nombre_tienda, url_base, productos=len(datos))
                    registrar_log(f"Scraper {nombre_tienda} completado. {len(datos)} items procesados.")
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