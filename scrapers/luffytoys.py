from core.logger import registrar_log
from core import ucp


class LuffyToysScraper:
    """LuffyToys (Shopify) por UCP: sus páginas de colección responden 429 a los scripts (ver core/ucp.py)."""

    def __init__(self):
        self.base_url = "https://luffytoys.cl"
        self.dominio = "luffytoys.cl"

    def extraer_datos(self):
        try:
            productos = ucp.buscar_catalogo(self.dominio, "gundam")
        except Exception as e:
            registrar_log(f"Error en LuffyToys (UCP): {e}")
            raise
        # Las etiquetas equivalen a la colección maqueta-armables/gundam que se leía antes (la búsqueda trae también figuras).
        # La URL conserva el formato de esa colección para que cada kit siga en su misma publicación, con su historial.
        return [ucp.a_publicacion(p, f"{self.base_url}/collections/maqueta-armables/products/{p['handle']}") for p in productos
                if {"Maqueta Armable", "Gundam"} <= set(p.get("tags") or []) and ucp.disponible(p)]
