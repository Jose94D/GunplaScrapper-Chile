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
    const btnForzarEscaneo = document.getElementById('btn-forzar-escaneo');
    if (btnForzarEscaneo) {
        btnForzarEscaneo.addEventListener('click', function() {
            const btn = this;
            btn.innerText = '⏳ Escaneando... (revisa la terminal)';
            btn.disabled = true;
            btn.style.opacity = '0.7';

            fetch('/admin/force-update')
                .then(response => response.json())
                .then(data => {
                    if(data.status === 'success') {
                        alert('✅ ÉXITO:\n' + data.message);
                        location.reload(); 
                    } else {
                        alert('❌ ERROR:\n' + data.message);
                    }
                })
                .catch(error => {
                    alert('❌ ERROR CRÍTICO:\nNo se pudo conectar con el servidor para iniciar el escaneo.');
                })
                .finally(() => {
                    btn.innerText = '⚡ Forzar Escaneo';
                    btn.disabled = false;
                    btn.style.opacity = '1';
                });
        });
    }
});