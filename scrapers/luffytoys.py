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

class LuffyToysScraper:
    def __init__(self):
        self.base_url = "https://luffytoys.cl"
        # IMPORTANTE: no agregar '?sort_by=' a esta URL. El robots.txt de luffytoys.cl
        # (Shopify) bloquea explícitamente ese patrón como "crawl trap"
        # (Disallow: /collections/*sort_by*). El orden de los resultados no nos
        # importa para el scraping, así que se usa la colección sin ese parámetro.
        self.coleccion_url = f"{self.base_url}/collections/maqueta-armables/gundam"
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    def extraer_datos(self):
        pagina = 1
        productos_extraidos = []
        urls_vistas = set()

        while True:
            try:
                # Paginación simple (?page=N), no afectada por ninguna regla de Disallow.
                url_pagina = self.coleccion_url if pagina == 1 else f"{self.coleccion_url}?page={pagina}"

                res = requests.get(url_pagina, headers=self.headers, timeout=15)
                soup = BeautifulSoup(res.text, 'html.parser')

                # Cada producto viene envuelto en un contenedor con clase 'thumbnail'
                tarjetas = soup.find_all('div', class_='thumbnail')

                if not tarjetas:
                    # No se detectaron productos en esta página: fin del catálogo.
                    break

                bucle_detectado = False

                for card in tarjetas:
                    enlace = card.find('a', class_='product-info__caption')
                    if not enlace or not enlace.get('href'):
                        continue

                    nombre_tag = enlace.find('span', class_='title')
                    nombre_prod = nombre_tag.get_text(strip=True) if nombre_tag else enlace.get_text(strip=True)
                    if not nombre_prod:
                        continue

                    # Precio efectivo (con o sin descuento); el 'compare-at-price'
                    # (precio tachado original) se ignora a propósito.
                    precio_tag = enlace.find('span', class_='price')
                    money_tag = precio_tag.find('span', class_='money') if precio_tag else None
                    if not money_tag or not money_tag.get_text(strip=True):
                        continue
                    precio_texto = money_tag.get_text(strip=True)

                    href = enlace['href'].split('?')[0]
                    url_prod = href if href.startswith('http') else self.base_url + href

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
                registrar_log(f"Error en LuffyToys (Pág {pagina}): {str(e)}")
                break

        return productos_extraidos