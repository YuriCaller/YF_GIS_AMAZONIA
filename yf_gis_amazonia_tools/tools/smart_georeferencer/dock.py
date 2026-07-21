"""
plugin.py — Clase principal de YF Georeferenciador (suite YF GIS Amazonia Tools).
Georreferenciación dinámica sobre el canvas con warp de malla TPS y
auto-detección de GCPs (OpenCV). Por Yuri F. Caller Córdova — gis-amazonia.pe
"""
import logging
import os
import tempfile
import numpy as np
try:
    from qgis.PyQt.QtGui import QAction        # Qt6: QAction vive en QtGui
except ImportError:
    from qgis.PyQt.QtWidgets import QAction    # Qt5: QAction vive en QtWidgets
from qgis.PyQt.QtCore import Qt
from qgis.PyQt import sip
from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                 QLabel, QPushButton, QComboBox, QFileDialog,
                                 QListWidget, QListWidgetItem, QSpinBox,
                                 QMessageBox, QGroupBox, QSlider, QCheckBox,
                                 QMenu, QLineEdit, QDialogButtonBox, QFormLayout,
                                 QDockWidget, QWidget, QScrollArea, QDoubleSpinBox)
from qgis.PyQt.QtGui import QImage, QIcon, QCursor, QDoubleValidator, QColor
from qgis.core import (QgsProject, QgsRasterLayer, QgsDataProvider, QgsPointXY)

from .canvas_item import GeorefCanvasItem, CaptureGcpTool
from . import exporter as ex
from . import georef_layer as gl
from . import diagnostics as diag
# NOTA: 'autodetect' (que importa cv2) se carga de forma diferida dentro de
# _run_detect, para que el plugin abra aunque OpenCV aún no esté instalado.


class XYDialog(QDialog):
    """Diálogo para escribir/editar la coordenada de mapa (X, Y) de un GCP."""
    def __init__(self, parent, x=0.0, y=0.0, title="Coordenada del punto de control"):
        super().__init__(parent)
        self.setWindowTitle(title)
        form = QFormLayout(self)
        self.ed_x = QLineEdit(f"{x:.4f}")
        self.ed_y = QLineEdit(f"{y:.4f}")
        v = QDoubleValidator(-1e12, 1e12, 6, self)
        self.ed_x.setValidator(v); self.ed_y.setValidator(v)
        form.addRow("X (Este):", self.ed_x)
        form.addRow("Y (Norte):", self.ed_y)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        form.addRow(bb)

    def values(self):
        def f(t):
            return float(t.replace(",", "."))
        return f(self.ed_x.text()), f(self.ed_y.text())


class GeorefDock(QDockWidget):
    def __init__(self, iface):
        super().__init__("YF Georeferenciador", iface.mainWindow())
        self.setObjectName("YFGeoreferenciadorDock")
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.item = None
        self.tool = None
        self.geo_layer = None              # capa VRT en la TOC
        self._tmpdir = None
        self._src_for_warp = None          # GeoTIFF decodificado del origen
        self._vrt_seq = 0
        self._build_ui()
        # ocultar/mostrar los markers junto con el panel (sin terminar la sesión)
        self.visibilityChanged.connect(self._on_visibility)

    def _on_visibility(self, visible):
        if self.item is not None:
            try:
                self.item.setVisible(visible)
                self.canvas.refresh()
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)

    def _build_ui(self):
        container = QWidget()
        lay = QVBoxLayout(container)

        # imagen a georreferenciar: desde capa cargada o desde archivo
        g1 = QGroupBox("1 · Imagen a georreferenciar")
        l1 = QVBoxLayout(g1)
        row = QHBoxLayout()
        self.cmb_img_layer = QComboBox()
        b_use_layer = QPushButton("Usar capa")
        b_use_layer.clicked.connect(self._use_layer_image)
        row.addWidget(QLabel("Capa cargada:"))
        row.addWidget(self.cmb_img_layer, 1)
        row.addWidget(b_use_layer)
        l1.addLayout(row)
        row2 = QHBoxLayout()
        self.lbl_img = QLabel("(ninguna)")
        b_img = QPushButton("…o elegir archivo")
        b_img.clicked.connect(self._pick_image)
        row2.addWidget(self.lbl_img, 1); row2.addWidget(b_img)
        l1.addLayout(row2)
        b_start = QPushButton("▶  Iniciar georeferenciación (colocar en el canvas)")
        b_start.clicked.connect(self._start_georef)
        l1.addWidget(b_start)
        lay.addWidget(g1)

        # referencia
        g2 = QGroupBox("2 · Capa(s) de referencia (georreferenciadas)")
        l2 = QVBoxLayout(g2)
        self.ref_list = QListWidget()
        self.ref_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self._reload_layers()
        b_rl = QPushButton("Recargar capas"); b_rl.clicked.connect(self._reload_layers)
        l2.addWidget(QLabel("Selecciona el satélite/ortomosaico de referencia:"))
        l2.addWidget(self.ref_list); l2.addWidget(b_rl)
        lay.addWidget(g2)

        # detector
        g3 = QGroupBox("3 · Detección automática de GCPs")
        l3 = QHBoxLayout(g3)
        self.cmb_det = QComboBox(); self.cmb_det.addItems(["SIFT (preciso)", "ORB (rápido)"])
        self.spin_n = QSpinBox(); self.spin_n.setRange(4, 200); self.spin_n.setValue(40)
        l3.addWidget(QLabel("Detector:")); l3.addWidget(self.cmb_det)
        l3.addWidget(QLabel("máx GCPs:")); l3.addWidget(self.spin_n)
        lay.addWidget(g3)

        b_detect = QPushButton("⟲  Detectar GCPs y georreferenciar")
        b_detect.clicked.connect(self._run_detect)
        lay.addWidget(b_detect)

        b_place = QPushButton("✛  Capturar puntos de control a mano")
        b_place.clicked.connect(self._start_capture)
        lay.addWidget(b_place)

        self.lbl_help = QLabel(
            "Captura: 1) clic en una feature de la imagen  →  "
            "2) clic en el punto de control en el mapa. "
            "La flecha guía conecta ambos. Clic derecho borra un punto.")
        self.lbl_help.setWordWrap(True)
        self.lbl_help.setStyleSheet("color:#557;")
        lay.addWidget(self.lbl_help)

        self.lbl_status = QLabel("Listo.")
        self.lbl_status.setWordWrap(True)
        lay.addWidget(self.lbl_status)

        # comparación / validación: actúa sobre la capa VRT de la TOC
        g5 = QGroupBox("4 · Comparar con la referencia (validar)")
        l5 = QVBoxLayout(g5)
        rowo = QHBoxLayout()
        rowo.addWidget(QLabel("Transparencia capa:"))
        self.sld_op = QSlider(Qt.Orientation.Horizontal)
        self.sld_op.setRange(0, 100); self.sld_op.setValue(100)
        self.sld_op.valueChanged.connect(self._on_opacity)
        self.lbl_op = QLabel("100%")
        rowo.addWidget(self.sld_op, 1); rowo.addWidget(self.lbl_op)
        l5.addLayout(rowo)
        self.chk_hide = QCheckBox("Ocultar imagen (flicker: ver solo la referencia)")
        self.chk_hide.toggled.connect(self._on_hide)
        l5.addWidget(self.chk_hide)
        l5.addWidget(QLabel("La imagen es una capa más: usa la TOC para opacidad, "
                            "orden o el Swipe nativo de QGIS."))
        lay.addWidget(g5)

        # diagnóstico de calidad: leave-one-out (heatmap por GCP)
        g6 = QGroupBox("5 · Diagnóstico de calidad (leave-one-out)")
        l6 = QVBoxLayout(g6)
        rowt = QHBoxLayout()
        rowt.addWidget(QLabel("Tolerancia (m):"))
        self.spin_tol = QDoubleSpinBox()
        self.spin_tol.setRange(0.01, 1000.0); self.spin_tol.setDecimals(2)
        self.spin_tol.setSingleStep(0.1); self.spin_tol.setValue(1.0)
        self.spin_tol.valueChanged.connect(self._on_tol)
        self.chk_heat = QCheckBox("Heatmap")
        self.chk_heat.setChecked(True)
        self.chk_heat.toggled.connect(self._on_heatmap)
        rowt.addWidget(self.spin_tol); rowt.addWidget(self.chk_heat)
        l6.addLayout(rowt)
        self.lbl_loo = QLabel("Agrega ≥5 GCPs para evaluar consistencia.")
        self.lbl_loo.setWordWrap(True)
        l6.addWidget(self.lbl_loo)
        self.list_loo = QListWidget()
        self.list_loo.setMaximumHeight(130)
        self.list_loo.itemClicked.connect(self._on_loo_click)
        l6.addWidget(self.list_loo)
        l6.addWidget(QLabel("Consistencia con modelo afín: rojo = punto "
                            "inconsistente (revisar). Clic = ir al punto."))
        lay.addWidget(g6)

        # export / colocar capa permanente
        g4 = QGroupBox("6 · Guardar resultado")
        l4 = QVBoxLayout(g4)
        rowm = QHBoxLayout()
        self.cmb_method = QComboBox(); self.cmb_method.addItems(["TPS", "Polinomial 2"])
        rowm.addWidget(QLabel("Método:")); rowm.addWidget(self.cmb_method, 1)
        l4.addLayout(rowm)
        b_place = QPushButton("⊕  Colocar capa georreferenciada en el panel (permanente)")
        b_place.clicked.connect(self._place_permanent)
        l4.addWidget(b_place)
        b_exp = QPushButton("Exportar GeoTIFF a una ruta…")
        b_exp.clicked.connect(self._export)
        l4.addWidget(b_exp)
        lay.addWidget(g4)

        b_finish = QPushButton("✕  Quitar imagen y terminar sesión")
        b_finish.clicked.connect(lambda: self._finish_session(remove_layer=True))
        lay.addWidget(b_finish)
        lay.addStretch(1)

        # panel acoplable con scroll (funciona en un dock angosto)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        self.setWidget(scroll)
        self.setMinimumWidth(330)

        self.image_path = None
        self._reload_image_layers()

    def _reload_image_layers(self):
        self.cmb_img_layer.clear()
        self._img_layer_ids = []
        for lyr in QgsProject.instance().mapLayers().values():
            if isinstance(lyr, QgsRasterLayer):
                self.cmb_img_layer.addItem(lyr.name())
                self._img_layer_ids.append(lyr.id())

    def _use_layer_image(self):
        i = self.cmb_img_layer.currentIndex()
        if i < 0 or i >= len(self._img_layer_ids):
            QMessageBox.warning(self, "Sin capa", "No hay capa ráster seleccionada.")
            return
        lyr = QgsProject.instance().mapLayer(self._img_layer_ids[i])
        path = lyr.source().split("|")[0]
        if not os.path.exists(path):
            QMessageBox.warning(
                self, "Capa sin archivo local",
                "Esa capa no apunta a un archivo en disco (¿es un basemap/WMS?).\n"
                "Usa una capa ráster basada en archivo, o elige un archivo.")
            return
        self.image_path = path
        self.lbl_img.setText(lyr.name())
        self.lbl_status.setText(f"Imagen: {lyr.name()} (desde capa cargada).")

    # ---- acciones ----
    def _reload_layers(self):
        self.ref_list.clear()
        for lyr in QgsProject.instance().mapLayers().values():
            it = QListWidgetItem(lyr.name())
            it.setData(Qt.ItemDataRole.UserRole, lyr.id())
            self.ref_list.addItem(it)
        self._reload_image_layers()

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Imagen de dron / escaneo", "",
            "Imágenes (*.tif *.tiff *.png *.jpg *.jpeg *.jfif *.bmp *.ecw *.sid);;"
            "Todos los archivos (*.*)")
        if path:
            self.image_path = path
            self.lbl_img.setText(os.path.basename(path))

    def _ensure_item(self):
        if self.item is None:
            if not self.image_path:
                QMessageBox.warning(self, "Falta imagen",
                                    "Elige una capa o un archivo de imagen primero.")
                return False
            img = QImage(self.image_path)
            if img.isNull():
                QMessageBox.critical(self, "Error", "No pude cargar la imagen.")
                return False
            self.item = GeorefCanvasItem(self.canvas, img)
            self.canvas.scene().addItem(self.item)
            self.tool = CaptureGcpTool(self.canvas, self.item,
                                       on_change=self._on_gcp_change,
                                       on_preview=self._on_preview,
                                       on_context=self._context_menu)
            self.canvas.setMapTool(self.tool)
            self.canvas.extentsChanged.connect(self.item.updatePosition)
            self._tmpdir = tempfile.mkdtemp(prefix="yf_georef_")
            # decodificar el origen (JFIF/JPEG/etc.) a GeoTIFF UNA vez, para que
            # el warp no falle leyendo un JPEG por tiles ('hBand is NULL')
            try:
                self._src_for_warp = gl.decode_to_gtiff(
                    self.image_path, os.path.join(self._tmpdir, "source_decoded.tif"))
            except Exception:
                self._src_for_warp = self.image_path
            self._build_layer()            # crea la capa en la TOC
        return True

    def _crs_authid(self):
        return self.canvas.mapSettings().destinationCrs().authid() or "EPSG:32719"

    def _build_layer(self):
        """(Re)genera el VRT georreferenciado y lo carga/actualiza en la TOC."""
        if self.item is None or self._tmpdir is None:
            return
        self._vrt_seq += 1
        base = os.path.join(self._tmpdir, f"georef_{self._vrt_seq}")
        method = "tps" if self.cmb_method.currentIndex() == 0 else "poly"
        try:
            src = self._src_for_warp or self.image_path
            out = gl.build_placement(src, self.item.fwd,
                                     self.item.gcps_original_px(), self.item.map_xy,
                                     self._crs_authid(), base, method=method,
                                     src_scale=self.item.src_scale)
        except Exception as e:
            self.lbl_status.setText(f"Capa no generada: {e}")
            return
        name = ("Georef · "
                + os.path.splitext(os.path.basename(self.image_path))[0]
                + " (en edición)")
        # IMPORTANTE: NO usar setDataSource para actualizar la capa. Cambiar la
        # fuente de un ráster en vivo deja el proveedor en un estado que el hilo
        # de render del canvas no puede dibujar -> 'hBand is NULL' y queda en
        # blanco. En su lugar se CREA una capa nueva (proveedor limpio) y se
        # reemplaza la anterior conservando su posición en la TOC.
        proj = QgsProject.instance()
        root = proj.layerTreeRoot()
        self.canvas.stopRendering()
        old = self.geo_layer if self._geo_layer_alive() else None
        idx = 0
        if old is not None:
            n = root.findLayer(old.id())
            if n is not None and n.parent() is not None:
                idx = n.parent().children().index(n)
        new = QgsRasterLayer(out, name)
        if not new.isValid():
            self.lbl_status.setText("Capa generada pero no válida.")
            return
        proj.addMapLayer(new, False)
        root.insertLayer(idx, new)
        if old is not None:
            try:
                proj.removeMapLayer(old.id())
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
        self.geo_layer = new
        self._apply_compare_to_layer()
        self.geo_layer.triggerRepaint()

    def _geo_layer_alive(self):
        """True solo si self.geo_layer existe, su objeto C++ no fue borrado y
        sigue en el proyecto. Evita 'wrapped C/C++ object has been deleted'."""
        if self.geo_layer is None or sip.isdeleted(self.geo_layer):
            self.geo_layer = None
            return False
        if QgsProject.instance().mapLayer(self.geo_layer.id()) is None:
            self.geo_layer = None
            return False
        return True

    def _layer_node(self):
        if not self._geo_layer_alive():
            return None
        return QgsProject.instance().layerTreeRoot().findLayer(self.geo_layer.id())

    def _on_preview(self, active):
        """Durante el arrastre: oculta la capa VRT (el item muestra el preview);
        al soltar: reconstruye el VRT y vuelve a mostrar la capa."""
        node = self._layer_node()
        if node is not None and not self.chk_hide.isChecked():
            node.setItemVisibilityChecked(not active)
        if not active:
            self._build_layer()            # commit: regenera el VRT

    def _start_georef(self):
        """Coloca la imagen en el canvas y en la TOC de inmediato, lista para
        georreferenciar (botón 'Iniciar')."""
        if self._ensure_item():
            self.canvas.setMapTool(self.tool)
            self.canvas.refresh()
            self._on_gcp_change()
            self.lbl_status.setText(
                "Imagen colocada en el canvas y en el panel de capas. "
                "Ahora captura puntos de control o usa la detección automática.")

    def _start_capture(self):
        if self._ensure_item():
            self.canvas.setMapTool(self.tool)
            self._on_gcp_change()
            self.lbl_status.setText(
                "Modo captura activo. Clic en la imagen, luego en el mapa.")

    def _on_opacity(self, v):
        self.lbl_op.setText(f"{v}%")
        self._apply_compare_to_layer()

    def _on_hide(self, on):
        node = self._layer_node()
        if node is not None:
            node.setItemVisibilityChecked(not on)

    def _apply_compare_to_layer(self):
        """Aplica transparencia/visibilidad (controles de comparación) a la
        capa VRT nativa de la TOC."""
        if not self._geo_layer_alive():
            return
        try:
            r = self.geo_layer.renderer()
            if r is not None:
                r.setOpacity(self.sld_op.value() / 100.0)
            self.geo_layer.triggerRepaint()
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)
        node = self._layer_node()
        if node is not None:
            node.setItemVisibilityChecked(not self.chk_hide.isChecked())

    def _on_gcp_change(self):
        if self.item is None:
            return
        n = len(self.item.src_px)
        rms = self.item.residual_rms()
        model = {0: "—", 1: "traslación", 2: "similitud"}.get(
            n, "TPS" if self.item.mode == "tps" else "afín")
        txt = f"GCPs: {n}  ·  modelo: {model}"
        if rms is not None and n >= 1:
            txt += f"  ·  RMS: {rms:.3f} m"
        if n < 3:
            txt += "   (≥3 para exportar)"
        self.lbl_status.setText(txt)
        # reconstruir la capa al confirmar (no durante un arrastre en curso)
        if self.item._drag_idx is None:
            self._build_layer()
            self._update_loo()

    # ---- menú contextual (clic derecho) ----
    def _context_menu(self, map_point, idx, image_px):
        m = QMenu()
        a_edit = a_del = a_add = a_csv = a_clear = None
        if idx is not None:
            a_edit = m.addAction("✎  Editar coordenada XY…")
            a_del = m.addAction("🗑  Borrar este punto")
            m.addSeparator()
        if image_px is not None:
            a_add = m.addAction("✛  Agregar punto aquí (escribir XY)…")
        a_csv = m.addAction("📄  Cargar GCPs desde CSV/Excel…")
        if len(self.item.src_px) > 0:
            m.addSeparator()
            a_clear = m.addAction("✕  Borrar todos los puntos")

        chosen = m.exec(QCursor.pos())
        if chosen is None:
            return
        if chosen == a_edit:
            self._edit_xy(idx)
        elif chosen == a_del:
            self.item.remove_gcp(idx); self._on_gcp_change()
        elif chosen == a_add:
            self._add_xy_here(image_px, map_point)
        elif chosen == a_csv:
            self._load_gcp_csv()
        elif chosen == a_clear:
            self.item.clear_gcps(); self._on_gcp_change()

    def _edit_xy(self, idx):
        x, y = self.item.map_xy[idx]
        d = XYDialog(self, x, y, "Editar punto de control")
        if d.exec() == QDialog.DialogCode.Accepted:
            try:
                nx, ny = d.values()
            except ValueError:
                QMessageBox.warning(self, "Valor inválido", "Coordenadas no válidas.")
                return
            self.item.move_target(idx, QgsPointXY(nx, ny))
            self._on_gcp_change()

    def _add_xy_here(self, image_px, map_point):
        d = XYDialog(self, map_point.x(), map_point.y(),
                     "Agregar punto de control")
        if d.exec() == QDialog.DialogCode.Accepted:
            try:
                nx, ny = d.values()
            except ValueError:
                QMessageBox.warning(self, "Valor inválido", "Coordenadas no válidas.")
                return
            self.item.add_gcp(image_px, QgsPointXY(nx, ny))
            self._on_gcp_change()

    def _load_gcp_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Cargar GCPs", "", "Tablas (*.csv *.txt *.xlsx *.xlsm)")
        if not path:
            return
        try:
            from . import gcp_io
            src_orig, mapxy = gcp_io.read_gcps(path)
        except Exception as e:
            QMessageBox.critical(self, "No se pudo leer", str(e))
            return
        # los píxeles del CSV son de la imagen ORIGINAL -> a espacio del item
        src_item = src_orig * self.item.src_scale
        self.item.set_gcps(src_item, mapxy)
        self._on_gcp_change()
        self.lbl_status.setText(
            f"Cargados {len(src_item)} GCPs desde {os.path.basename(path)}.")

    # ---- diagnóstico leave-one-out ----
    def _on_tol(self, v):
        if self.item is not None:
            self.item.set_loo(self.item.loo, tol=v)
            self._update_loo()

    def _on_heatmap(self, on):
        if self.item is not None:
            self.item.set_show_heatmap(on)

    def _on_loo_click(self, listitem):
        idx = listitem.data(Qt.ItemDataRole.UserRole)
        if idx is None or self.item is None or idx >= len(self.item.map_xy):
            return
        x, y = self.item.map_xy[idx]
        self.canvas.setCenter(QgsPointXY(x, y))
        self.canvas.refresh()
        self.item.set_highlight(idx)

    def _update_loo(self):
        """Recalcula LOO (modelo afín, para aislar puntos inconsistentes) y
        actualiza la lista y el heatmap."""
        if self.item is None:
            return
        tol = self.spin_tol.value()
        n = len(self.item.src_px)
        self.list_loo.clear()
        if n < 5:
            self.item.set_loo(None, tol=tol)
            self.lbl_loo.setText("Agrega ≥5 GCPs para una evaluación LOO fiable "
                                 "(con 3 o menos el resultado es inestable).")
            return
        res = diag.loo_residuals(self.item.src_px, self.item.map_xy, mode="affine")
        self.item.set_loo(res, tol=tol)
        rms = diag.loo_rms(res)
        worst = int(np.nanargmax(res))
        self.lbl_loo.setText(
            f"LOO RMS: {rms:.3f} m  ·  peor: GCP {worst + 1} ({res[worst]:.2f} m)")
        # lista ordenada de peor a mejor, con color de semáforo
        order = np.argsort(-res)
        for i in order:
            r = float(res[i])
            rc, gc, bc = diag.residual_color(r, tol)
            it = QListWidgetItem(f"GCP {i + 1:>2}   {r:7.3f} m")
            it.setForeground(QColor(rc, gc, bc).darker(160))
            it.setData(Qt.ItemDataRole.UserRole, int(i))
            self.list_loo.addItem(it)

    def _selected_ref_layers(self):
        ids = [self.ref_list.item(i).data(Qt.ItemDataRole.UserRole)
               for i in range(self.ref_list.count())
               if self.ref_list.item(i).isSelected()]
        return [QgsProject.instance().mapLayer(i) for i in ids]

    def _run_detect(self):
        if not self._ensure_item():
            return
        refs = self._selected_ref_layers()
        if not refs:
            QMessageBox.warning(self, "Falta referencia",
                                "Selecciona al menos una capa de referencia.")
            return
        det = "SIFT" if self.cmb_det.currentIndex() == 0 else "ORB"
        # la detección automática necesita OpenCV; ofrecer instalarlo si falta
        from . import dependencies as deps
        if deps.missing_dependencies():
            if not deps.prompt_and_install(self.iface.mainWindow()):
                self.lbl_status.setText(
                    "La detección automática necesita OpenCV. "
                    "Puedes capturar puntos a mano mientras tanto.")
                return
        self.lbl_status.setText("Detectando… (puede tardar unos segundos)")
        self.iface.mainWindow().repaint()
        try:
            from . import autodetect as ad   # import diferido (usa cv2)
            res = ad.auto_detect(self.item, self.canvas, refs,
                                 detector=det, max_gcps=self.spin_n.value())
        except Exception as e:
            QMessageBox.critical(self, "Error en detección", str(e))
            self.lbl_status.setText("Error.")
            return
        self.lbl_status.setText(res.get("msg", "Sin resultado.") +
                                ("  Ajusta a mano si hace falta." if res.get("ok")
                                 else "  Prueba ORB o acerca el zoom al solape."))
        self._on_gcp_change()

    def _place_permanent(self):
        if self.item is None or len(self.item.src_px) < 1:
            QMessageBox.warning(self, "Sin GCPs",
                                "Coloca al menos 1 punto de control primero.")
            return
        base = os.path.splitext(self.image_path)[0] + "_georef"
        method = "tps" if self.cmb_method.currentIndex() == 0 else "poly"
        try:
            src = self._src_for_warp or self.image_path
            out = gl.build_placement(src, self.item.fwd,
                                     self.item.gcps_original_px(), self.item.map_xy,
                                     self._crs_authid(), base, method=method,
                                     src_scale=self.item.src_scale)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        nm = "Georef · " + os.path.splitext(os.path.basename(self.image_path))[0]
        lyr = QgsRasterLayer(out, nm)
        if lyr.isValid():
            QgsProject.instance().addMapLayer(lyr)
            self.lbl_status.setText(
                f"Capa permanente colocada en el panel: {os.path.basename(out)}")
        else:
            QMessageBox.critical(self, "Capa inválida",
                                 f"No se pudo cargar la capa generada:\n{out}")

    def _export(self):
        if self.item is None or len(self.item.src_px) < 3:
            QMessageBox.warning(self, "Faltan GCPs",
                                "Necesitas al menos 3 puntos de control para exportar.")
            return
        out, _ = QFileDialog.getSaveFileName(self, "Guardar GeoTIFF", "",
                                             "GeoTIFF (*.tif)")
        if not out:
            return
        crs = self.canvas.mapSettings().destinationCrs().authid()
        method = "tps" if self.cmb_method.currentIndex() == 0 else "poly"
        try:
            ex.export_geotiff(self._src_for_warp or self.image_path,
                              self.item.gcps_original_px(),
                              self.item.map_xy, out, crs, method=method)
        except Exception as e:
            QMessageBox.critical(self, "Error al exportar", str(e))
            return
        if os.path.exists(out):
            self.iface.addRasterLayer(out, os.path.basename(out))
        self.lbl_status.setText(f"Exportado: {out}")

    def _finish_session(self, remove_layer=True):
        """Quita el item flotante, opcionalmente la capa VRT, y resetea estado."""
        # 1) desconectar la señal de extent (cada paso en su propio try)
        if self.item is not None:
            try:
                self.canvas.extentsChanged.disconnect(self.item.updatePosition)
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
            try:
                self.canvas.scene().removeItem(self.item)   # quita el flotante
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
        # 2) soltar la herramienta de mapa
        try:
            if self.tool is not None:
                self.canvas.unsetMapTool(self.tool)
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)
        # 3) la capa VRT: por defecto se queda en la TOC (georreferenciada);
        #    si el usuario pide quitarla, se elimina del proyecto
        if remove_layer and self.geo_layer is not None:
            try:
                if not sip.isdeleted(self.geo_layer):
                    QgsProject.instance().removeMapLayer(self.geo_layer.id())
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
        self._src_for_warp = None
        # 4) limpiar temporales
        try:
            if self._tmpdir and os.path.isdir(self._tmpdir):
                import shutil
                shutil.rmtree(self._tmpdir, ignore_errors=True)
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)
        # 5) refrescar y resetear
        self.item = None
        self.tool = None
        self.geo_layer = None
        self._tmpdir = None
        self.canvas.refresh()
        self.lbl_status.setText("Sesión terminada.")
