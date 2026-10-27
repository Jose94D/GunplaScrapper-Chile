"""Credenciales del administrador (fila id = 1 de la tabla usuarios)."""
from datetime import datetime

from werkzeug.security import generate_password_hash

from core.database import execute_query
from core.logger import registrar_log


def obtener_credenciales_admin():
    """(email, hash_clave) del administrador, o None si todavía se usan las del .env."""
    return execute_query("SELECT email, hash_clave FROM usuarios WHERE id = 1", fetchone=True)


def guardar_credenciales_admin(usuario, clave):
    """Guarda usuario y contraseña (como hash). Crea la fila id = 1 si todavía no existe."""
    hash_clave = generate_password_hash(clave)
    if obtener_credenciales_admin():
        execute_query("UPDATE usuarios SET email = ?, hash_clave = ? WHERE id = 1", (usuario, hash_clave), commit=True)
    else:
        execute_query(
            "INSERT INTO usuarios (id, email, hash_clave, rol, fecha_creacion) VALUES (1, ?, ?, 'admin', ?)",
            (usuario, hash_clave, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            commit=True
        )
    registrar_log(f"Se actualizaron las credenciales. Nuevo usuario: {usuario}")
