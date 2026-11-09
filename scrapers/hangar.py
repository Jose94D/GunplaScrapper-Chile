from bs4 import BeautifulSoup
import time
from core.logger import registrar_log
from core.precios import limpiar_precio
from core.peticiones import pedir
from core.imagenes import url_imagen

class HangarScraper:
    def __init__(self):
        self.base_url = "https://www.hangar019.cl"
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    def extraer_datos(self):
        pagina = 1
        productos_extraidos = []
        urls_vistas = set()

        while True:
            try:
                res = pedir(f"{self.base_url}/8-gunpla?p={pagina}", headers=self.headers)
                if res.status_code == 404 and pagina > 1:
                    break  # algunas tiendas responden 404 al pasar la última página
                res.raise_for_status()
                soup = BeautifulSoup(res.text, 'html.parser')
                nombres = soup.find_all('a', class_='product-name')
                
                if not nombres: 
                    break 
                
                bucle_detectado = False
                
                for n in nombres:
                    url_prod = n['href'] if n['href'].startswith('http') else self.base_url + n['href']
                    nombre_prod = n.text.strip()
                    
                    contenedor = n.find_parent('div', class_='product-container') or n.find_parent('li')
                    if not contenedor: 
                        continue
                    
                    p = contenedor.find('span', class_='product-price') or contenedor.find('span', itemprop='price')
                    if not p: 
                        continue
                        
                    precio_oferta = p.text.strip()
                    
                    if url_prod in urls_vistas:
                        bucle_detectado = True
                        break 
                        
                    urls_vistas.add(url_prod)

                    # El catálogo lista agotados con un aviso "Agotado" que solo se ve al pasar el mouse.
                    # Va después de urls_vistas: una última página repetida solo con agotados debe cortar el bucle.
                    # Ese aviso es solo de la tienda online: si alguna sucursal lo tiene, sigue disponible.
                    if contenedor.find('span', class_='out-of-stock') and not self.disponible_en_sucursal(url_prod):
                        continue

                    productos_extraidos.append({
                        'nombre_original': nombre_prod,
                        'precio': limpiar_precio(precio_oferta),
                        'url': url_prod,
                        'imagen': url_imagen(contenedor, self.base_url)
                    })
                
                if bucle_detectado: 
                    break
                pagina += 1
                time.sleep(2) 
                
            except Exception as e:
                registrar_log(f"Error en Hangar019 (Pág {pagina}): {str(e)}")
                raise 

        return productos_extraidos

    def disponible_en_sucursal(self, url):
        """La ficha del producto dice "Disponible" o "Agotado" por tienda online y por cada sucursal física."""
        time.sleep(1)
        res = pedir(url, headers=self.headers)
        if res.status_code == 404:  # el listado aún muestra algunos productos cuya ficha ya no existe
            return False
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        return any(s.get_text(strip=True).lower() == 'disponible'
                   for s in soup.find_all('span', class_='product_stocks_by_shop_content'))