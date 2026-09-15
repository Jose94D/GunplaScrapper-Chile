document.addEventListener("DOMContentLoaded", () => {
    // --- Lógica del Cambio de Tema ---
    const themeBtn = document.getElementById('theme-toggle');
    const bannerImg = document.getElementById('main-banner');

    // 1. Sincronizar UI (Imágenes y botones) al cargar la página
    // No manipulamos el fondo principal aquí para evitar el parpadeo blanco.
    // El script en el <head> de base.html ya aplicó el data-theme a la etiqueta html.
    const currentTheme = localStorage.getItem('theme') || 'dark'; 
    
    if (currentTheme === 'dark') {
        // Aseguramos que el body también tenga el atributo por si tu CSS depende de él
        document.body.setAttribute('data-theme', 'dark');
        if (bannerImg) bannerImg.src = '/static/Banner_dark.png';
        if (themeBtn) themeBtn.innerHTML = '☀️ Modo Claro';
    } else {
        document.body.removeAttribute('data-theme');
        if (bannerImg) bannerImg.src = '/static/Banner_light.png';
        if (themeBtn) themeBtn.innerHTML = '🌙 Modo Oscuro';
    }

    // 2. Evento de Clic para alternar el tema
    if (themeBtn) {
        themeBtn.addEventListener('click', () => {
            // Verificamos el estado actual
            const isDark = document.documentElement.getAttribute('data-theme') === 'dark' || document.body.getAttribute('data-theme') === 'dark';
            const newTheme = isDark ? 'light' : 'dark';
            
            // Aplicamos los cambios al DOM (html y body para máxima compatibilidad)
            if (newTheme === 'dark') {
                document.documentElement.setAttribute('data-theme', 'dark');
                document.body.setAttribute('data-theme', 'dark');
                if (bannerImg) bannerImg.src = '/static/Banner_dark.png';
                if (themeBtn) themeBtn.innerHTML = '☀️ Modo Claro';
            } else {
                document.documentElement.removeAttribute('data-theme');
                document.body.removeAttribute('data-theme');
                if (bannerImg) bannerImg.src = '/static/Banner_light.png';
                if (themeBtn) themeBtn.innerHTML = '🌙 Modo Oscuro';
            }

            // Guardamos la preferencia
            localStorage.setItem('theme', newTheme);

            // Si existe un gráfico (Chart.js), recargamos la página para que tome los nuevos colores
            if (window.myChart) location.reload();
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