document.addEventListener("DOMContentLoaded", () => {
    // Lógica del Cambio de Tema
    const themeBtn = document.getElementById('theme-toggle');
    const bannerImg = document.getElementById('main-banner');

    function applyTheme(theme) {
        if (theme === 'dark') {
            document.body.setAttribute('data-theme', 'dark');
            if(bannerImg) bannerImg.src = '/static/Banner_dark.png';
            if(themeBtn) themeBtn.innerHTML = '☀️ Modo Claro';
        } else {
            document.body.removeAttribute('data-theme');
            if(bannerImg) bannerImg.src = '/static/Banner_light.png';
            if(themeBtn) themeBtn.innerHTML = '🌙 Modo Oscuro';
        }
    }

    const currentTheme = localStorage.getItem('theme') || 'dark';
    applyTheme(currentTheme);

    if(themeBtn) {
        themeBtn.addEventListener('click', () => {
            let newTheme = document.body.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
            localStorage.setItem('theme', newTheme);
            applyTheme(newTheme);
            if(window.myChart) location.reload();
        });
    }

    // Lógica del Efecto Spotlight (Cursor en Tarjetas)
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

    // Lógica del Carrusel
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