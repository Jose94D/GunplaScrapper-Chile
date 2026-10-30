// Formularios con data-confirmar piden confirmación antes de enviarse (reemplaza los onsubmit, que la CSP bloquea)
document.addEventListener('submit', (e) => {
    const mensaje = e.target.dataset.confirmar;
    if (mensaje && !confirm(mensaje)) e.preventDefault();
});

document.addEventListener("DOMContentLoaded", () => {
    // --- Tema claro/oscuro ---
    // El <head> de base.html ya aplicó el tema guardado; aquí se sincronizan el banner y el botón,
    // y se alterna al hacer clic. data-theme lo usan nuestros estilos y data-bs-theme los de Bootstrap.
    const themeBtn = document.getElementById('theme-toggle');
    const bannerImg = document.getElementById('main-banner');
    const esOscuro = () => document.documentElement.getAttribute('data-theme') === 'dark';

    function aplicarTema(oscuro) {
        if (oscuro) document.documentElement.setAttribute('data-theme', 'dark');
        else document.documentElement.removeAttribute('data-theme');
        document.documentElement.setAttribute('data-bs-theme', oscuro ? 'dark' : 'light');
        if (bannerImg) bannerImg.src = oscuro ? bannerImg.dataset.srcDark : bannerImg.dataset.srcLight;
        // El icono (sol o luna) cambia por CSS; aquí solo la etiqueta para lectores de pantalla
        if (themeBtn) themeBtn.setAttribute('aria-label', oscuro ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro');
    }

    aplicarTema(esOscuro());

    if (themeBtn) {
        themeBtn.addEventListener('click', () => {
            const oscuro = !esOscuro();
            aplicarTema(oscuro);
            try { localStorage.setItem('theme', oscuro ? 'dark' : 'light'); } catch (e) { /* sin almacenamiento: vale solo para esta visita */ }
            // Las páginas que dibujan con colores del tema (el gráfico de producto) escuchan este evento
            document.dispatchEvent(new Event('temacambiado'));
        });
    }
});
