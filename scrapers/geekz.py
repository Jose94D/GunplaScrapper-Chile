import requests
from bs4 import BeautifulSoup
import time
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

class GeekzScraper:
    def __init__(self):
        self.base_url = "https://geekz.cl"
        self.categoria_path = "/shop/category/hobby-model-kit-9"
        self.query_params = "?attrib=0-102&min_price=&max_price=9999999.0&ppg=15"
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    def extraer_datos(self):
        pagina = 1
        productos_extraidos = []
        urls_vistas = set()

        while True:
            try:
                # Odoo pagina agregando '/page/N' entre la categoría y los query params
                if pagina == 1:
                    url_pagina = f"{self.base_url}{self.categoria_path}{self.query_params}"
                else:
                    url_pagina = f"{self.base_url}{self.categoria_path}/page/{pagina}{self.query_params}"

                res = requests.get(url_pagina, headers=self.headers, timeout=15)
                soup = BeautifulSoup(res.text, 'html.parser')

                # Cada producto es un <form class="... oe_product_cart ...">
                tarjetas = soup.find_all('form', class_='oe_product_cart')

                if not tarjetas:
                    # No se detectaron productos en esta página: fin del catálogo.
                    break

                bucle_detectado = False

                for form in tarjetas:
                    # Solo se guardan productos con el badge verde de stock.
                    # Si no está presente, el producto está agotado y se descarta.
                    badge_stock = form.find('span', class_='dr-product-label-color-green')
                    if not badge_stock or 'STOCK' not in badge_stock.get_text(strip=True).upper():
                        continue

                    titulo_tag = form.find('h6', itemprop='name')
                    url_tag = form.find('a', itemprop='url')
                    if not titulo_tag or not url_tag or not url_tag.get('href'):
                        continue

                    # El atributo 'content' del h6 trae el nombre completo, sin el truncamiento
                    # visual que aplica la clase CSS 'text-truncate'.
                    nombre_prod = titulo_tag.get('content', '').strip() or titulo_tag.get_text(strip=True)

                    # La URL trae parámetros de categoría/filtro (?category=9&attrib=...); se descartan
                    # para quedarnos con una URL estable y única por producto.
                    href = url_tag['href'].split('?')[0]
                    url_prod = href if href.startswith('http') else self.base_url + href

                    # Precio real: viene limpio (sin formato) en el span itemprop="price"
                    precio_tag = form.find('span', itemprop='price')
                    if not precio_tag or not precio_tag.get_text(strip=True):
                        continue
                    precio_texto = precio_tag.get_text(strip=True)

                    if url_prod in urls_vistas:
                        bucle_detectado = True
                        break

                    urls_vistas.add(url_prod)

                    productos_extraidos.append({
                        'nombre_original': nombre_prod,
                        'precio': limpiar_precio(precio_texto),
                        'url': url_prod
                    })

                if bucle_detectado:
                    break
                pagina += 1
                time.sleep(2)

            except Exception as e:
                registrar_log(f"Error en Geekz (Pág {pagina}): {str(e)}")
                break

        return productos_extraidos