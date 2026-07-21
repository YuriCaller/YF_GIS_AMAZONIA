# YF GIS Amazonia Tools

*Read this in: [English](README.md) · **Español***

**Suite profesional de herramientas GIS para catastro, topografía, geodesia GNSS y gestión agroforestal en la Amazonía peruana.**

[![QGIS](https://img.shields.io/badge/QGIS-3.22%2B-green.svg)](https://qgis.org/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.5.1-brightgreen.svg)](metadata.txt)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

---

## Descripción

**YF GIS Amazonia Tools** es un plugin unificado para QGIS que integra un conjunto de herramientas especializadas para profesionales de topografía, catastro, geodesia y gestión forestal. Reúne en una sola suite coherente —organizada por áreas temáticas— funcionalidades que de otro modo estarían dispersas en múltiples plugins.

El plugin está diseñado para el flujo de trabajo real del ingeniero forestal, topógrafo o especialista GIS: desde el levantamiento GNSS en campo, pasando por el post-proceso de coordenadas y la georreferenciación de planos, hasta la generación de memorias descriptivas, cartografía y reportes técnicos conforme a los estándares del IGN Perú, SERFOR y GOREMAD.

Aunque nació para la Amazonía peruana, hoy se usa en más de 20 países.

---

## Novedades v2.5.0 – v2.5.1

- **Sistema ANTEX / correcciones PCO-PCV (2.5.0):** el campo de antena ya no es documental. Nuevo gestor ANTEX (descarga IGS20, parseo, archivos custom de fabricante, lectura del header RINEX de la base); las correcciones de centro de fase de receptor/satélite ahora sí se aplican cuando hay ANTEX válido y nombre de antena. Soporte universal de antenas (Trimble, CHCNAV, Leica, South, Emlid, Mettatec…).
- **Arreglos de diálogos Qt6 (2.5.1):** corregidos los errores 'no attribute Accepted' en QGIS 4 en Smart Labels, Layout Rescaler, Batch Export, Vector Geometry y Generar Cajetín.

## Novedades v2.4.0

- **Smart Georeferencer (NUEVO):** georreferenciador dinámico en vivo para planos escaneados y ortofotos de dron. Captura de puntos de control estilo ArcGIS, autoensamblado a vértices, detección automática con OpenCV, motor de warp TPS y un diagnóstico de calidad *leave-one-out* que detecta puntos de control inconsistentes. Se integra en el submenú **Catastral**. (Detalle más abajo.)

## Novedades v2.3.0

- **GNSS — Modo Ocupación (estilo TBC/Pathfinder):** detecta marcas de evento de ocupación (Trimble Geo7X/DA2) dentro de un RINEX continuo y resuelve cada punto ocupado por separado, sin promediar entre puntos distintos. Salida: una capa con todos los puntos (H1, H2…) y un reporte de calidad por punto.
- **GNSS — DGPS submétrico:** posicionamiento diferencial por código (sin resolución de ambigüedad), donde los falsos fix son imposibles. Precisión honesta de 0.3–1 m, ideal bajo dosel.
- **GNSS — Procesamiento por lotes:** procesa varios rover contra una base en una sola corrida.

## Novedades v2.2.1

- **Soporte Qt6 / QGIS 4:** corre en builds Qt5 (QGIS 3.x) y Qt6 (QGIS 4.x) mediante el shim `qgis.PyQt`. Retrocompatible con QGIS 3.22+.

---

## Destacado: Smart Georeferencer

Georreferenciador **dinámico y en vivo**, pensado para encajar planos catastrales escaneados y ortofotos de dron con precisión de vértice. Complementa al georreferenciador nativo de QGIS aportando dos diferenciales que este no tiene: **autoensamblado a vértices en tiempo real** y un **diagnóstico de calidad leave-one-out**.

- **Colocación inmediata:** un botón coloca la imagen en el canvas y en el panel de capas, lista para georreferenciar.
- **Captura de GCP estilo ArcGIS (dos clics):** clic en una entidad de la imagen → clic en el punto de control del mapa. El ancla de origen queda fija y una flecha guía conecta ambos puntos.
- **Autoensamblado (snapping):** el punto de control destino se pega a los vértices de tus capas de referencia, usando la configuración de snapping de QGIS. Precisión catastral.
- **Detección automática de GCP:** mediante OpenCV (SIFT/ORB + RANSAC). OpenCV se instala solo en el primer uso; **solo se necesita para la detección automática** — la captura manual funciona sin él.
- **Motor de warp TPS en dos etapas:** la imagen se deforma y sigue el pan/zoom junto con el resto del mapa.
- **Diagnóstico de calidad leave-one-out (LOO):** detecta puntos de control inconsistentes (mal medidos o mal digitalizados). Con TPS el residual normal es cero por construcción, así que el LOO usa un modelo afín que sí aísla al punto problemático. Heatmap de color sobre los marcadores (verde/ámbar/rojo) y lista ordenada de peor a mejor. Requiere ≥5 GCP para ser fiable.
- **Gestión de puntos:** menú contextual (clic derecho) para agregar, borrar o editar las coordenadas XY de un punto, y para cargar GCP desde CSV/Excel (columnas `pixelX, pixelY, mapX, mapY`).
- **Exportación:** GeoTIFF a resolución completa (TPS o polinomial) y opción de fijar la capa georreferenciada de forma permanente.
- **Compatibilidad de formatos:** los orígenes JPEG/JFIF (escaneos de CamScanner, etc.) se decodifican a GeoTIFF para un warp confiable.

---

## Herramientas integradas

Todas las herramientas están **completamente integradas y funcionando** dentro de un único menú principal en QGIS, organizadas en submenús temáticos.

### Catastral

| Herramienta | Descripción |
|---|---|
| **Memoria Descriptiva** | Generador automático de memorias descriptivas en Word (.docx) para saneamiento físico-legal de predios rurales. Modos: polígono único, atlas completo (una memoria por polígono) y atlas por selección. Auto-detecta capas adyacentes para identificar colindantes. |
| **Segmentador de Parcelas** | División y segmentación de polígonos en líneas y vértices con cálculo automático de azimuts y ángulos. Nombres de capa con prefijo de origen para evitar colisiones en GeoPackage. |
| **Calcular Geometría Vectorial** | Calcula área, perímetro, centroides, coordenadas, longitud y azimut (GMS/decimal) directamente sobre la misma capa, sin crear capas nuevas. Método dual: Elipsoidal (`$area`) o Planar (`area($geometry)`) para planos legales y catastro. Polígonos, líneas y puntos. |
| **YF Tools Plus** | Suite topográfica: creación de polígonos desde Excel/CSV, segmentación con herencia de campos, exportación a Excel con un clic, recálculo de atributos geométricos. Soporte de multipart y anillos interiores. |
| **Polygon Divider — Dividir Polígono** | Divide un polígono por área exacta, N partes iguales o porcentajes, usando una línea de corte trazada o definida por ángulo (resaltado rojo, estilo "Divide" de ArcGIS Pro). Capa de salida opcional en GeoPackage con atributos heredados y etiquetado automático, o edición in situ con confirmación. 100% `QgsGeometry` nativo, sin dependencias externas. |
| **Smart Georeferencer — Georreferenciar en vivo** *(NUEVO v2.4.0)* | Georreferenciador dinámico para planos escaneados y ortofotos de dron: captura de GCP estilo ArcGIS, autoensamblado a vértices, detección automática con OpenCV, warp TPS, diagnóstico leave-one-out, importación de GCP desde CSV/Excel y exportación a GeoTIFF. (Ver sección destacada.) |
| **Smart Labels — Etiquetar capa** | Etiquetado inteligente desde clic derecho en el canvas. Auto-detecta el tipo de geometría y aplica estilos técnicos: vértices V-01/V-02, distancia+azimut en líneas, bloque área+perímetro en polígonos. Usa expresiones dinámicas (`$area`, `$perimeter`, `$length`). |
| **Exportar Expediente (Batch Export)** | Exporta todas las capas y composiciones a una carpeta estructurada (SHP + GPKG + PDF + XLSX + metadatos) en un clic. Plantillas para GOREMAD, SERFOR, ACCA y entrega simple. Compresión ZIP opcional. |

### Geodesia / GNSS

| Herramienta | Descripción |
|---|---|
| **Post-Proceso PPK/PPP** | Procesamiento GNSS diferencial con RTKLIB, validado en campo contra Trimble Business Center. Descarga automática de efemérides precisas (SP3+CLK Final/Rapid de ESA/IGS) según la fecha del RINEX. Instalación automática del motor rnx2rtkp. Autocompletado de base desde el header del RINEX (estilo TBC). Altura de antena rover/base. Modo Ocupación (varios puntos en un RINEX), DGPS submétrico y procesamiento por lotes. Validación anti-falso-fix y promedio ponderado 1/σ². Reportes PDF. |

### Agroforestal / Ambiental

| Herramienta | Descripción |
|---|---|
| **SAF Generator** | Generador de sistemas agroforestales con varios métodos de distribución espacial. Identificación única por planta, orientación personalizada de filas con captura en canvas y simbología automática por especie. |

### Búsqueda y Análisis

| Herramienta | Descripción |
|---|---|
| **Búsqueda Avanzada de Atributos** | Búsqueda multi-capa con expresiones simples o avanzadas (expresiones QGIS). Visualización con gráficos, generación de reportes, exportación a CSV/Excel, zoom y resaltado de entidades encontradas. |

### Layout / Compositor

| Herramienta | Descripción |
|---|---|
| **Generar Cajetín (Title Block)** | Generador de cajetines profesionales con 4 plantillas (Sencillo, BIM/Técnico, Catastral/Forestal, Premium). Expresiones dinámicas para escala, fecha y CRS. Flecha de norte, mapa de ubicación, leyenda y miniatura de situación integrados; elementos agrupados automáticamente. |
| **Redimensionar Layout (Layout Rescaler)** | Redimensiona todos los elementos del layout proporcionalmente al cambiar el tamaño de papel, preservando posiciones relativas con un snapshot proporcional. Integrado en la barra del compositor. |
| **Table Style Manager** | Aplica, copia y pega estilos de tablas de atributos en el compositor. 5 estilos predefinidos. Copiar/pegar entre tablas. Exportar/importar estilos como JSON. |

### Comparación Visual

| Herramienta | Descripción |
|---|---|
| **Swipe Tool** | Comparación visual de capas estilo ArcGIS Pro (cortina deslizante). |

### Navegación

| Herramienta | Descripción |
|---|---|
| **Go-To (Ir a coordenadas)** | Navegación a coordenadas con entrada multi-formato (UTM, geográficas, GMS) y pegado inteligente. |

---

## Instalación

### Requisitos

- **QGIS 3.22** o superior (probado hasta 3.40+; compatible con QGIS 4.x / Qt6)
- Python 3.9+
- **python-docx** (requerido para Memoria Descriptiva)

Dependencias opcionales (según la herramienta que uses):
- `opencv-python-headless` — para la **detección automática de GCP** en Smart Georeferencer (se instala sola en el primer uso; la captura manual no la necesita)
- `pandas` + `matplotlib` — para reportes y visualización en Búsqueda de Atributos
- `reportlab` — para reportes PDF en GNSS Post-Process
- `RTKLIB` — binario externo para post-proceso GNSS (se descarga solo en la primera corrida)

### Instalación desde ZIP (recomendado)

1. Descargar el [último release](https://github.com/YuriCaller/YF_GIS_AMAZONIA/releases) o el ZIP del repositorio.
2. En QGIS: **Complementos → Administrar e instalar complementos → Instalar desde ZIP**.
3. Seleccionar el ZIP e **Instalar complemento**.
4. El menú **YF GIS Amazonia** aparecerá en la barra de menú superior.

> **Al actualizar desde una versión previa**, lo más confiable es desinstalar la versión anterior y reiniciar QGIS por completo antes de instalar la nueva, para evitar que queden módulos en caché.

### Instalación manual

1. Clonar o descargar este repositorio.
2. Copiar la carpeta `yf_gis_amazonia_tools/` a:
   ```
   Windows: %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\
   Linux:   ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/
   macOS:   ~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/
   ```
3. Reiniciar QGIS.
4. Activar en **Complementos → Administrar e instalar complementos → Instalados**.

### Dependencias Python

Abrir **OSGeo4W Shell** (Windows) o terminal (Linux/macOS) y ejecutar:

```bash
python -m pip install python-docx pandas matplotlib reportlab
```

(OpenCV se instala automáticamente la primera vez que uses la detección automática de GCP.)

---

## Uso

Tras la instalación aparece un menú **YF GIS Amazonia** con sus submenús temáticos:

```
YF GIS Amazonia
├── Catastral
│   ├── Memoria Descriptiva
│   ├── Segmentador de Parcelas
│   ├── Calcular Geometría Vectorial
│   ├── YF Tools Plus
│   ├── Polygon Divider — Dividir Polígono
│   ├── Smart Georeferencer — Georreferenciar en vivo   (NUEVO)
│   ├── Smart Labels — Etiquetar capa
│   └── Exportar Expediente
├── Geodesia / GNSS
│   └── Post-Proceso PPK/PPP
├── Agroforestal / Ambiental
│   └── SAF Generator
├── Búsqueda y Análisis
│   └── Búsqueda Avanzada de Atributos
├── Layout / Compositor
│   ├── Generar Cajetín
│   ├── Redimensionar Layout
│   └── Table Style Manager
├── Comparación Visual
│   └── Swipe Tool
├── Navegación
│   └── Go-To (Ir a coordenadas)
└── Acerca de...
```

Cada herramienta abre su propio diálogo o panel acoplable con la funcionalidad completa.

---

## Arquitectura

El plugin usa una arquitectura modular con carga diferida (lazy) de herramientas:

```
yf_gis_amazonia_tools/
├── __init__.py              # Entry point (classFactory)
├── metadata.txt             # Metadata de QGIS
├── LICENSE                  # GNU GPL v3
├── README.md
├── icons/                   # Iconos del plugin
├── core/                    # Infraestructura compartida
│   ├── plugin_manager.py    # Orquestador y menú principal
│   ├── tool_registry.py     # Registro con carga lazy
│   ├── base_tool.py         # Clase base para herramientas
│   ├── logger.py            # Logger unificado (QGIS Message Log)
│   ├── coord_parser.py      # Parseo de coordenadas multi-formato
│   ├── crs_utils.py         # Utilidades CRS/UTM
│   └── qt_compat.py         # Compatibilidad PyQt5/PyQt6
└── tools/                   # Herramientas (submódulos)
    ├── memoria_descriptiva/
    ├── segmentador/
    ├── vector_geometry/
    ├── yf_tools_plus/
    ├── polygon_divider/
    ├── smart_georeferencer/     # NUEVO v2.4.0
    ├── smart_labels/
    ├── batch_export/
    ├── gnss_postprocess/
    ├── saf_generator/
    ├── attribute_search/
    ├── layout_tools/
    ├── layout_rescaler/
    ├── swipe/
    └── goto/
```

Cada herramienta expone una clase `Tool(BaseTool)` con método `run()`. Las herramientas se cargan solo al ser invocadas por primera vez, minimizando el tiempo de arranque de QGIS.

---

## Compatibilidad

> ✅ **Qt5 y Qt6:** compatible con QGIS 3.22+ (Qt5/PyQt5) y QGIS 4.x (Qt6/PyQt6) mediante el shim `qgis.PyQt`.

- **QGIS 3.22 LTR** — Soporte completo
- **QGIS 3.28 / 3.34 LTR** — Soporte completo
- **QGIS 3.40+ / 4.x** — Soporte completo (PyQt6)
- **Windows / Linux / macOS**

---

## Autor

**Ing. Yuri Fabián Caller Córdova**
- **CIP N° 214377** — Ingeniero Forestal
- Especialista GIS / GNSS / Fotogrametría
- Empresa: **Training Universal Company SAC (TUCSA)**
- Ubicación: Puerto Maldonado, Madre de Dios, Perú
- Email: yuricaller@gmail.com
- Web: [gis-amazonia.pe](https://gis-amazonia.pe)

---

## Contribuciones

Las contribuciones son bienvenidas. Para reportar bugs o solicitar funcionalidades, abre un [issue](https://github.com/YuriCaller/YF_GIS_AMAZONIA/issues).

Para contribuir código:
1. Fork del repositorio.
2. Crear una rama para tu feature (`git checkout -b feature/mi-feature`).
3. Commit de los cambios (`git commit -m 'Agregar mi-feature'`).
4. Push a la rama (`git push origin feature/mi-feature`).
5. Abrir un Pull Request.

---

## Licencia

Este proyecto está licenciado bajo la **GNU General Public License v3.0**. Ver el archivo [LICENSE](LICENSE) para los términos completos.

---

## Agradecimientos

- **Equipo de QGIS** por la plataforma y las APIs que hacen posible este plugin.
- **RTKLIB** por la biblioteca de procesamiento GNSS de código abierto.
- **OpenCV**, **python-docx**, **reportlab**, **pyproj** y demás bibliotecas que sustentan las herramientas.
- **Comunidad forestal y catastral de Madre de Dios**, cuyas necesidades reales guían el desarrollo de este plugin.
