# Qué hacer con este paquete

Cambios para **YF GIS Amazonia Tools v3.0.7**: manual en línea, `about` resumido y corrección de la instalación de componentes opcionales.

---

## 1. Archivos del plugin

Copie sobre su copia de trabajo del plugin:

```
metadata.txt                        ← reemplaza
core/dependencies.py                ← reemplaza
core/about_dialog.py                ← reemplaza
core/plugin_manager.py              ← reemplaza (ya parcheado)
core/tools_catalog.py               ← NUEVO
core/tests/test_catalogo.py         ← NUEVO
core/tests/__init__.py              ← NUEVO (vacío)
```

Nada más cambia. La API pública de `dependencies.py` se mantiene, así que `memoria_descriptiva/__init__.py` y `attribute_search/ui/report_panel.py` siguen funcionando sin tocarlos.

### Verificar antes de empaquetar

```bash
python -m unittest core.tests.test_catalogo -v
python -m flake8 --max-line-length=100 core/
python -m bandit -r core/
```

Los tres pasan limpios en esta entrega.

---

## 2. Publicar el manual

```
mkdocs.yml
requirements-docs.txt
docs/
.github/workflows/docs.yml
```

Van en la **raíz del repositorio** `YF_GIS_AMAZONIA`, junto a la carpeta del plugin.

**Activar GitHub Pages:** en el repositorio, `Settings → Pages → Source: GitHub Actions`. El flujo se dispara al tocar `docs/` o `mkdocs.yml` y publica en:

```
https://yuricaller.github.io/YF_GIS_AMAZONIA/
```

**Probar en local antes de subir:**

```bash
pip install -r requirements-docs.txt
mkdocs serve          # http://127.0.0.1:8000
mkdocs build --strict # falla si hay un enlace roto
```

!!! Si su usuario o repositorio tienen otro nombre, ajuste `DOCS_BASE` en `core/tools_catalog.py`, `MANUAL_URL` en `core/dependencies.py`, `site_url` en `mkdocs.yml` y `homepage` en `metadata.txt`.

---

## 3. Ayuda contextual (opcional, recomendado)

Para poner un botón `?` en cada diálogo de herramienta:

```python
from ...core.tools_catalog import abrir_ayuda

btn = QPushButton("?")
btn.setFixedWidth(28)
btn.setToolTip("Abrir el manual de esta herramienta")
btn.clicked.connect(lambda: abrir_ayuda("superposition"))  # clave del catálogo
```

La clave es la misma que el `tool_id` del menú. El test comprueba que exista la página correspondiente.

---

## Qué se corrigió y por qué

### Instalación de componentes

`--user` fallaba en OSGeo4W de dos formas que el usuario no podía distinguir: pip lo rechazaba por detectar un entorno tipo virtualenv, o instalaba en un directorio que QGIS no lee — y ahí pip decía *Successfully installed* mientras la herramienta seguía bloqueada.

Ahora se instala con `--target` en `<perfil>/python/dependencies`, que siempre es escribible, no necesita administrador, sobrevive a reinstalaciones del plugin y está bajo control del propio plugin en `sys.path`.

Se añade además: instalación desde `.whl` sin internet, traslado automático del proxy de QGIS a pip (pip no lee esa configuración por su cuenta) y un botón **Diagnóstico** en «Acerca de».

### Changelog truncado — fallo preexistente

Las líneas `Version X.Y.Z (fecha):` empezaban en la columna 0 dentro del valor de `changelog`, lo que corta el parseo de `configparser`. **El repositorio de QGIS venía mostrando solo la primera entrada**: 1 843 de 29 194 caracteres. Ya está sangrado y se leen las 26 versiones.

### El «Acerca de»

La lista estaba escrita a mano y anunciaba 8 herramientas de 17, con etiquetas «nuevo v2.0» un año después. Ahora se genera desde `core/tools_catalog.py`, que es también la fuente del manual, y el test falla si ambas listas divergen.

### El campo `about`

De 4 877 a 1 918 caracteres. El detalle técnico versión por versión se movió al `changelog` y al manual, que es donde alguien puede buscarlo.

---

## Pendiente

**YF Designer** y sus módulos no entran en esta versión, según lo acordado. Cuando se publiquen, añadir la entrada en `core/tools_catalog.py` y la página `docs/herramientas/<clave>.md`; el test recordará ambos pasos si se olvida alguno.

**Capturas de pantalla.** El manual no lleva ninguna. Conviene añadirlas en `docs/assets/` y referenciarlas desde cada página cuando tenga ocasión.
