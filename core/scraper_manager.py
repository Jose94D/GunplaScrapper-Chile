from datetime import datetime
from scrapers.hangar import HangarScraper
from scrapers.blaster import BlasterScraper
from core.database import execute_query
from core.logger import registrar_log
from core.catalog_manager import CatalogManager

class ScraperManager:
    def __init__(self):
        # Aquí se agregarán los futuros scrapers
        self.scrapers = [
            HangarScraper(),
            BlasterScraper()
        ]

    def _guardar_producto_db(self, producto_dict, nombre_tienda):
        """Busca o crea la publicación, y luego guarda el registro del precio histórico."""
        prod_nombre = producto_dict['producto']
        prod_url = producto_dict['url']
        precio = producto_dict['precio']
        precio_base = producto_dict['precio_base']
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Buscar si la publicación ya existe en la base de datos usando la URL única
        publicacion = execute_query("SELECT id FROM publicaciones_tiendas WHERE url = ?", (prod_url,), fetchone=True)
        
        # 2. Si no existe, la creamos (quedará con catalogo_id en NULL inicialmente)
        if not publicacion:
            execute_query('''
                INSERT INTO publicaciones_tiendas (tienda, nombre_original, url) 
                VALUES (?, ?, ?)''', 
                (nombre_tienda, prod_nombre, prod_url), 
                commit=True)
            
            # Volvemos a consultar para obtener el ID recién creado
            publicacion = execute_query("SELECT id FROM publicaciones_tiendas WHERE url = ?", (prod_url,), fetchone=True)
        
        publicacion_id = publicacion[0]

        # 3. Recuperar el estado 'activo' del último registro de esta publicación
        estado = execute_query("SELECT activo FROM historial_precios WHERE publicacion_id = ? ORDER BY fecha DESC LIMIT 1", (publicacion_id,), fetchone=True)
        estado_activo = estado[0] if estado and estado[0] is not None else 1
        
        # 4. Insertar el precio en el historial usando el ID relacional
        execute_query('''
            INSERT INTO historial_precios (publicacion_id, precio, precio_base, fecha, activo) 
            VALUES (?, ?, ?, ?, ?)''', 
            (publicacion_id, precio, precio_base, fecha_actual, estado_activo), 
            commit=True)

    def ejecutar_todos(self):
        """Recorre todos los scrapers, captura errores y guarda en DB relacional."""
        inicio = datetime.now()
        total_productos = 0
        registrar_log("Iniciando ejecución del Scraper Manager...")
        
        for scraper in self.scrapers:
            # Limpiamos el nombre de la clase para obtener el nombre de la tienda (Ej: 'HangarScraper' -> 'Hangar')
            nombre_scraper = scraper.__class__.__name__
            nombre_tienda = nombre_scraper.replace("Scraper", "")
            
            registrar_log(f"Iniciando recolección en: {nombre_scraper}")
            try:
                # 1. Ejecutamos el scraper
                productos = scraper.extraer_datos()
                
                if not productos:
                    registrar_log(f"Advertencia: {nombre_scraper} no devolvió ningún producto.")
                    continue

                # 2. Guardamos en la DB
                for p in productos:
                    self._guardar_producto_db(p, nombre_tienda)
                    
                total_productos += len(productos)
                registrar_log(f"{nombre_scraper} terminó con éxito. {len(productos)} obtenidos.")
                
            except Exception as e:
                registrar_log(f"FALLO CRÍTICO en {nombre_scraper}: {str(e)}")

        duracion = (datetime.now() - inicio).total_seconds()
        registrar_log(f"Escaneo global finalizado. Tiempo: {duracion:.1f}s. Total: {total_productos}")
        
        # 3. Ejecutar algoritmo de emparejamiento automático de catálogo
        manager_catalogo = CatalogManager()
        manager_catalogo.procesar_pendientes()
        
        return total_productos, duracion