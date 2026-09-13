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

from core.database import execute_query, actualizar_disponibilidad_productos
from core.logger import registrar_log
# Importamos el gestor de catálogo (ajusta la ruta según la ubicación exacta en tu estructura)
from core.catalog_manager import CatalogManager


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

    def guardar_datos(self, nombre_tienda, url_base, datos):
        """Procesa y guarda los datos de publicaciones e historial en la base de datos."""
        
        # 1. Asegurar la existencia de la tienda en DB y obtener su ID
        tienda_res = execute_query("SELECT id FROM tiendas WHERE nombre = ?", (nombre_tienda,), fetchone=True)
        if not tienda_res:
            execute_query("INSERT INTO tiendas (nombre, url_base) VALUES (?, ?)", (nombre_tienda, url_base), commit=True)
            tienda_id = execute_query("SELECT MAX(id) FROM tiendas", fetchone=True)[0]
        else:
            tienda_id = tienda_res[0]

        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        items_procesados = 0

        # 2. Desactivar URLs de esta tienda para identificar publicaciones agotadas o retiradas
        execute_query("UPDATE publicacion_producto SET es_url_activa = 0 WHERE tienda_id = ?", (tienda_id,), commit=True)

        for item in datos:
            nombre_orig = item['nombre_original']
            url = item['url']
            precio = item['precio']

            # 3. Buscar si la publicación existe usando su URL única
            pub_res = execute_query("SELECT id FROM publicacion_producto WHERE url = ?", (url,), fetchone=True)
            
            if pub_res:
                pub_id = pub_res[0]
                # Reactivar URL y actualizar precio y título original
                execute_query(
                    "UPDATE publicacion_producto SET precio = ?, es_url_activa = 1, nombre_original = ? WHERE id = ?", 
                    (precio, nombre_orig, pub_id), 
                    commit=True
                )
            else:
                # 4. Crear publicación nueva dejando producto_id en NULL.
                # CatalogManager se encargará de normalizar el nombre y asignarle un producto.
                execute_query(
                    "INSERT INTO publicacion_producto (producto_id, tienda_id, nombre_original, url, precio, es_url_activa) VALUES (NULL, ?, ?, ?, ?, 1)", 
                    (tienda_id, nombre_orig, url, precio), 
                    commit=True
                )
                pub_id = execute_query("SELECT MAX(id) FROM publicacion_producto", fetchone=True)[0]

            # 5. Insertar registro en el historial de precios
            execute_query(
                "INSERT INTO historial_precios (publicacion_producto_id, precio, fecha_registro) VALUES (?, ?, ?)", 
                (pub_id, precio, fecha_actual), 
                commit=True
            )
            items_procesados += 1

        return items_procesados

    def ejecutar_todos(self):
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
                    registrar_log(f"Scraper {nombre_tienda} completado. {len(datos)} items procesados.")
                else:
                    registrar_log(f"Advertencia: {nombre_tienda} no devolvió productos.")
            except Exception as e:
                registrar_log(f"FALLO CRÍTICO en scraper {nombre_tienda}: {str(e)}")

        duracion = time.time() - inicio
        registrar_log(f"Escaneo masivo finalizado. Tiempo: {duracion:.1f}s, Total registros historizados: {total_items}")

        # 6. Invocar el algoritmo de normalización y vinculación de catálogo
        try:
            catalog_mgr = CatalogManager()
            catalog_mgr.procesar_pendientes()
        except Exception as e:
            registrar_log(f"Error durante el procesamiento de catálogo: {str(e)}")

        # 7. Recalcular el estado "No disponible" según la disponibilidad real por tienda,
        # ahora que ya se actualizó es_url_activa en todas las tiendas de esta corrida.
        try:
            actualizar_disponibilidad_productos()
        except Exception as e:
            registrar_log(f"Error al recalcular disponibilidad de productos: {str(e)}")

        return total_items, duracion