[README.md](https://github.com/user-attachments/files/26686531/README.md)
# YF GIS Amazonia Tools

**Suite profesional de herramientas GIS para la Amazonía peruana**

Plugin unificado para QGIS que integra herramientas especializadas en saneamiento físico legal, catastro rural, geodesia GNSS y gestión agroforestal.

---

## Herramientas incluidas

### Catastral
| Herramienta | Estado | Descripción |
|---|---|---|
| **Memoria Descriptiva** | ✅ Integrado | Generador automático de memorias descriptivas para regularización de predios rurales |
| **Segmentador** | ✅ Integrado | División y partición de parcelas con Atlas automático |
| **YF Tools Plus** | ✅ Integrado | Cálculo de coordenadas, vértices, áreas y perímetros |

### Geodesia / GNSS
| Herramienta | Estado | Descripción |
|---|---|---|
| **Post-Proceso PPK/PPP** | ✅ Integrado | Procesamiento GNSS con RTKLIB, reportes PDF y archivos .cor para IGN |

### Agroforestal / Ambiental
| Herramienta | Estado | Descripción |
|---|---|---|
| **SAF Generator** | ✅ Integrado | Generador profesional de sistemas agroforestales con identificación única |

### Búsqueda y Análisis
| Herramienta | Estado | Descripción |
|---|---|---|
| **Attribute Search** | ✅ Integrado | Búsqueda avanzada multi-capa con reportes y visualización |

---

## Instalación

### Desde ZIP (recomendado)
1. Descargar el archivo `yf_gis_amazonia_tools.zip`
2. En QGIS: **Complementos → Administrar e instalar complementos → Instalar desde ZIP**
3. Seleccionar el archivo ZIP → Instalar
4. El menú **YF GIS Amazonia** aparecerá en la barra de menú

### Manual
1. Copiar la carpeta `yf_gis_amazonia_tools` a:
   ```
   Windows: %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\
   Linux:   ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/
   macOS:   ~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/
   ```
2. Reiniciar QGIS
3. Activar en Complementos → Administrar e instalar complementos → Instalados

---

## Arquitectura

```
yf_gis_amazonia_tools/
├── __init__.py                  # Entry point (classFactory)
├── metadata.txt                 # Plugin metadata para QGIS
├── icons/                       # Iconos del plugin
│   ├── main_icon.png
│   ├── catastral.png
│   ├── gnss.png
│   ├── agroforestal.png
│   ├── search.png
│   └── ...
├── core/                        # Infraestructura compartida
│   ├── plugin_manager.py        # Orquestador principal y menú
│   ├── tool_registry.py         # Registro y carga lazy de herramientas
│   ├── base_tool.py             # Clase base para herramientas
│   ├── logger.py                # Logger unificado (QGIS Log Messages)
│   ├── crs_utils.py             # Utilidades CRS/UTM
│   └── qt_compat.py             # Compatibilidad PyQt5/PyQt6
└── tools/                       # Herramientas (cada una es un submódulo)
    ├── saf_generator/           # ✅ SAF Generator integrado
    │   ├── __init__.py          # Tool class (entry point)
    │   ├── engine.py            # Lógica de generación (separada del UI)
    │   └── dialog.py            # Diálogo Qt
    ├── memoria_descriptiva/     # Stub - migración pendiente
    ├── gnss_postprocess/        # Stub - migración pendiente
    ├── segmentador/             # Stub - migración pendiente
    ├── yf_tools_plus/           # Stub - migración pendiente
    └── attribute_search/        # Stub - migración pendiente
```

### Cómo agregar una nueva herramienta

1. Crear directorio en `tools/mi_herramienta/`
2. Crear `__init__.py` que exponga `class Tool(BaseTool)` con método `run()`
3. Registrar en `core/plugin_manager.py` → `_register_tools()`
4. Agregar icono en `icons/`

---

## Requisitos

- QGIS ≥ 3.22
- Python ≥ 3.9
- Sin dependencias externas adicionales para el core

Dependencias opcionales por herramienta:
- **GNSS Post-Process**: RTKLIB (binario externo)
- **Attribute Search** (reportes): matplotlib, pandas, python-docx

---

## Autor

**Yuri Fabian Caller Córdova**
- CIP N° 214377 — Ingeniero Forestal
- Especialista GIS/GNSS/Fotogrametría
- Web: [gis-amazonia.pe](https://gis-amazonia.pe)
- Empresa: Training Universal Company SAC (TUCSA)
- Puerto Maldonado, Madre de Dios, Perú

---

## Licencia

GNU General Public License v2.0 o posterior
