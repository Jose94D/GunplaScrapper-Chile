from datetime import datetime
from core.database import execute_query

def registrar_log(accion):
    """Registra una acción en la base de datos o consola."""
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    execute_query("INSERT INTO logs (fecha_registro, accion) VALUES (?, ?)", (fecha_actual, accion), commit=True)
    print(f"[{fecha_actual}] LOG: {accion}")

def ultimos_eventos(cantidad=10):
    """[(fecha_registro, accion), ...] del más reciente al más antiguo."""
    return execute_query("SELECT fecha_registro, accion FROM logs ORDER BY id DESC LIMIT ?", (cantidad,), fetchall=True)
