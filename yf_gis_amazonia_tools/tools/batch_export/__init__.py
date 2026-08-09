# -*- coding: utf-8 -*-
"""
Batch Export — Exportación de expediente completo en un clic.
Genera carpeta organizada con shapefiles, GeoPackages, PDFs y metadatos.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import os
from qgis.PyQt.QtGui import QDesktopServices as __QDS
from qgis.PyQt.QtCore import QUrl as __QURL
import subprocess  # nosec B404 - llamadas con lista de args y sin shell
import sys

from qgis.PyQt.QtWidgets import QDialog
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import QgsProject

from ...core.base_tool import BaseTool
from ...core.logger import log_info, log_error


class Tool(BaseTool):
    """Batch Export — exportación de expediente completo."""

    TOOL_NAME = "Exportar Expediente"

    def __init__(self, iface, plugin_dir):
        super().__init__(iface, plugin_dir)

    def run(self):
        import traceback
        try:
            from .dialog import BatchExportDialog
            dlg = BatchExportDialog(self.iface.mainWindow())
        except Exception as e:
            log_error(f"Batch Export: error abriendo diálogo: {e}")
            traceback.print_exc()
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error — YF Batch Export",
                f"No se pudo abrir el diálogo:\n\n{e}"
            )
            return

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        # Recopilar parámetros
        nombre     = dlg.get_nombre()
        base_dir   = dlg.get_directorio()
        plantilla  = dlg.get_plantilla()
        autor      = dlg.get_autor()
        cliente    = dlg.get_cliente()
        capas      = dlg.get_capas_seleccionadas()
        layouts    = dlg.get_layouts_seleccionados()
        opciones   = dlg.get_opciones()
        crs_authid = QgsProject.instance().crs().authid()

        try:
            self._ejecutar_exportacion(
                dlg, nombre, base_dir, plantilla,
                autor, cliente, capas, layouts,
                opciones, crs_authid
            )
        except Exception as e:
            log_error(f"Batch Export: error durante exportación: {e}")
            traceback.print_exc()
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error — YF Batch Export",
                f"Error durante la exportación:\n\n{e}"
            )

    # ─────────────────────────────────────────────────────────────────
    # Lógica de exportación
    # ─────────────────────────────────────────────────────────────────

    def _ejecutar_exportacion(self, dlg, nombre, base_dir, plantilla,
                               autor, cliente, capas, layouts,
                               opciones, crs_authid):
        from .batch_export_engine import (
            crear_estructura, exportar_capa_shapefile,
            exportar_capa_geopackage, exportar_layout_pdf,
            exportar_tabla_coordenadas, generar_metadatos,
            comprimir_expediente, _sanitizar,
        )

        total = len(capas) * 2 + len(layouts) + 2  # estimado de pasos
        paso  = 0
        errores = []
        capas_info  = []
        layouts_info = []

        # ── 1. Crear estructura de carpetas ──────────────────────────
        dlg.set_progreso(5, "Creando estructura de carpetas...")
        raiz, carpetas = crear_estructura(base_dir, plantilla, nombre)
        log_info(f"Batch Export: estructura creada en {raiz}")

        # Resolver directorios según plantilla
        dir_shp   = carpetas.get("shapes",    carpetas.get("vectoriales", raiz))
        dir_gpkg  = carpetas.get("geopackage", carpetas.get("vectoriales", raiz))
        dir_pdf   = carpetas.get("mapas_pdf", carpetas.get("pdf", raiz))
        dir_tabla = carpetas.get("tablas",    carpetas.get("tablas_inventario", raiz))
        dir_meta  = carpetas.get("metadatos", raiz)

        # ── 2. Exportar capas vectoriales ────────────────────────────
        for i, (layer, fmt) in enumerate(capas):
            nombre_capa = _sanitizar(layer.name())
            paso += 1
            progreso = int(10 + (paso / total) * 70)
            dlg.set_progreso(progreso, f"Exportando capa: {layer.name()}...")

            tipo_geom = {0: "Punto", 1: "Línea", 2: "Polígono"}.get(
                layer.geometryType(), "Vector"
            )
            capas_info.append({
                "nombre":   layer.name(),
                "tipo":     tipo_geom,
                "features": layer.featureCount(),
            })

            if fmt in ("shp", "both"):
                path, ok, msg = exportar_capa_shapefile(layer, dir_shp, nombre_capa)
                if ok:
                    log_info(f"  SHP: {path}")
                else:
                    errores.append(f"SHP {layer.name()}: {msg}")
                    log_error(f"  SHP error: {msg}")

            if fmt in ("gpkg", "both"):
                path, ok, msg = exportar_capa_geopackage(layer, dir_gpkg, nombre_capa)
                if ok:
                    log_info(f"  GPKG: {path}")
                else:
                    errores.append(f"GPKG {layer.name()}: {msg}")
                    log_error(f"  GPKG error: {msg}")

            if fmt == "xlsx":
                path, ok, msg = exportar_tabla_coordenadas(
                    layer, dir_tabla, nombre_capa + "_tabla"
                )
                if ok:
                    log_info(f"  XLSX: {path}")
                else:
                    errores.append(f"XLSX {layer.name()}: {msg}")

        # ── 3. Exportar layouts PDF ──────────────────────────────────
        for layout, dpi in layouts:
            paso += 1
            progreso = int(10 + (paso / total) * 70)
            dlg.set_progreso(progreso, f"Exportando mapa: {layout.name()}...")

            nombre_layout = _sanitizar(layout.name())
            path, ok, msg = exportar_layout_pdf(layout, dir_pdf, nombre_layout, dpi)
            if ok:
                log_info(f"  PDF: {path}")
                layouts_info.append({"nombre": layout.name(), "dpi": dpi})
            else:
                errores.append(f"PDF {layout.name()}: {msg}")
                log_error(f"  PDF error: {msg}")

        # ── 4. Metadatos ─────────────────────────────────────────────
        if opciones.get("metadatos"):
            dlg.set_progreso(85, "Generando metadatos...")
            generar_metadatos(
                raiz, nombre, capas_info, layouts_info,
                autor, cliente, crs_authid
            )

        # ── 5. Comprimir ─────────────────────────────────────────────
        zip_path = None
        if opciones.get("zip"):
            dlg.set_progreso(92, "Comprimiendo expediente...")
            zip_path = comprimir_expediente(raiz)
            log_info(f"ZIP: {zip_path}")

        # ── 6. Resultado ─────────────────────────────────────────────
        dlg.set_progreso(100, "¡Exportación completada!")

        resumen = (
            f"Expediente exportado correctamente.\n\n"
            f"📁 Carpeta: {raiz}\n"
            f"📦 Capas exportadas: {len(capas)}\n"
            f"🗺️  Mapas PDF: {len(layouts)}\n"
        )
        if zip_path:
            resumen += f"🗜️  ZIP: {os.path.basename(zip_path)}\n"
        if errores:
            resumen += f"\n⚠️  {len(errores)} advertencia(s):\n"
            resumen += "\n".join(f"  • {e}" for e in errores[:5])

        self.iface.messageBar().pushSuccess(
            "YF · Batch Export", f"{len(capas)} capas + {len(layouts)} PDFs exportados"
        )

        QMessageBox.information(
            self.iface.mainWindow(),
            "YF · Exportación completada",
            resumen
        )

        # Abrir carpeta en el explorador
        if opciones.get("abrir"):
            self._abrir_carpeta(raiz)

    def _abrir_carpeta(self, path):
        """Abre la carpeta en el explorador del sistema."""
        try:
            __QDS.openUrl(__QURL.fromLocalFile(path))
        except Exception as e:
            log_error(f"Batch Export: no se pudo abrir carpeta: {e}")
