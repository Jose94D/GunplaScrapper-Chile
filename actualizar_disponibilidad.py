from core.database import init_db, actualizar_disponibilidad_productos

if __name__ == "__main__":
    init_db()  # asegura que la columna 'disponible' exista si la DB es antigua
    total = actualizar_disponibilidad_productos()
    print(f"Disponibilidad recalculada. Productos 'No disponible': {total}")
