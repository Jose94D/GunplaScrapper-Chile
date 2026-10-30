from datetime import datetime, timedelta
from core.database import execute_query, transaccion

def registrar_log(accion):
    """Registra una acción en la base de datos o consola."""
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    execute_query("INSERT INTO logs (fecha_registro, accion) VALUES (?, ?)", (fecha_actual, accion), commit=True)
    print(f"[{fecha_actual}] LOG: {accion}")

def borrar_eventos_antiguos(dias=90):
    """Borra los eventos de más de `dias` días y retorna cuántos. Se llama después del respaldo diario, que aún los tiene."""
    limite = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
    with transaccion() as conn:
        return conn.execute("DELETE FROM logs WHERE fecha_registro < ?", (limite,)).rowcount

def ultimos_eventos(cantidad=10):
    """[(fecha_registro, accion), ...] del más reciente al más antiguo."""
    return execute_query("SELECT fecha_registro, accion FROM logs ORDER BY id DESC LIMIT ?", (cantidad,), fetchall=True)
