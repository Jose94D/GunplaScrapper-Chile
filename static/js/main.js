document.addEventListener("DOMContentLoaded", () => {
    // --- Tema claro/oscuro ---
    // El <head> de base.html ya aplicó el tema guardado en <html data-theme>; aquí se sincroniza
    // el banner y el botón, y se alterna al hacer clic.
    const themeBtn = document.getElementById('theme-toggle');
    const bannerImg = document.getElementById('main-banner');
    const esOscuro = () => document.documentElement.getAttribute('data-theme') === 'dark';

    function aplicarTema(oscuro) {
        if (oscuro) document.documentElement.setAttribute('data-theme', 'dark');
        else document.documentElement.removeAttribute('data-theme');
        if (bannerImg) bannerImg.src = oscuro ? bannerImg.dataset.srcDark : bannerImg.dataset.srcLight;
        if (themeBtn) themeBtn.innerHTML = oscuro ? '☀️ Modo Claro' : '🌙 Modo Oscuro';
    }

    aplicarTema(esOscuro());

    if (themeBtn) {
        themeBtn.addEventListener('click', () => {
            const oscuro = !esOscuro();
            aplicarTema(oscuro);
            localStorage.setItem('theme', oscuro ? 'dark' : 'light');
            // Las páginas que dibujan con colores del tema (el gráfico de producto) escuchan este evento
            document.dispatchEvent(new Event('temacambiado'));
        });
    }

    // --- Lógica del Efecto Spotlight (Cursor en Tarjetas) ---
    document.addEventListener('mousemove', (e) => {
        const cards = document.querySelectorAll('.stat-card, .project-card');
        
        cards.forEach(card => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            card.style.setProperty('--mouse-x', `${x}px`);
            card.style.setProperty('--mouse-y', `${y}px`);
        });
    });

    // --- Lógica del Carrusel ---
    const slides = document.getElementById('carousel-slides');
    const prevBtn = document.getElementById('btn-carousel-prev');
    const nextBtn = document.getElementById('btn-carousel-next');

    if (slides) {
        let currentSlide = 0;
        const totalSlides = document.querySelectorAll('.carousel-slide').length;

        function moveSlide(direction) {
            if (totalSlides === 0) return;
            currentSlide += direction;
            if (currentSlide < 0) currentSlide = totalSlides - 1;
            if (currentSlide >= totalSlides) currentSlide = 0;
            slides.style.transform = `translateX(-${currentSlide * 100}%)`;
        }

        // Asignar eventos de clic a los botones
        if (prevBtn) prevBtn.addEventListener('click', () => moveSlide(-1));
        if (nextBtn) nextBtn.addEventListener('click', () => moveSlide(1));

        // Autoplay
        if (totalSlides > 1) {
            setInterval(() => moveSlide(1), 5000);
        }
    }
});