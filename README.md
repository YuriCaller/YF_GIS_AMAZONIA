# YF GIS Amazonia Tools

**Professional GIS toolkit for cadastral regularization, surveying, GNSS post-processing and agroforestry management in the Peruvian Amazon.**

[![QGIS](https://img.shields.io/badge/QGIS-3.22%2B-green.svg)](https://qgis.org/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.0.0-brightgreen.svg)](metadata.txt)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

---

## Descripción

**YF GIS Amazonia Tools** es un plugin unificado para QGIS que integra seis herramientas especializadas para profesionales de topografía, catastro, geodesia y gestión forestal en la Amazonía peruana. Combina funcionalidades que antes estaban dispersas en múltiples plugins en una sola suite coherente, organizada por áreas temáticas.

El plugin está diseñado para el flujo de trabajo real del ingeniero forestal, topógrafo o especialista GIS peruano: desde el levantamiento GNSS en campo, pasando por el procesamiento de coordenadas, hasta la generación de memorias descriptivas y reportes técnicos conforme a los estándares del IGN Perú y SERFOR.

---

## Herramientas integradas

Todas las herramientas están **completamente integradas y funcionando** dentro de un único menú principal en QGIS.

### Catastral

| Herramienta | Descripción |
|---|---|
| **Memoria Descriptiva** v3.2 | Generador automático de memorias descriptivas en Word (.docx) para saneamiento físico-legal de predios rurales. Tres modos: polígono único, atlas completo (una memoria por cada polígono), o atlas por selección. Auto-detecta capas adyacentes para identificación de colindantes. |
| **Segmentador de Parcelas** | División y segmentación de polígonos en líneas y vértices con cálculo automático de azimuts y ángulos internos/externos. Delega a la pestaña de segmentación de YF Tools Plus. |
| **YF Tools Plus** v2.3 | Suite de herramientas topográficas: creación de polígonos desde Excel/CSV, segmentación con herencia de campos, exportación a Excel con un clic, recalculación de atributos geométricos. Soporte completo de polígonos multipart y anillos interiores. |

### Geodesia / GNSS

| Herramienta | Descripción |
|---|---|
| **Post-Proceso PPK/PPP** v2.0 | Procesamiento GNSS diferencial con RTKLIB. Validación geodésica estricta de bases, generación de reportes PDF con estructura IGN Perú (UTM, Geográficas, Cartesianas), archivos .cor para submisión al IGN, exportación a SHP, GPKG, KML y GeoJSON. |

### Agroforestal / Ambiental

| Herramienta | Descripción |
|---|---|
| **SAF Generator** v2.1 | Generador profesional de sistemas agroforestales con seis métodos de distribución espacial (Hash, Ajedrez, Filas, Bloques, Aleatorio, Secuencial). Identificación única por planta (A1, B2, C3...), orientación personalizada de filas con captura en canvas, simbología automática por especie. |

### Búsqueda y Análisis

| Herramienta | Descripción |
|---|---|
| **Búsqueda Avanzada de Atributos** v1.1 | Búsqueda multi-capa con expresiones simples o avanzadas (expresiones QGIS). Visualización de resultados con gráficos, generación de reportes, exportación a CSV/Excel, zoom y resaltado de features encontradas. |

---

## Instalación

### Requisitos

- **QGIS 3.22** o superior (probado hasta 3.40+)
- Python 3.9+
- **python-docx** (requerido para Memoria Descriptiva)

Dependencias opcionales (según la herramienta que uses):
- `pandas` + `matplotlib` — para reportes y visualización en Attribute Search
- `reportlab` — para reportes PDF en GNSS Post-Process
- `RTKLIB` — binario externo requerido para post-proceso GNSS

### Instalación desde ZIP (recomendado)

1. Descargar el [último release](https://github.com/YuriCaller/YF_GIS_AMAZONIA/releases) o el archivo ZIP del repositorio
2. En QGIS: **Complementos → Administrar e instalar complementos → Instalar desde ZIP**
3. Seleccionar el archivo ZIP e **Instalar complemento**
4. El menú **YF GIS Amazonia** aparecerá en la barra de menú superior de QGIS

### Instalación manual

1. Clonar o descargar este repositorio
2. Copiar la carpeta `yf_gis_amazonia_tools/` a:
   ```
   Windows: %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\
   Linux:   ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/
   macOS:   ~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/
   ```
3. Reiniciar QGIS
4. Activar en **Complementos → Administrar e instalar complementos → Instalados**

### Instalación de dependencias Python

Abrir **OSGeo4W Shell** (Windows) o terminal (Linux/macOS) y ejecutar:

```bash
python -m pip install python-docx pandas matplotlib reportlab
```

---

## Uso

Tras la instalación, aparece un menú **YF GIS Amazonia** en la barra de menú de QGIS con cuatro submenús temáticos:

```
YF GIS Amazonia
├── Catastral
│   ├── Memoria Descriptiva
│   ├── Segmentador de Parcelas
│   └── YF Tools Plus
├── Geodesia / GNSS
│   └── Post-Proceso PPK/PPP
├── Agroforestal / Ambiental
│   └── SAF Generator
├── Búsqueda y Análisis
│   └── Búsqueda Avanzada de Atributos
└── Acerca de...
```

Cada herramienta abre su propio diálogo o panel acoplable con la funcionalidad completa.

---

## Arquitectura

El plugin usa una arquitectura modular con carga lazy de herramientas:

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
│   ├── crs_utils.py         # Utilidades CRS/UTM
│   └── qt_compat.py         # Compatibilidad PyQt5/PyQt6
└── tools/                   # Herramientas (submódulos)
    ├── memoria_descriptiva/
    ├── saf_generator/
    ├── yf_tools_plus/
    ├── gnss_postprocess/
    ├── attribute_search/
    └── segmentador/
```

Cada herramienta expone una clase `Tool(BaseTool)` con método `run()`. Las herramientas se cargan solo al ser invocadas por primera vez, minimizando el tiempo de arranque de QGIS.

---

## Compatibilidad

- **QGIS 3.22 LTR** — Soporte completo
- **QGIS 3.28+** — Soporte completo
- **QGIS 3.34 LTR** — Soporte completo
- **QGIS 3.40+** — Soporte completo (PyQt6)
- **Windows / Linux / macOS**

---

## Autor

**Ing. Yuri Fabian Caller Córdova**
- **CIP N° 214377** — Ingeniero Forestal
- Especialista GIS / GNSS / Fotogrametría
- Empresa: **Training Universal Company SAC (TUCSA)**
- Ubicación: Puerto Maldonado, Madre de Dios, Perú
- Email: yuricaller@gmail.com
- Web: [gis-amazonia.pe](https://gis-amazonia.pe)

---

## Contribuciones

Las contribuciones son bienvenidas. Para reportar bugs o solicitar nuevas funcionalidades, abre un [issue](https://github.com/YuriCaller/YF_GIS_AMAZONIA/issues).

Para contribuir código:
1. Fork del repositorio
2. Crear una rama para tu feature (`git checkout -b feature/mi-feature`)
3. Commit de los cambios (`git commit -m 'Agregar mi-feature'`)
4. Push a la rama (`git push origin feature/mi-feature`)
5. Abrir un Pull Request

---

## Licencia

Este proyecto está licenciado bajo la **GNU General Public License v3.0**. Ver el archivo [LICENSE](LICENSE) para los términos completos.

---

## Agradecimientos

- **Equipo de QGIS** por la excelente plataforma y APIs que hacen posible este plugin
- **RTKLIB** por la biblioteca de procesamiento GNSS de código abierto
- **python-docx**, **reportlab**, **pyproj** y demás bibliotecas que sustentan las herramientas
- **Comunidad forestal y catastral de Madre de Dios** cuyas necesidades reales guían el desarrollo de este plugin
