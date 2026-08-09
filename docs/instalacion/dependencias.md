# Componentes opcionales

La suite arranca sin necesidad de instalar nada más. Algunas herramientas concretas, en cambio, necesitan un componente adicional de Python. Esta página explica cuáles son y **qué hacer cuando la instalación falla**, que es la incidencia más reportada del plugin.

## Qué necesita cada herramienta

| Componente | Lo necesita | ¿Obligatorio? |
|---|---|---|
| `python-docx` | [Memoria Descriptiva](../herramientas/memoria_descriptiva.md), reportes Word de [Búsqueda de Atributos](../herramientas/attribute_search.md) | Sí, para generar el documento |
| `opencv-python` | Detección automática de puntos de control en el [Georreferenciador](../herramientas/smart_georeferencer.md) | No. La captura manual funciona sin él |
| `winsdk` | OCR nativo de Windows en [Go-To](../herramientas/goto.md) | No. Hay respaldo por Tesseract y entrada manual |
| `openpyxl` | Lectura de `.xlsx` en [YF Tools Plus](../herramientas/yf_tools_plus.md) | Normalmente ya viene con QGIS |

RTKLIB, que usa el [post-proceso GNSS](../herramientas/gnss_postprocess.md), no es un paquete de Python: se descarga solo la primera vez que ejecuta un procesamiento.

---

## Instalación normal

Abra la herramienta. Si falta el componente, aparece una ventana que explica qué se va a instalar, para qué sirve y cuánto pesa. Pulse **Instalar ahora** y espere.

!!! info "Dónde queda instalado"
    En su perfil de QGIS, en `python/dependencies`. No se modifica la instalación de QGIS ni el Python del sistema, no hacen falta permisos de administrador, y el componente **sobrevive a las actualizaciones del plugin**: no tendrá que volver a descargarlo.

Si todo va bien, la herramienta se desbloquea sin reiniciar QGIS.

---

## Cuando la instalación falla

En direcciones regionales, gobiernos regionales y oficinas de SERFOR es habitual que la red bloquee la descarga. El plugin traduce el error de `pip` a una causa legible; a continuación, qué hacer con cada una.

### «La conexión pasa por un proxy que bloqueó la descarga»

Es el caso más frecuente en entidades públicas.

Si en QGIS ya tiene el proxy configurado (porque de otro modo no le cargarían los servicios WMS), **el plugin lo reutiliza automáticamente**. Compruébelo en `Configuración → Opciones → Red`: deben estar marcados el proxy y rellenos servidor y puerto. Vuelva a intentar la instalación después de guardarlo.

Si no conoce los datos del proxy, pídalos al área de sistemas o use la [instalación sin internet](#instalacion-sin-internet).

### «El certificado SSL fue rechazado»

La red de la entidad inspecciona el tráfico cifrado. No intente desactivar la verificación de certificados: use la [instalación sin internet](#instalacion-sin-internet), que no toca la red.

### «Sin permisos de escritura»

No debería ocurrir con la instalación en el perfil, pero si aparece, verifique que su usuario puede escribir en su propia carpeta de perfil de QGIS. La ruta exacta aparece en **Acerca de → Diagnóstico**.

### «No se pudo alcanzar el repositorio de paquetes (PyPI)»

El equipo no tiene salida a internet. Vaya directamente a la [instalación sin internet](#instalacion-sin-internet).

---

## Instalación sin internet

Funciona en cualquier escenario de los anteriores. Necesita otro equipo con conexión y una memoria USB.

**1. En el equipo con internet**, descargue el archivo `.whl` desde PyPI:

- python-docx: <https://pypi.org/project/python-docx/#files>
- opencv-python: <https://pypi.org/project/opencv-python/#files>

Elija el archivo terminado en `-py3-none-any.whl` cuando exista (sirve para cualquier sistema). Para `opencv-python`, que trae código compilado, elija el que corresponda a su Windows y a la versión de Python de QGIS —esa versión aparece en **Acerca de → Diagnóstico**.

**2. Copie el archivo** a una USB y llévelo al equipo de trabajo.

**3. En QGIS**, abra la herramienta que necesita el componente. Cuando aparezca la ventana, pulse **Instalar desde archivo .whl...** y seleccione el archivo.

!!! warning "python-docx necesita dos archivos"
    `python-docx` depende de `lxml`, que puede no estar en su QGIS. Si la instalación desde `.whl` se queja de una dependencia ausente, descargue también el `.whl` de [lxml](https://pypi.org/project/lxml/#files) e instálelo primero.

---

## Instalación manual desde la consola

Si prefiere la línea de órdenes, o si el área de sistemas va a hacerlo por usted, esta es la forma correcta.

!!! danger "No use `python -m pip install python-docx` a secas"
    Es el error que más problemas causa. En una instalación OSGeo4W conviven varios intérpretes de Python, y `python` a secas puede no ser el que QGIS utiliza. El resultado es desconcertante: `pip` informa *Successfully installed* y la herramienta sigue bloqueada, porque el paquete quedó en un Python que QGIS nunca lee.

**1. Obtenga las rutas exactas.** En QGIS, abra `Complementos → YF GIS Amazonia Tools → Acerca de` y pulse **Diagnóstico**. Copie las líneas `Intérprete pip` y `Carpeta paquetes`.

**2. Abra la consola de OSGeo4W** (menú Inicio → QGIS → *OSGeo4W Shell*).

**3. Ejecute**, sustituyendo por sus rutas y **conservando las comillas**:

```bat
"C:\OSGeo4W\apps\Python312\python.exe" -m pip install --target "C:\Users\USUARIO\AppData\Roaming\QGIS\QGIS3\profiles\default\python\dependencies" python-docx
```

En Linux o macOS es equivalente, con las rutas propias del sistema:

```bash
/usr/bin/python3 -m pip install --target ~/.local/share/QGIS/QGIS3/profiles/default/python/dependencies python-docx
```

**4. Reinicie QGIS** y abra la herramienta.

---

## Comprobar el estado

`Complementos → YF GIS Amazonia Tools → Acerca de → Diagnóstico` muestra el intérprete que usa el plugin, la carpeta de paquetes, si está en `sys.path` y qué componentes están disponibles.

Ese texto es lo que conviene adjuntar al [reportar una incidencia](https://github.com/YuriCaller/YF_GIS_AMAZONIA/issues): el botón **Copiar** lo deja en el portapapeles.

---

## Preguntas frecuentes

**¿Se pierde al actualizar el plugin?**
No. Los componentes viven en el perfil de QGIS, no en la carpeta del plugin.

**¿Y si uso varios perfiles de QGIS?**
Cada perfil tiene su propia carpeta. Tendrá que instalar el componente en cada uno.

**¿Puedo desinstalarlos?**
Sí. Borre la carpeta `python/dependencies` de su perfil. La ruta está en **Diagnóstico**.

**Instalé el componente y la herramienta sigue bloqueada.**
Reinicie QGIS. Si persiste, revise en **Diagnóstico** que la carpeta de paquetes figure como presente en `sys.path`; si no, es probable que el paquete se instalara en otro Python — repita la instalación manual usando exactamente la ruta que indica el diagnóstico.
