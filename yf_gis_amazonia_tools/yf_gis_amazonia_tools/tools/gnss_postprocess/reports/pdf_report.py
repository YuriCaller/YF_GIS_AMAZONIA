# -*- coding: utf-8 -*-
"""
pdf_report.py
Genera el informe técnico de fidelidad del post-proceso GNSS usando reportlab.
Si reportlab no está disponible, genera HTML equivalente como fallback.
"""
import os
import datetime
import json
from ..gnss_engine.config_builder import ProcessingParams
from ..gnss_engine.coord_converter import BaseCoords
from ..results.pos_parser import PosStats, Q_LABELS


class PDFReportGenerator:
    """
    Genera informe técnico completo en PDF.
    Secciones según spec del prompt:
      1. Portada / encabezado
      2. Resumen del procesamiento
      3. Información de la base (con trazabilidad si fue corregida)
      4. Parámetros RTKLIB usados
      5. Métricas de calidad
      6. Observaciones técnicas
    """

    def __init__(self, params: ProcessingParams,
                 report_meta: dict,
                 stats: PosStats):
        self.p    = params
        self.meta = report_meta   # profesional, cip, empresa, proyecto, etc.
        self.st   = stats

    # ══════════════════════════════════════════════
    # PUNTO DE ENTRADA
    # ══════════════════════════════════════════════
    def generate(self) -> str:
        """Genera PDF o HTML como fallback. Retorna ruta del archivo."""
        try:
            return self._generate_pdf()
        except ImportError:
            return self._generate_html_fallback()

    # ══════════════════════════════════════════════
    # PDF (reportlab)
    # ══════════════════════════════════════════════
    def _generate_pdf(self) -> str:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table,
            TableStyle, HRFlowable, KeepTogether
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

        p  = self.p
        st = self.st
        m  = self.meta
        bc: BaseCoords = p.base_coords
        now = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')

        # ── Colores institucionales
        VERDE   = colors.HexColor('#1a472a')
        VERDE_L = colors.HexColor('#2d6a4f')
        VERDE_S = colors.HexColor('#e8f5e9')
        GRIS    = colors.HexColor('#f5f5f0')
        NEGRO   = colors.HexColor('#1a1a1a')
        ROJO    = colors.HexColor('#c62828')
        AZUL    = colors.HexColor('#1565c0')

        # ── Estilos
        styles = getSampleStyleSheet()
        s_titulo = ParagraphStyle('titulo',
            fontSize=18, textColor=colors.white,
            fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=4)
        s_sub = ParagraphStyle('sub',
            fontSize=11, textColor=colors.HexColor('#b7e4c7'),
            fontName='Helvetica', alignment=TA_CENTER, spaceAfter=2)
        s_h1 = ParagraphStyle('h1',
            fontSize=12, textColor=VERDE, fontName='Helvetica-Bold',
            spaceBefore=10, spaceAfter=4,
            borderPadding=(0, 0, 2, 0))
        s_body = ParagraphStyle('body',
            fontSize=9, textColor=NEGRO, fontName='Helvetica',
            spaceAfter=3, leading=13)
        s_warn = ParagraphStyle('warn',
            fontSize=9, textColor=ROJO, fontName='Helvetica-Bold', spaceAfter=3)
        s_mono = ParagraphStyle('mono',
            fontSize=8, textColor=NEGRO, fontName='Courier', spaceAfter=2)

        # ── Output
        out_path = os.path.join(
            p.out_dir,
            f'{p.out_prefix}_informe.pdf'
        )
        doc = SimpleDocTemplate(
            out_path, pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm
        )
        story = []

        # ─────────────── PORTADA ───────────────────
        portada_data = [
            [Paragraph('🛰️  GNSS Post-Process PPK/PPP v2', s_titulo)],
            [Paragraph(f'Informe Técnico de Fidelidad — {m.get("proyecto","")}', s_sub)],
            [Paragraph(f'{m.get("profesional","")}  ·  {m.get("cip","")}', s_sub)],
            [Paragraph(f'{m.get("lugar","")}  ·  {now}', s_sub)],
        ]
        portada_table = Table(portada_data, colWidths=[17*cm])
        portada_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), VERDE),
            ('ROWPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,0), 18),
            ('BOTTOMPADDING', (0,-1), (-1,-1), 18),
            ('ROUNDEDCORNERS', [5]),
        ]))
        story.append(portada_table)
        story.append(Spacer(1, 0.5*cm))

        # ─────────────── 1. RESUMEN ────────────────
        story.append(Paragraph('1. Resumen del Procesamiento', s_h1))
        story.append(HRFlowable(width='100%', thickness=1.5, color=VERDE_L))
        story.append(Spacer(1, 0.2*cm))

        total = st.total or 1
        resumen_data = [
            ['Parámetro', 'Valor'],
            ['Modo de procesamiento', f'{p.mode.upper()} — {p.solution_type}'],
            ['Filtro Kalman', p.kalman_filter.capitalize()],
            ['Frecuencias', f'L{p.freq}'],
            ['Constelaciones (navsys)', f'0x{p.navsys:02X}'],
            ['Máscara de elevación', f'{p.elev_mask_deg}°'],
            ['Épocas totales', str(st.total)],
            ['Solución Fix (Q=1)', f'{st.fix_count}  ({st.fix_pct:.1f}%)'],
            ['Solución Float (Q=2)', f'{st.float_count}  ({st.float_pct:.1f}%)'],
            ['Solución PPP (Q=6)', f'{st.ppp_count}  ({st.ppp_pct:.1f}%)'],
            ['RMS Norte', f'{st.rms_n:.5f} m'],
            ['RMS Este',  f'{st.rms_e:.5f} m'],
            ['RMS Vertical', f'{st.rms_u:.5f} m'],
        ]
        story.append(self._styled_table(resumen_data, VERDE, VERDE_S, GRIS))
        story.append(Spacer(1, 0.3*cm))

        # ─────────────── 2. BASE ────────────────────
        story.append(Paragraph('2. Base de Referencia', s_h1))
        story.append(HRFlowable(width='100%', thickness=1.5, color=VERDE_L))
        story.append(Spacer(1, 0.2*cm))

        if p.mode == 'ppk' and bc:
            corregida_str = 'SÍ — Coordenadas corregidas respecto al RINEX header' \
                            if bc.fue_corregida else 'NO — Coincide con RINEX header'
            base_data = [
                ['Campo', 'Valor'],
                ['Fuente de coordenadas', bc.fuente],
                ['Datum', bc.datum],
                ['Latitud (°)', f'{bc.lat_dd:.10f}'],
                ['Longitud (°)', f'{bc.lon_dd:.10f}'],
                ['Altura elipsoidal (m)', f'{bc.h_elip:.4f}'],
            ]
            if bc.zona_utm:
                base_data += [
                    ['Zona UTM', bc.zona_utm],
                    ['Este UTM (m)', f'{bc.este_utm:.3f}'],
                    ['Norte UTM (m)', f'{bc.norte_utm:.3f}'],
                ]
            base_data.append(['Coordenadas corregidas', corregida_str])

            story.append(self._styled_table(base_data, VERDE, VERDE_S, GRIS))

            # Trazabilidad (si fue corregida)
            if bc.fue_corregida:
                story.append(Spacer(1, 0.2*cm))
                dh = bc.delta_horizontal_m or 0.0
                dv = bc.delta_vertical_m or 0.0
                story.append(Paragraph(
                    f'⚠️  TRAZABILIDAD: Las coordenadas de la base fueron corregidas. '
                    f'ΔHorizontal = {dh:.4f} m   ΔVertical = {dv:.4f} m', s_warn))
                if bc.rinex_lat:
                    traz_data = [
                        ['', 'Lat (°)', 'Lon (°)', 'h (m)'],
                        ['RINEX header (original)',
                         f'{bc.rinex_lat:.10f}', f'{bc.rinex_lon:.10f}', f'{bc.rinex_h:.4f}'],
                        ['Coordenadas IGN (usadas)',
                         f'{bc.lat_dd:.10f}', f'{bc.lon_dd:.10f}', f'{bc.h_elip:.4f}'],
                        ['Diferencia',
                         f'{abs(bc.lat_dd-bc.rinex_lat)*111320:.4f} m',
                         f'{abs(bc.lon_dd-bc.rinex_lon)*111320:.4f} m',
                         f'{dv:.4f} m'],
                    ]
                    story.append(self._styled_table(traz_data, ROJO,
                                                    colors.HexColor('#ffebee'),
                                                    colors.HexColor('#fce4ec')))
        else:
            story.append(Paragraph('Modo PPP — No aplica base de referencia.', s_body))

        story.append(Spacer(1, 0.3*cm))

        # ─────────────── 3. MÉTRICAS ────────────────
        story.append(Paragraph('3. Métricas de Calidad', s_h1))
        story.append(HRFlowable(width='100%', thickness=1.5, color=VERDE_L))
        story.append(Spacer(1, 0.2*cm))

        metricas_data = [
            ['Tipo solución', 'Código Q', 'Épocas', '%', 'Calificación'],
        ]
        for q, label in Q_LABELS.items():
            cnt = st.count_q.get(q, 0)
            pct = cnt / total * 100
            cal = self._calidad_texto(q, pct)
            metricas_data.append([label, str(q), str(cnt), f'{pct:.2f}%', cal])

        story.append(self._styled_table(metricas_data, VERDE, VERDE_S, GRIS))

        # RMS
        story.append(Spacer(1, 0.2*cm))
        rms_data = [
            ['Componente', 'RMS (m)', 'Evaluación'],
            ['Norte (N)', f'{st.rms_n:.5f}', self._eval_rms(st.rms_n, 0.05)],
            ['Este  (E)', f'{st.rms_e:.5f}', self._eval_rms(st.rms_e, 0.05)],
            ['Vertical (U)', f'{st.rms_u:.5f}', self._eval_rms(st.rms_u, 0.10)],
        ]
        if st.mean_lat:
            rms_data += [
                ['Coord. media Lat (°)', f'{st.mean_lat:.10f}', ''],
                ['Coord. media Lon (°)', f'{st.mean_lon:.10f}', ''],
                ['Altura media (m)',     f'{st.mean_h:.4f}', ''],
            ]
        story.append(self._styled_table(rms_data, AZUL,
                                        colors.HexColor('#e3f2fd'),
                                        colors.HexColor('#f5f5f5')))
        story.append(Spacer(1, 0.3*cm))

        # ─────────────── 4. EQUIPO ──────────────────
        story.append(Paragraph('4. Equipo y Software', s_h1))
        story.append(HRFlowable(width='100%', thickness=1.5, color=VERDE_L))
        story.append(Spacer(1, 0.2*cm))

        eq_data = [
            ['Campo', 'Valor'],
            ['Receptor GNSS',  m.get('receptor', '')],
            ['Antena',         m.get('antena', '')],
            ['N° serie',       m.get('serial', '')],
            ['Software',       'RTKLIB rnx2rtkp (bundled)'],
            ['RINEX Rover',    os.path.basename(p.rinex_rover or '')],
            ['RINEX Base',     os.path.basename(p.rinex_base or '') or 'N/A (PPP)'],
            ['SP3',            os.path.basename(p.sp3_file or '') or 'N/A'],
            ['CLK',            os.path.basename(p.clk_file or '') or 'N/A'],
        ]
        story.append(self._styled_table(eq_data, VERDE, VERDE_S, GRIS))
        story.append(Spacer(1, 0.3*cm))

        # ─────────────── 5. OBSERVACIONES ──────────
        if m.get('notas'):
            story.append(Paragraph('5. Observaciones Técnicas', s_h1))
            story.append(HRFlowable(width='100%', thickness=1.5, color=VERDE_L))
            story.append(Spacer(1, 0.2*cm))
            story.append(Paragraph(m['notas'], s_body))

        # ─────────────── PIE ────────────────────────
        story.append(Spacer(1, 0.5*cm))
        pie_data = [[Paragraph(
            f'GNSS Post-Process v2.0  ·  {m.get("profesional","")}  ·  '
            f'{m.get("cip","")}  ·  Generado: {now}',
            ParagraphStyle('pie', fontSize=7.5, textColor=colors.white,
                           fontName='Helvetica', alignment=TA_CENTER)
        )]]
        pie_table = Table(pie_data, colWidths=[17*cm])
        pie_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), VERDE),
            ('ROWPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(pie_table)

        doc.build(story)
        return out_path

    # ══════════════════════════════════════════════
    # FICHA TÉCNICA IGN (JSON)
    # ══════════════════════════════════════════════
    def generate_ign_ficha_json(self, nombre_punto: str = '') -> str:
        """
        Genera ficha técnica de punto tipo IGN en formato JSON.
        """
        p  = self.p
        st = self.st
        m  = self.meta
        bc = p.base_coords

        ficha = {
            'ficha_tecnica_gnss': {
                'nombre_punto':       nombre_punto or p.out_prefix,
                'proyecto':           m.get('proyecto', ''),
                'profesional':        m.get('profesional', ''),
                'cip':                m.get('cip', ''),
                'empresa':            m.get('empresa', ''),
                'fecha_procesamiento': datetime.datetime.now().isoformat(),
                'metodo':             p.mode.upper(),
                'tipo_solucion':      p.solution_type,
                'software':           'RTKLIB rnx2rtkp',
                'receptor':           m.get('receptor', ''),
                'antena':             m.get('antena', ''),
                'serial':             m.get('serial', ''),
                'coordenadas_finales': {
                    'lat_dd':    st.mean_lat,
                    'lon_dd':    st.mean_lon,
                    'h_elip_m':  st.mean_h,
                    'precision_horizontal_m': round(
                        ((st.mean_sdn or 0)**2 + (st.mean_sde or 0)**2)**0.5, 5
                    ) if st.mean_sdn else None,
                    'precision_vertical_m':   st.mean_sdu,
                    'datum': 'WGS84 / SIRGAS 2000',
                },
                'calidad_procesamiento': {
                    'epocas_total':  st.total,
                    'fix_pct':       round(st.fix_pct, 2),
                    'float_pct':     round(st.float_pct, 2),
                    'ppp_pct':       round(st.ppp_pct, 2),
                    'rms_n_m':       round(st.rms_n, 5),
                    'rms_e_m':       round(st.rms_e, 5),
                    'rms_u_m':       round(st.rms_u, 5),
                },
                'base_referencia': {
                    'fuente':      bc.fuente if bc else 'N/A',
                    'datum':       bc.datum if bc else 'N/A',
                    'lat_dd':      bc.lat_dd if bc else None,
                    'lon_dd':      bc.lon_dd if bc else None,
                    'h_elip_m':    bc.h_elip if bc else None,
                    'fue_corregida': bc.fue_corregida if bc else False,
                    'delta_h_m':   bc.delta_horizontal_m if bc else None,
                    'delta_v_m':   bc.delta_vertical_m if bc else None,
                } if p.mode == 'ppk' else None,
                'archivos': {
                    'rinex_rover': os.path.basename(p.rinex_rover or ''),
                    'rinex_base':  os.path.basename(p.rinex_base or '') or None,
                    'sp3':         os.path.basename(p.sp3_file or '') or None,
                    'clk':         os.path.basename(p.clk_file or '') or None,
                },
                'notas': m.get('notas', ''),
            }
        }

        path = os.path.join(p.out_dir, p.out_prefix + '_ficha_ign.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(ficha, f, ensure_ascii=False, indent=2, default=str)
        return path

    # ══════════════════════════════════════════════
    # FALLBACK HTML
    # ══════════════════════════════════════════════
    def _generate_html_fallback(self) -> str:
        """HTML equivalente cuando reportlab no está disponible."""
        from ..reports.html_report import HTMLReportGenerator
        gen = HTMLReportGenerator(self.p, self.meta, self.st)
        return gen.generate()

    # ──────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────
    @staticmethod
    def _styled_table(data, header_color, even_color, odd_color):
        from reportlab.platypus import Table, TableStyle
        from reportlab.lib import colors
        t = Table(data, hAlign='LEFT')
        style = [
            ('BACKGROUND', (0,0), (-1,0), header_color),
            ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
            ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0,0), (-1,-1), 8.5),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [even_color, odd_color]),
            ('GRID',       (0,0), (-1,-1), 0.3, colors.HexColor('#cccccc')),
            ('ROWPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING',(0,0), (-1,-1), 6),
        ]
        t.setStyle(TableStyle(style))
        return t

    @staticmethod
    def _calidad_texto(q: int, pct: float) -> str:
        if q == 1:
            if pct >= 80: return '✅ Excelente'
            if pct >= 50: return '✔ Aceptable'
            return '⚠ Insuficiente'
        if q == 2:
            return '⚠ Revisar sesión' if pct > 40 else 'Normal'
        if q == 4:
            return '❌ Revisar datos' if pct > 20 else 'Marginal'
        return '—'

    @staticmethod
    def _eval_rms(val: float, umbral: float) -> str:
        if val == 0:
            return '—'
        if val < umbral:
            return f'✅ Alta precisión (<{umbral*100:.0f}cm)'
        if val < umbral * 3:
            return f'✔ Precis. media'
        return f'⚠ Revisar ({val:.3f}m)'
