import requests
from bs4 import BeautifulSoup
import time
from core.logger import registrar_log

class HangarScraper:
    def __init__(self):
        self.base_url = "https://www.hangar019.cl"
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    def extraer_datos(self):
        """Scraper puro. Retorna una lista de productos extraídos."""
        pagina = 1
        productos_extraidos = []
        urls_vistas = set()

        while True:
            try:
                res = requests.get(f"{self.base_url}/8-gunpla?p={pagina}", headers=self.headers, timeout=15)
                soup = BeautifulSoup(res.text, 'html.parser')
                nombres = soup.find_all('a', class_='product-name')
                
                if not nombres: break 
                
                bucle_detectado = False
                
                for n in nombres:
                    url_prod = n['href'] if n['href'].startswith('http') else self.base_url + n['href']
                    nombre_prod = n.text.strip()
                    
                    contenedor = n.find_parent('div', class_='product-container') or n.find_parent('li')
                    if not contenedor: continue
                    
                    p = contenedor.find('span', class_='product-price') or contenedor.find('span', itemprop='price')
                    if not p: continue
                        
                    precio_oferta = p.text.strip()
                    p_base_element = contenedor.find('span', class_='old-price') or contenedor.find('span', class_='regular-price')
                    precio_base = p_base_element.text.strip() if p_base_element and p_base_element.text.strip() else precio_oferta
                    
                    if url_prod in urls_vistas:
                        bucle_detectado = True
                        break 
                        
                    urls_vistas.add(url_prod)
                    
                    productos_extraidos.append({
                        'producto': nombre_prod,
                        'precio': precio_oferta,
                        'precio_base': precio_base,
                        'url': url_prod
                    })
                
                if bucle_detectado: break
                pagina += 1
                time.sleep(2) 
                
            except Exception as e:
                registrar_log(f"Error en Hangar019 (Pág {pagina}): {str(e)}")
                break 

        return productos_extraidos