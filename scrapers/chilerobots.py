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

def reconstruir_nombre_desde_url(url):
    """
    PrestaShop a veces trunca el texto visible del nombre del producto
    (termina en '...'), pero el slug de la URL siempre trae el nombre completo.
    Se usa como respaldo únicamente cuando se detecta truncamiento.
    Ej: '.../142-sinanju-stein-narrative-ver-hg-1-144-bandai.html'
        -> 'Sinanju Stein Narrative VER HG 1/144 Bandai'
    """
    try:
        slug = url.rstrip('/').rsplit('/', 1)[-1]
        if slug.endswith('.html'):
            slug = slug[:-5]
        slug = re.sub(r'^\d+-', '', slug)              # quita el ID numérico inicial (ej: '142-')
        slug = re.sub(r'(?<=\d)-(?=\d)', '/', slug)    # restaura escalas: '1-144' -> '1/144'
        palabras = [p for p in slug.split('-') if p]
        if not palabras:
            return None
        # Palabras cortas (grados, siglas: HG, MG, EG, GBC...) se dejan en mayúscula;
        # el resto se capitaliza normalmente.
        nombre = ' '.join(p.upper() if len(p) <= 3 else p.capitalize() for p in palabras)
        return nombre.strip() or None
    except Exception:
        return None

class ChileRobotsScraper:
    def __init__(self):
        self.base_url = "https://www.chilerobots.cl"
        self.categoria_url = f"{self.base_url}/10-gundam"
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    def extraer_datos(self):
        pagina = 1
        productos_extraidos = []
        urls_vistas = set()

        while True:
            try:
                # La primera página no lleva query params; desde la 2 en adelante
                # se pide la vista completa (?cr_view=all) igual que navega el catálogo real.
                if pagina == 1:
                    url_pagina = self.categoria_url
                else:
                    url_pagina = f"{self.categoria_url}?page={pagina}&cr_view=all"

                res = requests.get(url_pagina, headers=self.headers, timeout=15)
                soup = BeautifulSoup(res.text, 'html.parser')

                titulos = soup.find_all('h2', class_='product-title')

                if not titulos:
                    # No se detectaron productos en esta página: fin del catálogo.
                    break

                bucle_detectado = False

                for h in titulos:
                    n = h.find('a')
                    if not n or not n.get('href'):
                        continue

                    url_prod = n['href'] if n['href'].startswith('http') else self.base_url + n['href']
                    nombre_prod = n.text.strip()

                    # PrestaShop a veces trunca el nombre visible (termina en '...' o '…').
                    # En ese caso se reconstruye desde el slug de la URL, que siempre viene completo.
                    if nombre_prod.endswith('...') or nombre_prod.endswith('…'):
                        nombre_reconstruido = reconstruir_nombre_desde_url(url_prod)
                        if nombre_reconstruido:
                            nombre_prod = nombre_reconstruido

                    # El bloque de precios vive en el mismo contenedor 'product-description' que el título
                    contenedor = h.find_parent('div', class_='product-description')
                    if not contenedor:
                        continue

                    # Precio en oferta (span.price); si no existe, se usa el precio regular (span.regular-price)
                    p_oferta = contenedor.find('span', class_='price')
                    p_regular = contenedor.find('span', class_='regular-price')

                    if p_oferta and p_oferta.text.strip():
                        precio_texto = p_oferta.text.strip()
                    elif p_regular and p_regular.text.strip():
                        precio_texto = p_regular.text.strip()
                    else:
                        continue

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
                registrar_log(f"Error en ChileRobots (Pág {pagina}): {str(e)}")
                break

        return productos_extraidos