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

class HobbyToysScraper:
    def __init__(self):
        self.base_url = "https://www.hobbytoys.cl"
        self.categoria_url = f"{self.base_url}/categoria-producto/model-kit/gundam-modelkit/"
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    def extraer_datos(self):
        pagina = 1
        productos_extraidos = []
        urls_vistas = set()

        while True:
            try:
                url_pagina = self.categoria_url if pagina == 1 else f"{self.categoria_url}page/{pagina}/"

                res = requests.get(url_pagina, headers=self.headers, timeout=15)
                soup = BeautifulSoup(res.text, 'html.parser')

                tarjetas = soup.find_all('div', class_='wpr-grid-item-inner')

                if not tarjetas:
                    # No se detectaron productos en esta página: fin del catálogo.
                    break

                bucle_detectado = False

                for card in tarjetas:
                    titulo_tag = card.find('h2', class_='wpr-grid-item-title')
                    n = titulo_tag.find('a') if titulo_tag else None
                    if not n or not n.get('href'):
                        continue

                    url_prod = n['href'].split('?')[0]
                    nombre_prod = n.text.strip()

                    precio_container = card.find('div', class_='wpr-grid-item-price')
                    if not precio_container:
                        continue

                    # WooCommerce muestra el precio en oferta dentro de <ins>, y el precio
                    # original tachado dentro de <del>. Si no hay oferta, solo existe el
                    # span.amount suelto (precio regular).
                    tag_oferta = precio_container.find('ins')
                    if tag_oferta:
                        amount_tag = tag_oferta.find('span', class_='amount')
                    else:
                        amount_tag = precio_container.find('span', class_='amount')

                    if not amount_tag or not amount_tag.get_text(strip=True):
                        continue
                    precio_texto = amount_tag.get_text(strip=True)

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
                registrar_log(f"Error en HobbyToys (Pág {pagina}): {str(e)}")
                break

        return productos_extraidos