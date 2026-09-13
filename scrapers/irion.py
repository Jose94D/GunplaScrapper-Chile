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

class IrionScraper:
    def __init__(self):
        self.base_url = "https://irion.cl"
        # IMPORTANTE: no agregar '?sort_by=' ni múltiples 'filter.*' a esta URL.
        # El robots.txt de irion.cl (Shopify) bloquea explícitamente esos patrones
        # como "crawl traps" (Disallow: /collections/*sort_by* y /collections/*filter*&*filter*).
        # Por eso se usa la colección 'gundam' sin parámetros, y el filtro por marca
        # (Bandai) se hace acá abajo, en código, no vía query string.
        self.coleccion_url = f"{self.base_url}/collections/gundam"
        self.marca_objetivo = "bandai"
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    def extraer_datos(self):
        pagina = 1
        productos_extraidos = []
        urls_vistas = set()

        while True:
            try:
                # Paginación simple (?page=N), no está afectada por ninguna regla de Disallow.
                url_pagina = self.coleccion_url if pagina == 1 else f"{self.coleccion_url}?page={pagina}"

                res = requests.get(url_pagina, headers=self.headers, timeout=15)
                soup = BeautifulSoup(res.text, 'html.parser')

                # Cada producto viene envuelto en el elemento personalizado <product-card>
                tarjetas = soup.find_all('product-card')

                if not tarjetas:
                    # No se detectaron productos en esta página: fin del catálogo.
                    break

                bucle_detectado = False

                for card in tarjetas:
                    # Filtramos solo la marca objetivo (Bandai); el resto de 'gundam'
                    # incluye pinturas y accesorios de otras marcas.
                    vendor_tag = card.find('div', class_='product-vendor')
                    marca = vendor_tag.get_text(strip=True) if vendor_tag else ''
                    if marca.strip().lower() != self.marca_objetivo:
                        continue

                    titulo_tag = card.find('h3', class_='product-card_title')
                    n = titulo_tag.find('a') if titulo_tag else None
                    if not n or not n.get('href'):
                        continue

                    # La URL trae parámetros de tracking de Shopify (_pos, _fid, _ss); se descartan
                    # para que la publicación quede identificada por una URL estable y única.
                    href = n['href'].split('?')[0]
                    url_prod = href if href.startswith('http') else self.base_url + href
                    nombre_prod = n.text.strip()

                    # Precio efectivo (el que se paga, con o sin descuento)
                    precio_tag = card.find('div', class_='price-sale')
                    if not precio_tag or not precio_tag.text.strip():
                        continue
                    precio_texto = precio_tag.text.strip()

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
                registrar_log(f"Error en Irion (Pág {pagina}): {str(e)}")
                break

        return productos_extraidos