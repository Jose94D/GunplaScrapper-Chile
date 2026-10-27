import re


def limpiar_precio(precio):
    """Convierte un precio en pesos chilenos a float.

    Acepta números o textos como '$19.990', '19,990' o 'CLP 19990': junta todos los dígitos,
    porque el peso no usa decimales. Retorna 0.0 si no hay ningún dígito.
    """
    if isinstance(precio, (int, float)):
        return float(precio)
    # shortcut: un texto con dos precios ('Antes $29.990 Ahora $19.990') junta ambos; cada scraper debe pasar solo el precio vigente
    numeros = re.findall(r'\d+', precio or '')
    return float(''.join(numeros)) if numeros else 0.0
