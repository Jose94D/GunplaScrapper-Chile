document.addEventListener('DOMContentLoaded', () => {
    // --- Vista del catálogo: cuadrícula o lista, recordada en este navegador ---
    const botonesVista = document.querySelectorAll('.selector-vista [data-vista]');
    const aplicarVista = (vista) => {
        document.documentElement.dataset.vista = vista;
        botonesVista.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.vista === vista)));
    };
    aplicarVista(document.documentElement.dataset.vista || 'grilla');
    botonesVista.forEach((boton) => boton.addEventListener('click', () => {
        aplicarVista(boton.dataset.vista);
        try { localStorage.setItem('vista', boton.dataset.vista); } catch (e) { /* sin almacenamiento: vale solo para esta visita */ }
    }));

    // --- Orden y cantidad por página se aplican al elegirlos ---
    document.querySelectorAll('select[data-autoenviar]').forEach((s) => s.addEventListener('change', () => s.form.submit()));

    // --- Carrusel: contador "01 / 04" y sin avance automático si el visitante pidió menos movimiento ---
    const carrusel = document.getElementById('novedades');
    const contador = document.getElementById('novedades-contador');
    if (carrusel && contador) {
        const total = contador.textContent.split('/')[1].trim();
        carrusel.addEventListener('slid.bs.carousel', (e) => {
            contador.textContent = `${String(e.to + 1).padStart(2, '0')} / ${total}`;
        });
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            bootstrap.Carousel.getOrCreateInstance(carrusel, { ride: false, interval: false }).pause();
        }
    }
});
