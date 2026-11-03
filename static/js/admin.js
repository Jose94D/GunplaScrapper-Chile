// --- Pestañas del panel: se muestra la que contiene el #ancla (#tiendas abre Resumen), o Resumen si no hay ---
// Corre apenas carga el script (al final del <body>) y no en DOMContentLoaded, para que no se vean todas un instante
(() => {
    const vistas = [...document.querySelectorAll('.vista-panel')];
    const enlaces = document.querySelectorAll('.panel-menu a');
    if (!vistas.length) return;
    const mostrar = () => {
        const destino = location.hash.length > 1 ? document.getElementById(location.hash.slice(1)) : null;
        const vista = (destino && destino.closest('.vista-panel')) || vistas[0];
        vistas.forEach((v) => { v.hidden = v !== vista; });
        enlaces.forEach((a) => {
            if (a.hash === '#' + vista.dataset.vista) a.setAttribute('aria-current', 'page');
            else a.removeAttribute('aria-current');
        });
        if (destino && destino.id !== vista.dataset.vista) destino.scrollIntoView();  // una sección dentro de la pestaña
        else window.scrollTo(0, 0);
    };
    window.addEventListener('hashchange', mostrar);
    mostrar();
})();

document.addEventListener('DOMContentLoaded', () => {
    // --- Modal de fusión (Bootstrap): se llena con el producto del botón que lo abrió ---
    const modalFusion = document.getElementById('modalFusion');
    if (modalFusion) {
        modalFusion.addEventListener('show.bs.modal', (e) => {
            document.getElementById('input_id_duplicado').value = e.relatedTarget.dataset.id;
            document.getElementById('textoDuplicado').textContent = e.relatedTarget.dataset.nombre;
            document.getElementById('id_principal').value = '';
        });
    }

    // --- Orden y cantidad por página se aplican al elegirlos ---
    document.querySelectorAll('select[data-autoenviar]').forEach((s) => s.addEventListener('change', () => s.form.submit()));

    // --- Forzar escaneo ---
    // El escaneo corre en segundo plano en el servidor; aquí se consulta su estado hasta que termina.
    const boton = document.getElementById('btn-forzar-escaneo');
    const estado = document.getElementById('estado-escaneo');
    if (!boton) return;
    const texto = boton.querySelector('span');

    const restaurar = (mensaje) => {
        texto.textContent = 'Forzar escaneo';
        boton.disabled = false;
        estado.textContent = mensaje;
    };

    const esperarFin = () => {
        fetch('/admin/force-update/estado')
            .then((r) => r.json())
            .then((data) => {
                if (data.en_curso) return setTimeout(esperarFin, 5000);
                estado.textContent = 'Escaneo terminado. Recargando el panel…';
                location.reload();
            })
            .catch(() => setTimeout(esperarFin, 5000));
    };

    boton.addEventListener('click', () => {
        texto.textContent = 'Escaneando…';
        boton.disabled = true;
        estado.textContent = 'Puede tardar varios minutos. Puedes seguir usando el panel; se recargará al terminar.';
        fetch('/admin/force-update', {
            method: 'POST',
            headers: { 'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content }
        })
            .then((r) => r.json())
            .then((data) => (data.status === 'started' ? esperarFin() : restaurar(data.message)))
            .catch(() => restaurar('No se pudo conectar con el servidor para iniciar el escaneo.'));
    });
});
