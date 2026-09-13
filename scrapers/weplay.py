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

class WeplayScraper:
    def __init__(self):
        self.base_url = "https://www.weplay.cl"
        self.categoria_path = "/figuras-y-juguetes/model-kits.html"
        self.query_params = "brand_id=2053"
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    def extraer_datos(self):
        pagina = 1
        productos_extraidos = []
        urls_vistas = set()

        while True:
            try:
                if pagina == 1:
                    url_pagina = f"{self.base_url}{self.categoria_path}?{self.query_params}"
                else:
                    url_pagina = f"{self.base_url}{self.categoria_path}?{self.query_params}&p={pagina}"

                res = requests.get(url_pagina, headers=self.headers, timeout=15)
                soup = BeautifulSoup(res.text, 'html.parser')

                tarjetas = soup.find_all('div', class_='product-item-info')

                if not tarjetas:
                    # No se detectaron productos en esta página: fin del catálogo.
                    break

                bucle_detectado = False

                for card in tarjetas:
                    # Se excluyen productos "Disponible solo en tienda" (class 'unavailable'):
                    # no se pueden comprar online, así que no representan un precio de compra real.
                    etiqueta = card.find('div', class_='product-label')
                    if etiqueta and 'unavailable' in etiqueta.get('class', []):
                        continue

                    nombre_tag = card.find('a', class_='product-item-link')
                    if not nombre_tag or not nombre_tag.get('href'):
                        continue

                    url_prod = nombre_tag['href'].split('?')[0]
                    nombre_prod = nombre_tag.get_text(strip=True)

                    # data-price-amount trae el precio limpio, sin formato ni símbolo de moneda
                    precio_tag = card.find(attrs={'data-price-amount': True})
                    if not precio_tag or not precio_tag.get('data-price-amount'):
                        continue
                    precio_texto = precio_tag['data-price-amount']

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
                registrar_log(f"Error en Weplay (Pág {pagina}): {str(e)}")
                break

        return productos_extraidos