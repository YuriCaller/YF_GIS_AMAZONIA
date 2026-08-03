# YF GIS Amazonia Tools

*Read this in: **English** · [Español](README.es.md)*

**Professional GIS toolkit for cadastral, surveying, GNSS post-processing and agroforestry workflows in the Peruvian Amazon.**

[![QGIS](https://img.shields.io/badge/QGIS-3.22%2B-green.svg)](https://qgis.org/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.5.1-brightgreen.svg)](metadata.txt)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

---

## Overview

**YF GIS Amazonia Tools** is a unified QGIS plugin that integrates a set of specialized tools for surveying, cadastral, geodesy and forestry professionals. It brings together —organized by theme— functionality that would otherwise be scattered across multiple plugins, in a single coherent suite.

The plugin is built around the real-world workflow of the forestry engineer, surveyor or GIS specialist: from GNSS field surveying, through coordinate post-processing and plan georeferencing, to the generation of technical memoirs, cartography and reports compliant with the standards of Peru's IGN, SERFOR and GOREMAD.

Although it was born for the Peruvian Amazon, it is now used in more than 20 countries.

---

## What's new in v3.0.5

- **Superposition Analyser — official geoservices (NEW):** evaluates a parcel against pre-existing rights and protected areas, reporting overlap area in hectares, percentage of the parcel and a severity level. Sources may be local vector files, official geoservices, or both combined in a single run.
- **Editable geoservice catalogue:** a JSON file in the profile config folder, preloaded and field-verified for Peru — SERFOR (forest concessions, permits, cesiones en uso, BPP, forest zoning, fragile ecosystems), SERNANP (protected areas, **buffer zones**, reserved zones, ACR, ACP) and MIDAGRI (rural cadastre, native and peasant communities). Users in other countries add their own services without touching code.
- **WFS and ArcGIS REST**, chosen per service. Downloads are restricted to the parcel bounding box, so a national layer is never fetched in full. Which transport each service actually supports was verified against the live servers, not assumed from documentation.
- **Honest traceability:** local files are fingerprinted with SHA-256; a geoservice can only be attested as a *snapshot* (URL, layer, timestamp, feature count). The report states that difference explicitly rather than presenting both as equivalent guarantees.
- **A layer that fails to load is reported as NOT EVALUATED**, never as free of overlap — a distinction that matters when the report goes into an administrative or registry file. Each institution's legal notice is carried into the report.

## What's new in v3.0.0 – v3.0.3

- **Qt6 / QGIS 4.x compatibility completed:** 194 enumerations migrated to scoped form; 104 bare `try/except/pass` blocks replaced with logging (Bandit B110); Flake8 clean.
- **YF Tools Plus:** unified *Tabla → Polígono* tab reading Excel and CSV directly, with multi-polygon support via ID field, vertex ordering, and honest validation reporting by Excel row number.
- **Icons** migrated to Font-GIS (CC BY 4.0) and native QGIS icons (GPL).

## What's new in v2.5.0 – v2.5.1

- **ANTEX / PCO-PCV correction system (2.5.0):** the antenna field is no longer documentary. New ANTEX manager (IGS20 download, parsing, custom manufacturer files, RINEX base header reading); receiver/satellite phase-center corrections are now actually applied when a valid ANTEX and antenna name are present. Universal antenna support (Trimble, CHCNAV, Leica, South, Emlid, Mettatec…).
- **Qt6 dialog fixes (2.5.1):** fixed 'no attribute Accepted' errors on QGIS 4 in Smart Labels, Layout Rescaler, Batch Export, Vector Geometry and Title Block.

## What's new in v2.4.0

- **Smart Georeferencer (NEW):** a dynamic, real-time georeferencer for scanned plans and drone orthophotos. ArcGIS-style control-point capture, snapping to reference vertices, automatic GCP detection with OpenCV, a TPS warp engine, and a *leave-one-out* quality diagnostic that flags inconsistent control points. Integrated into the **Catastral** submenu. (Details below.)

## v2.3.0

- **GNSS — Occupation Mode (TBC/Pathfinder-style):** detects occupation event flags (Trimble Geo7X/DA2) inside a continuous RINEX and resolves each occupied point separately, never averaging between different points. Output: one layer with all points (H1, H2…) plus a per-point quality report.
- **GNSS — Submeter DGPS:** differential code positioning (no ambiguity resolution), where false fixes are impossible. Honest 0.3–1 m accuracy, ideal under canopy.
- **GNSS — Batch processing:** process multiple rover files against one base in a single run.

## v2.2.1

- **Qt6 / QGIS 4 support:** runs on both Qt5 (QGIS 3.x) and Qt6 (QGIS 4.x) builds via the `qgis.PyQt` shim. Backwards-compatible with QGIS 3.22+.

---

## Featured: Smart Georeferencer

A **dynamic, live** georeferencer designed to fit scanned cadastral plans and drone orthophotos with vertex-level precision. It complements QGIS's native georeferencer with two differentiators it doesn't have: **real-time snapping to vertices** and a **leave-one-out quality diagnostic**.

- **Immediate placement:** a button drops the image onto the canvas and into the Layers panel, ready to georeference.
- **ArcGIS-style two-click GCP capture:** click a feature on the image → click the control point on the map. The source anchor stays fixed and a guide arrow connects the two points.
- **Snapping:** the target control point snaps onto the vertices of your reference layers, using the QGIS snapping configuration. Cadastral precision.
- **Automatic GCP detection:** via OpenCV (SIFT/ORB + RANSAC). OpenCV installs itself on first use and is **only required for automatic detection** — manual capture works without it.
- **Two-stage TPS warp engine:** the image warps and follows pan/zoom together with the rest of the map.
- **Leave-one-out (LOO) quality diagnostic:** detects inconsistent control points (mis-measured or mis-digitized). With TPS the standard residual is zero by construction, so the LOO uses an affine model that does isolate the problem point. Colour heatmap on the markers (green/amber/red) and a worst-first list. Requires ≥5 GCPs to be reliable.
- **Point management:** right-click context menu to add, delete or edit a point's XY coordinates, and to load GCPs from CSV/Excel (columns `pixelX, pixelY, mapX, mapY`).
- **Export:** full-resolution GeoTIFF (TPS or polynomial) and an option to place the georeferenced layer permanently.
- **Format compatibility:** JPEG/JFIF sources (CamScanner scans, etc.) are decoded to GeoTIFF for a reliable warp.

---

## Integrated tools

All tools are **fully integrated and working** within a single main menu in QGIS, organized into thematic submenus.

### Catastral

| Tool | Description |
|---|---|
| **Memoria Descriptiva** | Automatic generator of technical memoirs in Word (.docx) for the legal regularization of rural land. Modes: single polygon, full atlas (one memoir per polygon) and atlas by selection. Auto-detects adjacent layers to identify neighbors. |
| **Segmentador de Parcelas** | Polygon division and segmentation into lines and vertices with automatic azimuth and angle calculation. Layer names prefixed with the source name to avoid GeoPackage collisions. |
| **Calcular Geometría Vectorial** | Calculates area, perimeter, centroids, coordinates, length and azimuth (DMS/decimal) directly on the same layer, without creating new layers. Dual method: Ellipsoidal (`$area`) or Planar (`area($geometry)`) for legal plans and cadastre. Polygons, lines and points. |
| **YF Tools Plus** | Surveying toolset: build polygons from Excel/CSV, segmentation with field inheritance, one-click export to Excel, recomputation of geometric attributes. Full multipart and inner-ring support. |
| **Polygon Divider** | Divides a polygon by exact area, N equal parts or percentages, using a traced or angle-defined cut line (red highlight, ArcGIS Pro "Divide" style). Optional GeoPackage output layer with inherited attributes and automatic labeling, or in-place edit with confirmation. 100% native `QgsGeometry`, no external dependencies. |
| **Smart Georeferencer** *(NEW v2.4.0)* | Dynamic georeferencer for scanned plans and drone orthophotos: ArcGIS-style GCP capture, snapping to vertices, automatic detection with OpenCV, TPS warp, leave-one-out diagnostic, GCP import from CSV/Excel and GeoTIFF export. (See featured section.) |
| **Smart Labels** | Intelligent labeling from a right-click on the canvas. Auto-detects geometry type and applies technical styles: V-01/V-02 vertices, distance+azimuth on lines, area+perimeter block on polygons. Uses dynamic expressions (`$area`, `$perimeter`, `$length`). |
| **Batch Export (Exportar Expediente)** | Exports all layers and layouts to a structured folder (SHP + GPKG + PDF + XLSX + metadata) in one click. Templates for GOREMAD, SERFOR, ACCA and simple delivery. Optional ZIP compression. |

### Geodesia / GNSS

| Tool | Description |
|---|---|
| **Post-Proceso PPK/PPP** | Differential GNSS processing with RTKLIB, field-validated against Trimble Business Center. Automatic precise-ephemeris download (SP3+CLK Final/Rapid from ESA/IGS) based on the RINEX date. Automatic rnx2rtkp engine installation. Base auto-fill from the RINEX header (TBC-style). Rover/base antenna height. Occupation Mode (multiple points in one RINEX), submeter DGPS and batch processing. Anti-false-fix validation and 1/σ² weighted averaging. PDF reports. |

### Agroforestal / Ambiental

| Tool | Description |
|---|---|
| **SAF Generator** | Agroforestry-system generator with several spatial distribution methods. Unique per-plant identification, custom row orientation captured on canvas, and automatic per-species symbology. |

### Búsqueda y Análisis

| Tool | Description |
|---|---|
| **Búsqueda Avanzada de Atributos** | Multi-layer search with simple or advanced (QGIS) expressions. Chart visualization, report generation, CSV/Excel export, zoom and highlighting of matched features. |
| **Analizador de Superposición** | Evaluates a parcel against pre-existing rights and protected areas. Sources: local vector folder, official geoservices (WFS / ArcGIS REST), or both. Reports overlap in hectares, percentage of the parcel and severity level; generates an HTML→Word report with an editable conclusion, SHA-256 traceability for local files and snapshot traceability for services. Preloaded catalogue for Peru (SERFOR, SERNANP, MIDAGRI), editable and extensible to other countries. |

### Layout / Compositor

| Tool | Description |
|---|---|
| **Generar Cajetín (Title Block)** | Professional title-block generator with 4 templates (Simple, BIM/Technical, Cadastral/Forestry, Premium). Dynamic expressions for scale, date and CRS. Integrated north arrow, location map, legend and situation thumbnail; elements grouped automatically. |
| **Redimensionar Layout (Layout Rescaler)** | Rescales all layout elements proportionally when the paper size changes, preserving relative positions via a proportional snapshot. Integrated into the layout designer toolbar. |
| **Table Style Manager** | Applies, copies and pastes attribute-table styles in the layout designer. 5 predefined styles. Copy/paste between tables. Export/import styles as JSON. |

### Comparación Visual

| Tool | Description |
|---|---|
| **Swipe Tool** | ArcGIS Pro-style visual layer comparison (sliding curtain). |

### Navegación

| Tool | Description |
|---|---|
| **Go-To** | Coordinate navigation with multi-format input (UTM, geographic, DMS) and smart paste. |

---

## Installation

### Requirements

- **QGIS 3.22** or newer (tested up to 3.40+; compatible with QGIS 4.x / Qt6)
- Python 3.9+
- **python-docx** (required for Memoria Descriptiva)

Optional dependencies (depending on the tool you use):
- `opencv-python-headless` — for **automatic GCP detection** in Smart Georeferencer (installs itself on first use; manual capture doesn't need it)
- `pandas` + `matplotlib` — for reports and visualization in Attribute Search
- `reportlab` — for PDF reports in GNSS Post-Process
- `RTKLIB` — external binary for GNSS post-processing (downloads itself on the first run)

### Install from ZIP (recommended)

1. Download the [latest release](https://github.com/YuriCaller/YF_GIS_AMAZONIA/releases) or the repository ZIP.
2. In QGIS: **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Select the ZIP and click **Install Plugin**.
4. The **YF GIS Amazonia** menu will appear in the top menu bar.

> **When upgrading from a previous version**, the most reliable path is to uninstall the old version and fully restart QGIS before installing the new one, to avoid leftover cached modules.

### Manual install

1. Clone or download this repository.
2. Copy the `yf_gis_amazonia_tools/` folder to:
   ```
   Windows: %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\
   Linux:   ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/
   macOS:   ~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/
   ```
3. Restart QGIS.
4. Enable it under **Plugins → Manage and Install Plugins → Installed**.

### Python dependencies

Open the **OSGeo4W Shell** (Windows) or a terminal (Linux/macOS) and run:

```bash
python -m pip install python-docx pandas matplotlib reportlab
```

(OpenCV installs automatically the first time you use automatic GCP detection.)

---

## Usage

After installation, a **YF GIS Amazonia** menu appears with its thematic submenus:

```
YF GIS Amazonia
├── Catastral
│   ├── Memoria Descriptiva
│   ├── Segmentador de Parcelas
│   ├── Calcular Geometría Vectorial
│   ├── YF Tools Plus
│   ├── Polygon Divider — Dividir Polígono
│   ├── Smart Georeferencer — Georreferenciar en vivo   (NEW)
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
└── Acerca de... (About)
```

Each tool opens its own dialog or dockable panel with the full functionality. The interface labels are in Spanish, matching the plugin's identity and how the tools appear in the QGIS menu.

---

## Architecture

The plugin uses a modular architecture with lazy tool loading:

```
yf_gis_amazonia_tools/
├── __init__.py              # Entry point (classFactory)
├── metadata.txt             # QGIS metadata
├── LICENSE                  # GNU GPL v3
├── README.md                # English (this file)
├── README.es.md             # Spanish
├── icons/                   # Plugin icons
├── core/                    # Shared infrastructure
│   ├── plugin_manager.py    # Orchestrator and main menu
│   ├── tool_registry.py     # Lazy-loading registry
│   ├── base_tool.py         # Base class for tools
│   ├── logger.py            # Unified logger (QGIS Message Log)
│   ├── coord_parser.py      # Multi-format coordinate parsing
│   ├── crs_utils.py         # CRS/UTM utilities
│   └── qt_compat.py         # PyQt5/PyQt6 compatibility
└── tools/                   # Tools (submodules)
    ├── memoria_descriptiva/
    ├── segmentador/
    ├── vector_geometry/
    ├── yf_tools_plus/
    ├── polygon_divider/
    ├── smart_georeferencer/     # NEW v2.4.0
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

Each tool exposes a `Tool(BaseTool)` class with a `run()` method. Tools are loaded only when invoked for the first time, minimizing QGIS startup time.

---

## Compatibility

> ✅ **Qt5 and Qt6:** compatible with QGIS 3.22+ (Qt5/PyQt5) and QGIS 4.x (Qt6/PyQt6) via the `qgis.PyQt` shim.

- **QGIS 3.22 LTR** — Full support
- **QGIS 3.28 / 3.34 LTR** — Full support
- **QGIS 3.40+ / 4.x** — Full support (PyQt6)
- **Windows / Linux / macOS**

---

## Author

**Ing. Yuri Fabián Caller Córdova**
- **CIP N° 214377** — Forestry Engineer
- GIS / GNSS / Photogrammetry specialist
- Company: **Training Universal Company SAC (TUCSA)**
- Location: Puerto Maldonado, Madre de Dios, Peru
- Email: yuricaller@gmail.com
- Web: [gis-amazonia.pe](https://gis-amazonia.pe)

---

## Contributing

Contributions are welcome. To report bugs or request features, open an [issue](https://github.com/YuriCaller/YF_GIS_AMAZONIA/issues).

To contribute code:
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/my-feature`).
3. Commit your changes (`git commit -m 'Add my-feature'`).
4. Push to the branch (`git push origin feature/my-feature`).
5. Open a Pull Request.

---

## License

This project is licensed under the **GNU General Public License v3.0**. See the [LICENSE](LICENSE) file for the full terms.

---

## Acknowledgments

- The **QGIS team** for the platform and APIs that make this plugin possible.
- **RTKLIB** for the open-source GNSS processing library.
- **OpenCV**, **python-docx**, **reportlab**, **pyproj** and the other libraries that power these tools.
- The **forestry and cadastral community of Madre de Dios**, whose real-world needs guide this plugin's development.


## Créditos de iconos

Algunos iconos provienen de [Font-GIS](https://github.com/Viglino/font-gis) por Jean-Marc Viglino, licencia CC BY 4.0, y del proyecto QGIS (GPL).
