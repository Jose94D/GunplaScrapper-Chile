"""Visitas del sitio: una fila por visitante y por día, con las páginas que vio.

- Visitas: días-visitante (la misma persona que vuelve otro día suma otra visita).
- Personas únicas: visitantes distintos en el período, según la cookie anónima `visitante`.
- Páginas vistas: cada página pública que se abrió.

Solo cuentan las páginas que avisan desde el navegador (main.js): los bots que no ejecutan JavaScript no inflan las cifras.
"""
import re
from datetime import date, timedelta

from core.database import execute_query, transaccion

# Rastreadores que sí ejecutan JavaScript (Googlebot, vistas previas de enlaces) o herramientas automáticas
UA_BOTS = re.compile(r"bot|crawl|spider|slurp|headless|lighthouse|preview|python|curl|wget|scrap", re.I)
VISITANTE_VALIDO = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
RANGOS = (7, 30, 90, 365, 0)  # días; 0 = todo el historial


def es_bot(user_agent):
    return not user_agent or bool(UA_BOTS.search(user_agent))


def registrar_visita(visitante, dia=None):
    dia = dia or date.today().isoformat()
    with transaccion() as conn:
        # INSERT + UPDATE en vez de ON CONFLICT: funciona también con el SQLite antiguo de algunos hostings
        conn.execute("INSERT OR IGNORE INTO visitas_diarias (dia, visitante, paginas) VALUES (?, ?, 0)", (dia, visitante))
        conn.execute("UPDATE visitas_diarias SET paginas = paginas + 1 WHERE dia = ? AND visitante = ?", (dia, visitante))


def serie_diaria():
    """Datos del gráfico del panel: un punto por día desde la primera visita hasta hoy (los días sin visitas en 0),
    y los totales de cada rango, porque las personas únicas no se pueden sumar día a día en el navegador."""
    filas = execute_query("SELECT dia, COUNT(*), SUM(paginas) FROM visitas_diarias GROUP BY dia ORDER BY dia", fetchall=True)
    por_dia = {dia: (visitas, paginas) for dia, visitas, paginas in filas}
    hoy = date.today()
    dia = date.fromisoformat(filas[0][0]) if filas else hoy
    fechas, visitas, paginas = [], [], []
    while dia <= hoy:
        v, p = por_dia.get(dia.isoformat(), (0, 0))
        fechas.append(dia.strftime("%d/%m/%Y"))
        visitas.append(v)
        paginas.append(p)
        dia += timedelta(days=1)

    totales = {}
    for dias in RANGOS:
        desde = (hoy - timedelta(days=dias - 1)).isoformat() if dias else ""
        t = execute_query("SELECT COUNT(*), COUNT(DISTINCT visitante), COALESCE(SUM(paginas), 0) FROM visitas_diarias WHERE dia >= ?",
                          (desde,), fetchone=True)
        totales[dias] = {"visitas": t[0], "personas": t[1], "paginas": t[2]}
    return {"fechas": fechas, "visitas": visitas, "paginas": paginas, "totales": totales}
