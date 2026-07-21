from datetime import datetime
from scrapers.hangar import HangarScraper
from scrapers.blaster import BlasterScraper
from core.database import execute_query
from core.logger import registrar_log

class ScraperManager:
    def __init__(self):
        # Aquí se agregarán los futuros scrapers (Ej: BlasterScraper, MiraxScraper)
        self.scrapers = [
            HangarScraper(),
            BlasterScraper()
        ]

    def _guardar_producto_db(self, producto_dict):
        """Envía el producto a la base de datos manteniendo el estado 'activo' previo."""
        prod = producto_dict['producto']
        # Recupera el estado activo mediante core/database
        estado = execute_query("SELECT activo FROM historial_precios WHERE producto = ? ORDER BY fecha DESC LIMIT 1", (prod,), fetchone=True)
        estado_activo = estado[0] if estado and estado[0] is not None else 1
        
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        execute_query('''
            INSERT INTO historial_precios (producto, precio, precio_base, url, fecha, activo) 
            VALUES (?, ?, ?, ?, ?, ?)''', 
            (prod, producto_dict['precio'], producto_dict['precio_base'], producto_dict['url'], fecha_actual, estado_activo), 
            commit=True)

    def ejecutar_todos(self):
        """Recorre todos los scrapers, captura errores y guarda en DB."""
        inicio = datetime.now()
        total_productos = 0
        registrar_log("Iniciando ejecución del Scraper Manager...")
        
        for scraper in self.scrapers:
            nombre_scraper = scraper.__class__.__name__
            registrar_log(f"Iniciando recolección en: {nombre_scraper}")
            try:
                # 1. Ejecutamos el scraper (Responsabilidad de extracción)
                productos = scraper.extraer_datos()
                
                if not productos:
                    registrar_log(f"Advertencia: {nombre_scraper} no devolvió ningún producto.")
                    continue

                # 2. Guardamos en la DB (Responsabilidad de almacenamiento)
                for p in productos:
                    self._guardar_producto_db(p)
                    
                total_productos += len(productos)
                registrar_log(f"{nombre_scraper} terminó con éxito. {len(productos)} obtenidos.")
                
            except Exception as e:
                # El fallo de un scraper no detiene a los demás
                registrar_log(f"FALLO CRÍTICO en {nombre_scraper}: {str(e)}")

        duracion = (datetime.now() - inicio).total_seconds()
        registrar_log(f"Escaneo global finalizado. Tiempo: {duracion:.1f}s. Total: {total_productos}")
        
        return total_productos, duracion