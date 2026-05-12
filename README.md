# YF GIS Amazonia Tools

**Professional GIS toolkit for cadastral regularization, surveying, GNSS post-processing and agroforestry management in the Peruvian Amazon.**

[![QGIS](https://img.shields.io/badge/QGIS-3.22%2B-green.svg)](https://qgis.org/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.0.0-brightgreen.svg)](metadata.txt)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

---

## DescripciÃ³n

**YF GIS Amazonia Tools** es un plugin unificado para QGIS que integra seis herramientas especializadas para profesionales de topografÃ­a, catastro, geodesia y gestiÃ³n forestal en la AmazonÃ­a peruana. Combina funcionalidades que antes estaban dispersas en mÃºltiples plugins en una sola suite coherente, organizada por Ã¡reas temÃ¡ticas.

El plugin estÃ¡ diseÃ±ado para el flujo de trabajo real del ingeniero forestal, topÃ³grafo o especialista GIS peruano: desde el levantamiento GNSS en campo, pasando por el procesamiento de coordenadas, hasta la generaciÃ³n de memorias descriptivas y reportes tÃ©cnicos conforme a los estÃ¡ndares del IGN PerÃº y SERFOR.

---

## Herramientas integradas

Todas las herramientas estÃ¡n **completamente integradas y funcionando** dentro de un Ãºnico menÃº principal en QGIS.

### Catastral

| Herramienta | DescripciÃ³n |
|---|---|
| **Memoria Descriptiva** v3.2 | Generador automÃ¡tico de memorias descriptivas en Word (.docx) para saneamiento fÃ­sico-legal de predios rurales. Tres modos: polÃ­gono Ãºnico, atlas completo (una memoria por cada polÃ­gono), o atlas por selecciÃ³n. Auto-detecta capas adyacentes para identificaciÃ³n de colindantes. |
| **Segmentador de Parcelas** | DivisiÃ³n y segmentaciÃ³n de polÃ­gonos en lÃ­neas y vÃ©rtices con cÃ¡lculo automÃ¡tico de azimuts y Ã¡ngulos internos/externos. Delega a la pestaÃ±a de segmentaciÃ³n de YF Tools Plus. |
| **YF Tools Plus** v2.3 | Suite de herramientas topogrÃ¡ficas: creaciÃ³n de polÃ­gonos desde Excel/CSV, segmentaciÃ³n con herencia de campos, exportaciÃ³n a Excel con un clic, recalculaciÃ³n de atributos geomÃ©tricos. Soporte completo de polÃ­gonos multipart y anillos interiores. |

### Geodesia / GNSS

| Herramienta | DescripciÃ³n |
|---|---|
| **Post-Proceso PPK/PPP** v2.0 | Procesamiento GNSS diferencial con RTKLIB. ValidaciÃ³n geodÃ©sica estricta de bases, generaciÃ³n de reportes PDF con estructura IGN PerÃº (UTM, GeogrÃ¡ficas, Cartesianas), archivos .cor para submisiÃ³n al IGN, exportaciÃ³n a SHP, GPKG, KML y GeoJSON. |

### Agroforestal / Ambiental

| Herramienta | DescripciÃ³n |
|---|---|
| **SAF Generator** v2.1 | Generador profesional de sistemas agroforestales con seis mÃ©todos de distribuciÃ³n espacial (Hash, Ajedrez, Filas, Bloques, Aleatorio, Secuencial). IdentificaciÃ³n Ãºnica por planta (A1, B2, C3...), orientaciÃ³n personalizada de filas con captura en canvas, simbologÃ­a automÃ¡tica por especie. |

### BÃºsqueda y AnÃ¡lisis

| Herramienta | DescripciÃ³n |
|---|---|
| **BÃºsqueda Avanzada de Atributos** v1.1 | BÃºsqueda multi-capa con expresiones simples o avanzadas (expresiones QGIS). VisualizaciÃ³n de resultados con grÃ¡ficos, generaciÃ³n de reportes, exportaciÃ³n a CSV/Excel, zoom y resaltado de features encontradas. |

---

## InstalaciÃ³n

### Requisitos

- **QGIS 3.22** o superior (probado hasta 3.40+)
- Python 3.9+
- **python-docx** (requerido para Memoria Descriptiva)

Dependencias opcionales (segÃºn la herramienta que uses):
- `pandas` + `matplotlib` â€” para reportes y visualizaciÃ³n en Attribute Search
- `reportlab` â€” para reportes PDF en GNSS Post-Process
- `RTKLIB` â€” binario externo requerido para post-proceso GNSS

### InstalaciÃ³n desde ZIP (recomendado)

1. Descargar el [Ãºltimo release](https://github.com/YuriCaller/YF_GIS_AMAZONIA/releases) o el archivo ZIP del repositorio
2. En QGIS: **Complementos â†’ Administrar e instalar complementos â†’ Instalar desde ZIP**
3. Seleccionar el archivo ZIP e **Instalar complemento**
4. El menÃº **YF GIS Amazonia** aparecerÃ¡ en la barra de menÃº superior de QGIS

### InstalaciÃ³n manual

1. Clonar o descargar este repositorio
2. Copiar la carpeta `yf_gis_amazonia_tools/` a:
   ```
   Windows: %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\
   Linux:   ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/
   macOS:   ~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/
   ```
3. Reiniciar QGIS
4. Activar en **Complementos â†’ Administrar e instalar complementos â†’ Instalados**

### InstalaciÃ³n de dependencias Python

Abrir **OSGeo4W Shell** (Windows) o terminal (Linux/macOS) y ejecutar:

```bash
python -m pip install python-docx pandas matplotlib reportlab
```

---

## Uso

Tras la instalaciÃ³n, aparece un menÃº **YF GIS Amazonia** en la barra de menÃº de QGIS con cuatro submenÃºs temÃ¡ticos:

```
YF GIS Amazonia
â”œâ”€â”€ Catastral
â”‚   â”œâ”€â”€ Memoria Descriptiva
â”‚   â”œâ”€â”€ Segmentador de Parcelas
â”‚   â””â”€â”€ YF Tools Plus
â”œâ”€â”€ Geodesia / GNSS
â”‚   â””â”€â”€ Post-Proceso PPK/PPP
â”œâ”€â”€ Agroforestal / Ambiental
â”‚   â””â”€â”€ SAF Generator
â”œâ”€â”€ BÃºsqueda y AnÃ¡lisis
â”‚   â””â”€â”€ BÃºsqueda Avanzada de Atributos
â””â”€â”€ Acerca de...
```

Cada herramienta abre su propio diÃ¡logo o panel acoplable con la funcionalidad completa.

---

## Arquitectura

El plugin usa una arquitectura modular con carga lazy de herramientas:

```
yf_gis_amazonia_tools/
â”œâ”€â”€ __init__.py              # Entry point (classFactory)
â”œâ”€â”€ metadata.txt             # Metadata de QGIS
â”œâ”€â”€ LICENSE                  # GNU GPL v3
â”œâ”€â”€ README.md
â”œâ”€â”€ icons/                   # Iconos del plugin
â”œâ”€â”€ core/                    # Infraestructura compartida
â”‚   â”œâ”€â”€ plugin_manager.py    # Orquestador y menÃº principal
â”‚   â”œâ”€â”€ tool_registry.py     # Registro con carga lazy
â”‚   â”œâ”€â”€ base_tool.py         # Clase base para herramientas
â”‚   â”œâ”€â”€ logger.py            # Logger unificado (QGIS Message Log)
â”‚   â”œâ”€â”€ crs_utils.py         # Utilidades CRS/UTM
â”‚   â””â”€â”€ qt_compat.py         # Compatibilidad PyQt5/PyQt6
â””â”€â”€ tools/                   # Herramientas (submÃ³dulos)
    â”œâ”€â”€ memoria_descriptiva/
    â”œâ”€â”€ saf_generator/
    â”œâ”€â”€ yf_tools_plus/
    â”œâ”€â”€ gnss_postprocess/
    â”œâ”€â”€ attribute_search/
    â””â”€â”€ segmentador/
```

Cada herramienta expone una clase `Tool(BaseTool)` con mÃ©todo `run()`. Las herramientas se cargan solo al ser invocadas por primera vez, minimizando el tiempo de arranque de QGIS.

---

## Compatibilidad

- **QGIS 3.22 LTR** â€” Soporte completo
- **QGIS 3.28+** â€” Soporte completo
- **QGIS 3.34 LTR** â€” Soporte completo
- **QGIS 3.40+** â€” Soporte completo (PyQt6)
- **Windows / Linux / macOS**
---
## Autor

**Ing. Yuri Fabian Caller CÃ³rdova**
- **CIP NÂ° 214377** â€” Ingeniero Forestal
- Especialista GIS / GNSS / FotogrametrÃ­a
- Empresa: **Training Universal Company SAC (TUCSA)**
- UbicaciÃ³n: Puerto Maldonado, Madre de Dios, PerÃº
- Email: yuricaller@gmail.com
- Web: [gis-amazonia.pe](https://gis-amazonia.pe)

---

## Contribuciones

Las contribuciones son bienvenidas. Para reportar bugs o solicitar nuevas funcionalidades, abre un [issue](https://github.com/YuriCaller/YF_GIS_AMAZONIA/issues).

Para contribuir cÃ³digo:
1. Fork del repositorio
2. Crear una rama para tu feature (`git checkout -b feature/mi-feature`)
3. Commit de los cambios (`git commit -m 'Agregar mi-feature'`)
4. Push a la rama (`git push origin feature/mi-feature`)
5. Abrir un Pull Request

---

## Licencia

Este proyecto estÃ¡ licenciado bajo la **GNU General Public License v3.0**. Ver el archivo [LICENSE](LICENSE) para los tÃ©rminos completos.

---

## Agradecimientos

- **Equipo de QGIS** por la excelente plataforma y APIs que hacen posible este plugin
- **RTKLIB** por la biblioteca de procesamiento GNSS de cÃ³digo abierto
- **python-docx**, **reportlab**, **pyproj** y demÃ¡s bibliotecas que sustentan las herramientas
- **Comunidad forestal y catastral de Madre de Dios** cuyas necesidades reales guÃ­an el desarrollo de este plugin
