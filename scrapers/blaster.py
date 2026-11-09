from core.logger import registrar_log
from core import ucp

GRADOS = {"HG - High Grade", "MG - Master Grade", "RG - Real Grade", "SD - Standard Grade", "SD - Super deformed"}


class BlasterScraper:
    """Blaster (Shopify) por UCP: su colección respondía 429 a los scripts (ver core/ucp.py)."""

    def __init__(self):
        self.dominio = "www.blasterchile.cl"
        # La búsqueda ordena por relevancia y no es un listado exhaustivo: se juntan varias consultas
        # para que ningún kit con stock quede fuera (se marcaría como agotado por error)
        self.consultas = ("HG gundam", "MG gundam", "RG gundam", "SD gundam")

    def extraer_datos(self):
        productos = {}
        try:
            for consulta in self.consultas:
                for p in ucp.buscar_catalogo(self.dominio, consulta, {"available": True}):
                    productos[p["url"].split("?")[0]] = p
        except Exception as e:
            registrar_log(f"Error en Blaster (UCP): {e}")
            raise
        # Lo mismo que filtraba de su colección: kits Gundam de Bandai en HG, MG, RG y SD, con stock.
        # Los SD Cross Silhouette no traen etiqueta de grado, pero sí "SD" al inicio del título.
        return [ucp.a_publicacion(p, url) for url, p in productos.items()
                if {"Gundam", "Model Kit"} <= set(p.get("tags") or [])
                and (GRADOS & set(p.get("tags") or []) or p["title"].upper().startswith("SD "))
                and "bandai" in p["title"].lower() and ucp.disponible(p)]
