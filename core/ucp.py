"""Catálogo de tiendas Shopify por UCP (Universal Commerce Protocol), el canal que Shopify ofrece a los clientes automáticos.

Desde noviembre de 2026 Shopify responde 429 a las páginas de colección pedidas por scripts que no se identifican.
UCP es la alternativa oficial: cada consulta lleva la dirección del perfil del scraper (static/ucp-agente.json),
que Shopify descarga y valida. El perfil solo declara búsqueda en el catálogo: no puede comprar ni crear carritos.
"""
import json
import time

from config import URL_SITIO
from core.peticiones import pedir

# Shopify guarda el perfil en caché un día: al cambiar ucp-agente.json, subir ?v= para que lo vuelva a leer
PERFIL = (URL_SITIO or "https://www.gunplascraper-chile.cl") + "/static/ucp-agente.json?v=2"
POR_PAGINA = 250  # menos consultas por escaneo: UCP limita las consultas seguidas (429 con espera de más de media hora)
MAX_PAGINAS = 40  # tope de seguridad: una paginación que nunca termina no deja el escaneo pegado


def buscar_catalogo(dominio, consulta, filtros=None):
    """Todos los productos que devuelve search_catalog para `consulta`, recorriendo sus páginas.
    Lanza una excepción ante cualquier error: un scraper nunca debe devolver un catálogo a medias."""
    productos, cursor, cursores_vistos = [], None, set()
    for _ in range(MAX_PAGINAS):
        catalogo = {"query": consulta, "context": {"address_country": "CL", "currency": "CLP"}, "pagination": {"limit": POR_PAGINA}}
        if filtros:  # p. ej. {"available": True}: Shopify corta la búsqueda en 1000 resultados, filtrar en origen la achica
            catalogo["filters"] = filtros
        if cursor:
            catalogo["pagination"]["cursor"] = cursor
        res = pedir(f"https://{dominio}/api/ucp/mcp", headers={"Accept": "application/json"}, json={
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "search_catalog", "arguments": {"meta": {"ucp-agent": {"profile": PERFIL}}, "catalog": catalogo}}})
        try:
            datos = res.json()
        except ValueError:  # una página de error de Cloudflare u otra respuesta que no es JSON
            res.raise_for_status()
            raise
        if "error" in datos:  # p. ej. el perfil no se pudo leer: Shopify lo explica en data.content
            raise RuntimeError(f"UCP {res.status_code}: {json.dumps(datos['error'], ensure_ascii=False)[:300]}")
        res.raise_for_status()
        resultado = datos["result"]
        if resultado.get("isError"):
            raise RuntimeError(f"UCP: {json.dumps(resultado, ensure_ascii=False)[:300]}")
        pagina = resultado.get("structuredContent") or json.loads(resultado["content"][0]["text"])
        for p in pagina.get("products", []):
            p.setdefault("url", f"https://{dominio}/products/{p['handle']}")  # algunos productos vienen sin url
            productos.append(p)
        paginacion = pagina.get("pagination") or {}
        cursor = paginacion.get("cursor")
        if not paginacion.get("has_next_page") or not cursor or cursor in cursores_vistos:
            return productos
        cursores_vistos.add(cursor)
        time.sleep(1)
    raise RuntimeError(f"UCP: {dominio} tiene más de {MAX_PAGINAS} páginas para '{consulta}'")


def disponible(producto):
    """search_catalog también devuelve productos sin stock: cuenta si alguna variante se puede comprar."""
    return any((v.get("availability") or {}).get("available") for v in producto.get("variants", []))


def a_publicacion(producto, url):
    """Producto UCP al formato que esperan ScraperManager y el catálogo. CLP no tiene decimales: el monto ya está en pesos."""
    media = producto.get("media") or []
    return {
        "nombre_original": producto["title"].strip(),
        "precio": float(producto["price_range"]["min"]["amount"]),
        "url": url,
        "imagen": media[0]["url"] if media else None,
    }
