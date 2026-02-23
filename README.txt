
INSTRUCCIONES DE USO - TABLERO DE CONTROL DOCUMENTAL

1. REQUISITOS
   - Python instalado (ya lo tienes).
   - Librerías: streamlit, pandas, pypdf, watchdog.
     (Si falta alguna, ejecuta: pip install streamlit pandas pypdf watchdog)

2. CÓMO INICIAR
   - Haz doble clic en el archivo "run_app.bat" en esta carpeta.
   - O abre una terminal aquí y ejecuta: `python -m streamlit run dashboard.py`

3. FUNCIONALIDADES
   - **NUEVAS CATEGORÍAS**: Memorias, Proceso Constructivo, Geométrico, ODT.
   - **EDICIÓN INTERACTIVA**: Marca "Revisado", cambia Estado y edita Notas DIRECTAMENTE en la tabla.
   - **VERSIONES**: Detecta automáticamente versiones en nombres de archivo (v1, RevA, etc.).
   - Escanea automáticamente carpeta y subcarpetas.
   - Filtros avanzados: Por Proyecto, Categoría, Estado y "Ocultar Revisados".
   - Persistencia automática en "notes.json".

4. PERSONALIZACIÓN
   - Puedes editar "dashboard.py" para personalizar lógica o colores.

¡Listo para usar!
