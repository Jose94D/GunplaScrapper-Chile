"""Peticiones a las tiendas con reintentos: un corte o un 'demasiadas peticiones' puntual no hace perder el escaneo."""
import time

import requests

# Respuestas que suelen ser pasajeras: límite de peticiones o el servidor de la tienda caído un momento
REINTENTABLES = {429, 500, 502, 503, 504}
ESPERA_MAXIMA = 60  # segundos; si la tienda pide más, se respeta el máximo y se deja para el siguiente escaneo


def _retry_after(respuesta):
    """Segundos que pide esperar la tienda en la cabecera Retry-After, o None si no viene o no es un número."""
    valor = respuesta.headers.get('Retry-After', '').strip()
    return int(valor) if valor.isdigit() else None


def pedir(url, headers=None, sesion=None, intentos=3, espera_base=5):
    """
    GET a una tienda. Ante 429, 5xx o un corte de conexión espera y reintenta hasta `intentos` veces:
    lo que pida la tienda en Retry-After o, si no pide nada, espera_base x número de intento (5 s, 10 s...).
    Retorna la última respuesta (el scraper decide si es un error) y relanza el último corte de conexión.
    `sesion` permite usar cloudscraper (Blaster) en vez de requests.
    """
    cliente = sesion or requests
    for intento in range(1, intentos + 1):
        try:
            respuesta = cliente.get(url, headers=headers, timeout=15)
        except (requests.ConnectionError, requests.Timeout):
            if intento == intentos:
                raise
            espera = espera_base * intento
        else:
            if respuesta.status_code not in REINTENTABLES or intento == intentos:
                return respuesta
            espera = _retry_after(respuesta) or espera_base * intento
        time.sleep(min(espera, ESPERA_MAXIMA))
