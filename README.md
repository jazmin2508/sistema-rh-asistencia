# Sistema RH - Control de Asistencia

Aplicación web en Python + Streamlit + SQLite.

## Ejecutar en Windows

1. Instala Python 3.11 o superior.
2. Abre PowerShell en esta carpeta.
3. Ejecuta:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

4. Abre la dirección que muestre Streamlit, normalmente:
`http://localhost:8501`

## Usuario inicial

- Usuario: `admin`
- Contraseña: `admin123`

Cámbiala después de entrar.

## Publicar en Internet

Sube estos archivos a un repositorio de GitHub y despliega `app.py` en Streamlit Community Cloud.
La aplicación crea `rh.db` automáticamente.

**Nota:** SQLite es adecuada para una instalación pequeña/pruebas. Para uso empresarial con muchos usuarios simultáneos, conviene migrar a PostgreSQL.
