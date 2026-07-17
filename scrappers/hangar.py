import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime
import time

class HangarScraper:
    def __init__(self, db_name):
        self.db_name = db_name
        self.base_url = "https://www.hangar019.cl"
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        self._inicializar_base_datos()

    def _inicializar_base_datos(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Tabla principal
        cursor.execute('''CREATE TABLE IF NOT EXISTS historial_precios (id INTEGER PRIMARY KEY AUTOINCREMENT, producto TEXT NOT NULL, precio TEXT, url TEXT, fecha TEXT NOT NULL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS estadisticas (id INTEGER PRIMARY KEY, contador INTEGER)''')
        cursor.execute('''INSERT OR IGNORE INTO estadisticas (id, contador) VALUES (1, 0)''')
        
        # Actualización de esquema sobre la marcha
        try:
            cursor.execute("PRAGMA table_info(historial_precios)")
            columnas = [col[1] for col in cursor.fetchall()]
            if columnas and 'activo' not in columnas:
                cursor.execute("ALTER TABLE historial_precios ADD COLUMN activo INTEGER DEFAULT 1")
            if columnas and 'precio_base' not in columnas:
                cursor.execute("ALTER TABLE historial_precios ADD COLUMN precio_base TEXT")
        except sqlite3.Error:
            pass
            
        conn.commit()
        conn.close()

    def _guardar_precio(self, producto, precio, precio_base, url):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Consultamos el último estado 'activo' de este producto para no desocultarlo sin querer
        cursor.execute("SELECT activo FROM historial_precios WHERE producto = ? ORDER BY fecha DESC LIMIT 1", (producto,))
        resultado = cursor.fetchone()
        estado_activo = resultado[0] if resultado and resultado[0] is not None else 1
        
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''INSERT INTO historial_precios (producto, precio, precio_base, url, fecha, activo) VALUES (?, ?, ?, ?, ?, ?)''', (producto, precio, precio_base, url, fecha_actual, estado_activo))
        
        conn.commit()
        conn.close()

    def ejecutar_escaneo(self):
        print(f"[{datetime.now()}] -> Iniciando escaneo profundo en Hangar019...")
        pagina = 1
        productos_vistos_sesion = set()

        while True:
            print(f"[{datetime.now()}] -> Registrando página {pagina} de la tienda...")
            try:
                res = requests.get(f"{self.base_url}/8-gunpla?p={pagina}", headers=self.headers, timeout=15)
                soup = BeautifulSoup(res.text, 'html.parser')
                
                # Buscamos mediante el ancla original que funcionaba
                nombres = soup.find_all('a', class_='product-name')
                
                if not nombres: 
                    break 
                
                bucle_detectado = False
                
                for n in nombres:
                    url_prod = n['href'] if n['href'].startswith('http') else self.base_url + n['href']
                    nombre_prod = n.text.strip()
                    
                    # 1. Encontrar la "caja" o contenedor que envuelve a este producto subiendo por el árbol HTML
                    contenedor = n.find_parent('div', class_='product-container') or n.find_parent('li')
                    if not contenedor: 
                        continue
                    
                    # 2. Buscar el precio actual dentro de ese contenedor específico
                    p = contenedor.find('span', class_='product-price') or contenedor.find('span', itemprop='price')
                    if not p: 
                        continue
                        
                    precio_oferta = p.text.strip()
                    
                    # 3. Buscar el precio tachado (PrestaShop clásico usa 'old-price', el nuevo usa 'regular-price')
                    p_base_element = contenedor.find('span', class_='old-price') or contenedor.find('span', class_='regular-price')
                    
                    # Si no hay precio tachado, el precio base es el mismo que el precio actual
                    precio_base = p_base_element.text.strip() if p_base_element and p_base_element.text.strip() else precio_oferta
                    
                    if url_prod in productos_vistos_sesion:
                        print(f"[{datetime.now()}] -> Alerta PrestaShop: Producto repetido detectado en página {pagina} ({nombre_prod}). Deteniendo escaneo.")
                        bucle_detectado = True
                        break 
                        
                    productos_vistos_sesion.add(url_prod)
                    self._guardar_precio(nombre_prod, precio_oferta, precio_base, url_prod)
                
                if bucle_detectado: break
                pagina += 1
                time.sleep(2) 
            except Exception as e:
                print(f"Error en página {pagina}: {e}")
                raise e 
                
        print(f"[{datetime.now()}] -> Escaneo finalizado. Total: {len(productos_vistos_sesion)} productos únicos.")
        return len(productos_vistos_sesion)