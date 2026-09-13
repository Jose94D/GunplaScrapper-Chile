import cloudscraper
from bs4 import BeautifulSoup
import time
import random
import re
from core.logger import registrar_log

def limpiar_precio(precio_str):
    """Extrae todos los dígitos de un texto y los retorna como float."""
    if not precio_str:
        return 0.0
    numeros = re.findall(r'\d+', precio_str)
    if not numeros:
        return 0.0
    try:
        return float("".join(numeros))
    except ValueError:
        return 0.0

class BlasterScraper:
    def __init__(self):
        self.base_url = "https://www.blasterchile.cl"
        self.collection_path = "/collections/model-kit"
        self.filters = "?sort_by=price-ascending&filter.v.availability=1&filter.p.product_type=Model+Kit+-+HG+-+Gundam&filter.p.product_type=Model+Kit+-+MG+-+Gundam&filter.p.product_type=Model+Kit+-+RG+-+Gundam&filter.p.product_type=Model+Kit+-+SD+-+Gundam&filter.p.vendor=Bandai"
        
        self.session = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )

    def extraer_datos(self):
        pagina = 1
        productos_extraidos = []
        urls_vistas = set()

        try:
            self.session.get(self.base_url, timeout=15)
            time.sleep(random.uniform(2.0, 4.0))
        except Exception:
            pass

        while True:
            url_target = f"{self.base_url}{self.collection_path}{self.filters}&page={pagina}"
            intentos = 0
            max_intentos = 3
            res = None
            
            while intentos < max_intentos:
                try:
                    res = self.session.get(url_target, timeout=15)
                    if res.status_code == 429:
                        time.sleep((intentos + 1) * 15)
                        intentos += 1
                        continue 
                    elif res.status_code != 200:
                        registrar_log(f"Blaster bloqueó la conexión (Error {res.status_code})")
                        break
                    break 
                except Exception as e:
                    intentos += 1
                    time.sleep(5)

            if not res or res.status_code != 200:
                break

            try:
                soup = BeautifulSoup(res.text, 'html.parser')
                enlaces_productos = soup.find_all('a', href=lambda href: href and '/products/' in href)
                
                if not enlaces_productos: 
                    break
                productos_en_esta_pagina = 0

                for enlace in enlaces_productos:
                    url_bruta = enlace.get('href')
                    url_limpia = url_bruta.split('?')[0]
                    
                    if '/products/' in url_limpia:
                        handle_producto = url_limpia.split('/products/')[-1]
                        url_prod = f"{self.base_url}/products/{handle_producto}"
                    else:
                        url_prod = url_limpia if url_limpia.startswith('http') else self.base_url + url_limpia
                        
                    if url_prod in urls_vistas: 
                        continue

                    contenedor = enlace.find_parent(['div', 'li'], class_=lambda c: c and ('product' in c.lower() or 'item' in c.lower() or 'grid' in c.lower() or 'card' in c.lower()))
                    if not contenedor: 
                        continue

                    nombre_tag = contenedor.find(['h2', 'h3', 'h4', 'span'], class_=lambda c: c and 'title' in c.lower())
                    nombre_prod = nombre_tag.text.strip() if nombre_tag else enlace.text.strip()
                    
                    if not nombre_prod or len(nombre_prod) < 3: 
                        continue

                    # Precio en oferta (span.product-price__discounted); si no existe, se usa
                    # el precio regular (cualquier span.money suelto). Antes esto se resolvía con
                    # un regex que solo reconocía "$199.990" (punto), y fallaba silenciosamente
                    # con el formato real de la tienda "$199,990" (coma), guardando precio 0.
                    precio_texto = None
                    tag_oferta = contenedor.find('span', class_='product-price__discounted')
                    if tag_oferta:
                        money_tag = tag_oferta.find('span', class_='money')
                        if money_tag and money_tag.text.strip():
                            precio_texto = money_tag.text.strip()

                    if not precio_texto:
                        money_tag = contenedor.find('span', class_='money')
                        if money_tag and money_tag.text.strip():
                            precio_texto = money_tag.text.strip()

                    if not precio_texto:
                        # Sin precio detectable: se descarta el producto en vez de guardar 0.
                        continue

                    urls_vistas.add(url_prod)
                    productos_extraidos.append({
                        'nombre_original': nombre_prod,
                        'precio': limpiar_precio(precio_texto),
                        'url': url_prod
                    })
                    productos_en_esta_pagina += 1
                
                if productos_en_esta_pagina == 0: 
                    break
                pagina += 1
                time.sleep(random.uniform(3.5, 7.2)) 
                
            except Exception as e:
                break 

        return productos_extraidos