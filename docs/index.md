# YF GIS Amazonia Tools

Suite de herramientas GIS para **catastro, gestión forestal y topografía** en la Amazonía peruana, desarrollada sobre expedientes reales de Madre de Dios y conforme a la normativa peruana.

!!! tip "¿Primera vez?"
    Empiece por [instalar el plugin](instalacion/index.md). Si una herramienta le pide un componente que no tiene, la página de [componentes opcionales](instalacion/dependencias.md) explica cómo resolverlo incluso en equipos institucionales con la red restringida.

---

## Qué resuelve esta suite

El plugin nació de un problema concreto: en la Amazonía peruana un expediente técnico —una memoria descriptiva, un plano perimétrico, un informe de superposición— exige repetir siempre las mismas operaciones, y hacerlas a mano en QGIS consume horas y admite errores que después se pagan caro en el trámite. Cada herramienta automatiza una de esas operaciones **manteniendo la trazabilidad que un expediente necesita**.

Dos principios recorren toda la suite:

- **No se inventa información.** Si una capa no puede leerse, se reporta como *no evaluada*, nunca como libre de superposición. Un informe que afirma más de lo que comprobó no sirve como sustento técnico.
- **Todo resultado es reconstruible.** Los archivos locales se acreditan con SHA-256; los geoservicios, con URL, capa, hora y conteo de entidades.

---

## Las herramientas

### Catastral

| Herramienta | Para qué |
|---|---|
| [Memoria Descriptiva](herramientas/memoria_descriptiva.md) | Genera la memoria en Word con cuadro de vértices y narrativa de colindancias |
| [Segmentador de Parcelas](herramientas/segmentador.md) | Azimuts, ángulos internos y distancias por lado |
| [Calculadora de Geometría Vectorial](herramientas/vector_geometry.md) | Área, perímetro, centroide y azimut sobre la propia capa |
| [YF Tools Plus](herramientas/yf_tools_plus.md) | Tabla → Polígono desde Excel o CSV, con multipolígono |
| [Divisor de Polígonos](herramientas/polygon_divider.md) | División por área exacta, partes iguales o porcentajes |
| [Georreferenciador Inteligente](herramientas/smart_georeferencer.md) | Planos escaneados e imágenes de dron, en vivo sobre el lienzo |
| [Etiquetado Técnico](herramientas/smart_labels.md) | Vértices, distancias con azimut y bloques de área |
| [Exportar Expediente](herramientas/batch_export.md) | Carpeta estructurada lista para entregar |

### Geodesia y análisis

| Herramienta | Para qué |
|---|---|
| [Post-Proceso PPK / PPP](herramientas/gnss_postprocess.md) | RTKLIB con efemérides precisas y corrección ANTEX |
| [Análisis de Superposición](herramientas/superposition.md) | Contraste contra derechos preexistentes y áreas protegidas |
| [Búsqueda de Atributos](herramientas/attribute_search.md) | Búsqueda multicapa con reportes |
| [Generador SAF](herramientas/saf_generator.md) | Diseño de sistemas agroforestales |

### Producción cartográfica

| Herramienta | Para qué |
|---|---|
| [Generador de Cajetín](herramientas/title_block.md) | Cajetín con expresiones dinámicas de escala, fecha y datum |
| [Gestor de Estilos de Tabla](herramientas/layout_tools.md) | Estilos de tabla de atributos en el compositor |
| [Redimensionar Composición](herramientas/layout_rescaler.md) | Cambio de tamaño de papel conservando proporciones |
| [Comparación Visual (Swipe)](herramientas/swipe.md) | Cortina deslizante entre dos capas |
| [Navegación Go-To](herramientas/goto.md) | Ir a coordenadas en DD, GMS, UTM o MGRS |

---

## Requisitos

- **QGIS 3.22 o superior.** Compatible con QGIS 4.x (Qt6).
- **Windows, Linux o macOS.** Salvo el post-proceso GNSS, que usa binarios de RTKLIB para Windows.
- Ningún componente externo es obligatorio para arrancar. Los opcionales se instalan bajo demanda desde el propio plugin.

---

## Cómo leer este manual

Cada página de herramienta sigue la misma estructura: **para qué sirve**, **qué necesita antes de empezar**, **cómo se usa**, **qué produce** y **qué hacer cuando falla**. Esa última sección es la que más consultan quienes ya conocen la herramienta.

Los [casos reales](casos/superposicion_loboyoc.md) documentan expedientes completos, desde el dato de campo hasta el documento presentado. Sirven mejor que cualquier captura de pantalla para entender cuándo conviene usar cada herramienta.

---

## Autoría y licencia

Desarrollado por **Yuri Fabián Caller Córdova** (CIP N° 214377), especialista en GIS, Geomática y Geodesia, bajo **Training Universal Company SAC (TUCSA)**, Puerto Maldonado, Madre de Dios, Perú.

Software libre bajo licencia **GPL-3.0-or-later**. Iconos de [Font-GIS](https://viglino.github.io/font-gis/) (Jean-Marc Viglino, CC BY 4.0) y del proyecto QGIS (GPL).

[:material-github: Código y reporte de incidencias](https://github.com/YuriCaller/YF_GIS_AMAZONIA){ .md-button }
[:material-web: gis-amazonia.pe](https://yuricaller.github.io/gis-amazonia/){ .md-button }
