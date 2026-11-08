from core.logger import registrar_log
from core import ucp


class IrionScraper:
    """Irion (Shopify) por UCP: sus páginas de colección responden 429 a los scripts (ver core/ucp.py)."""

    def __init__(self):
        self.dominio = "irion.cl"

    def extraer_datos(self):
        try:
            productos = ucp.buscar_catalogo(self.dominio, "gundam")
        except Exception as e:
            registrar_log(f"Error en Irion (UCP): {e}")
            raise
        # Lo mismo que leía de la colección 'gundam': kits Bandai con stock. La búsqueda trae además pinturas,
        # otras marcas y agotados. Algunos productos de Bandai no tienen la etiqueta, pero sí la marca en el título.
        return [ucp.a_publicacion(p, p["url"].split("?")[0]) for p in productos
                if "GUNDAM" in (p.get("tags") or []) and ("BANDAI" in (p.get("tags") or []) or "BANDAI" in p["title"].upper())
                and ucp.disponible(p)]
