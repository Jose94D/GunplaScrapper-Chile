document.addEventListener("DOMContentLoaded", () => {
    // --- LÓGICA DEL MODAL DE FUSIÓN ---
    const modalFusion = document.getElementById('modalFusion');
    const fondoModal = document.getElementById('fondoModal');
    const inputIdDuplicado = document.getElementById('input_id_duplicado');
    const textoDuplicado = document.getElementById('textoDuplicado');
    const idPrincipalSelect = document.getElementById('id_principal');
    const btnCerrarModal = document.getElementById('btn-cerrar-modal');
    
    // Abrir modal (Asignamos el evento a todos los botones de fusión)
    const botonesFusion = document.querySelectorAll('.btn-fusion');
    botonesFusion.forEach(boton => {
        boton.addEventListener('click', function() {
            const idDuplicado = this.getAttribute('data-id');
            const nombreDuplicado = this.getAttribute('data-nombre');
            
            inputIdDuplicado.value = idDuplicado;
            textoDuplicado.innerText = nombreDuplicado;
            modalFusion.style.display = 'block';
            fondoModal.style.display = 'block';
        });
    });

    // Cerrar modal
    function cerrarModal() {
        modalFusion.style.display = 'none';
        fondoModal.style.display = 'none';
        idPrincipalSelect.value = '';
    }

    if (btnCerrarModal) btnCerrarModal.addEventListener('click', cerrarModal);
    if (fondoModal) fondoModal.addEventListener('click', cerrarModal);

    // --- FUNCIÓN DEL BOTÓN DE ESCANEO ---
    // El escaneo corre en segundo plano en el servidor; aquí se consulta su estado hasta que termina.
    const btnForzarEscaneo = document.getElementById('btn-forzar-escaneo');
    if (btnForzarEscaneo) {
        const textoOriginal = btnForzarEscaneo.innerText;

        function restaurarBoton() {
            btnForzarEscaneo.innerText = textoOriginal;
            btnForzarEscaneo.disabled = false;
            btnForzarEscaneo.style.opacity = '1';
        }

        function esperarFin() {
            fetch('/admin/force-update/estado')
                .then(response => response.json())
                .then(data => {
                    if (data.en_curso) {
                        setTimeout(esperarFin, 5000);
                    } else {
                        alert('✅ Escaneo terminado. El detalle está en "Últimos Eventos del Sistema".');
                        location.reload();
                    }
                })
                .catch(() => setTimeout(esperarFin, 5000));
        }

        btnForzarEscaneo.addEventListener('click', function() {
            btnForzarEscaneo.innerText = '⏳ Escaneando... (puede tardar varios minutos)';
            btnForzarEscaneo.disabled = true;
            btnForzarEscaneo.style.opacity = '0.7';

            fetch('/admin/force-update', {
                method: 'POST',
                headers: { 'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content }
            })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'started') {
                        esperarFin();
                    } else {
                        alert('⚠️ ' + data.message);
                        restaurarBoton();
                    }
                })
                .catch(() => {
                    alert('❌ ERROR CRÍTICO:\nNo se pudo conectar con el servidor para iniciar el escaneo.');
                    restaurarBoton();
                });
        });
    }
});