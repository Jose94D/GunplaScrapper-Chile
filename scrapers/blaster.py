import cloudscraper
from bs4 import BeautifulSoup
import time
import random
from core.logger import registrar_log

class BlasterScraper:
    def __init__(self):
        self.base_url = "https://www.blasterchile.cl"
        self.collection_path = "/collections/model-kit"
        # Filtros de búsqueda (Bandai, disponibilidad y grados específicos)
        self.filters = "?sort_by=price-ascending&filter.v.availability=1&filter.p.product_type=Model+Kit+-+HG+-+Gundam&filter.p.product_type=Model+Kit+-+MG+-+Gundam&filter.p.product_type=Model+Kit+-+RG+-+Gundam&filter.p.product_type=Model+Kit+-+SD+-+Gundam&filter.p.vendor=Bandai"
        
        # Cloudscraper crea una sesión que resuelve los desafíos de Cloudflare
        # y simula perfectamente a un navegador Chrome real en Windows
        self.session = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )

    def extraer_datos(self):
        pagina = 1
        productos_extraidos = []
        urls_vistas = set()

        # Visita inicial a la página principal para capturar las cookies base
        try:
            self.session.get(self.base_url, timeout=15)
            time.sleep(random.uniform(2.0, 4.0))
        except:
            pass

        while True:
            url_target = f"{self.base_url}{self.collection_path}{self.filters}&page={pagina}"
            
            # Sistema de reintentos (Exponential Backoff) para mitigar el Error 429
            intentos = 0
            max_intentos = 3
            res = None
            
            while intentos < max_intentos:
                try:
                    res = self.session.get(url_target, timeout=15)
                    
                    if res.status_code == 429:
                        tiempo_castigo = (intentos + 1) * 15 # Espera 15s, luego 30s, luego 45s
                        time.sleep(tiempo_castigo)
                        intentos += 1
                        continue 
                        
                    elif res.status_code != 200:
                        registrar_log(f"Blaster bloqueó la conexión (Error {res.status_code})")
                        break
                        
                    # Si llegamos aquí, fue un éxito (200 OK)
                    break 
                    
                except Exception as e:
                    intentos += 1
                    time.sleep(5)

            # Si después de los reintentos no hay respuesta válida (o persiste el 429), salimos
            if not res or res.status_code != 200:
                break

            try:
                soup = BeautifulSoup(res.text, 'html.parser')
                
                # Búsqueda Universal de enlaces a productos en Shopify
                enlaces_productos = soup.find_all('a', href=lambda href: href and '/products/' in href)
                
                if not enlaces_productos:
                    break

                productos_en_esta_pagina = 0

                for enlace in enlaces_productos:
                    url_bruta = enlace.get('href')
                    
                    # 1. Limpiar variantes de URL eliminando parámetros
                    url_limpia = url_bruta.split('?')[0]
                    
                    # 2. NORMALIZACIÓN: Forzar la ruta canónica extrayendo solo lo que va después de /products/
                    if '/products/' in url_limpia:
                        handle_producto = url_limpia.split('/products/')[-1]
                        url_prod = f"{self.base_url}/products/{handle_producto}"
                    else:
                        url_prod = url_limpia if url_limpia.startswith('http') else self.base_url + url_limpia
                        
                    # 3. Validación de duplicados (ahora bloquea URLs idénticas correctamente)
                    if url_prod in urls_vistas:
                        continue

                    # Subimos en el DOM para buscar la "caja" o tarjeta del producto
                    contenedor = enlace.find_parent(['div', 'li'], class_=lambda c: c and ('product' in c.lower() or 'item' in c.lower() or 'grid' in c.lower() or 'card' in c.lower()))
                    if not contenedor: 
                        continue

                    # Extracción del Nombre
                    nombre_tag = contenedor.find(['h2', 'h3', 'h4', 'span'], class_=lambda c: c and 'title' in c.lower())
                    nombre_prod = nombre_tag.text.strip() if nombre_tag else enlace.text.strip()
                    
                    if not nombre_prod or len(nombre_prod) < 3:
                        continue

                    # Extracción agresiva del Precio
                    precio_oferta = "$0"
                    precio_base = "$0"
                    
                    textos_con_dinero = contenedor.find_all(string=lambda t: t and '$' in t)
                    if textos_con_dinero:
                        precios_limpios = [p.strip() for p in textos_con_dinero if len(p.strip()) > 1]
                        if precios_limpios:
                            precio_oferta = precios_limpios[-1]
                            precio_base = precios_limpios[0] if len(precios_limpios) > 1 else precio_oferta

                    # Agregamos a la lista de validación y de extracción
                    urls_vistas.add(url_prod)
                    productos_extraidos.append({
                        'producto': nombre_prod,
                        'precio': precio_oferta,
                        'precio_base': precio_base,
                        'url': url_prod
                    })
                    productos_en_esta_pagina += 1
                # Si no se extrajo ningún producto en esta página, terminamos el bucle
                
                if productos_en_esta_pagina == 0:
                    break

                pagina += 1
                
                # Tiempos de espera aleatorios para imitar comportamiento humano al cambiar de página
                tiempo_pausa = random.uniform(3.5, 7.2)
                time.sleep(tiempo_pausa) 
                
            except Exception as e:
                break 

        return productos_extraidos