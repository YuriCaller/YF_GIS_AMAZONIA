# -*- coding: utf-8 -*-
"""
html_report.py
Genera informe HTML como fallback cuando reportlab no está disponible.
Mismo contenido que el PDF pero en HTML autocontenido.
"""
import os
import datetime
from ..gnss_engine.config_builder import ProcessingParams
from ..results.pos_parser import PosStats, Q_LABELS, Q_COLORS_HEX


class HTMLReportGenerator:
    def __init__(self, params: ProcessingParams, meta: dict, stats: PosStats):
        self.p  = params
        self.m  = meta
        self.st = stats

    def generate(self) -> str:
        path = os.path.join(self.p.out_dir, self.p.out_prefix + '_informe.html')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self._build())
        return path

    def _build(self) -> str:
        p  = self.p
        st = self.st
        m  = self.m
        bc = p.base_coords
        now = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
        total = st.total or 1

        def bar(pct, color):
            return (f'<div style="display:inline-block;width:{pct:.1f}%;'
                    f'background:{color};height:20px;vertical-align:middle;'
                    f'min-width:2px;"></div>')

        fix_pct   = st.fix_count / total * 100
        float_pct = st.float_count / total * 100
        ppp_pct   = st.ppp_count / total * 100
        other_pct = max(0, 100 - fix_pct - float_pct - ppp_pct)

        traz_html = ''
        if bc and bc.fue_corregida:
            dh = bc.delta_horizontal_m or 0
            dv = bc.delta_vertical_m or 0
            traz_html = f'''
            <div style="background:#fff3e0;border-left:4px solid #e65100;padding:10px;margin:10px 0;border-radius:3px;">
              <strong>⚠️ TRAZABILIDAD:</strong> Coordenadas de base CORREGIDAS<br>
              ΔHorizontal = <strong>{dh:.4f} m</strong> &nbsp;|&nbsp; ΔVertical = <strong>{dv:.4f} m</strong><br>
              RINEX original: Lat={bc.rinex_lat:.8f}° Lon={bc.rinex_lon:.8f}° h={bc.rinex_h:.4f}m<br>
              IGN aplicado:   Lat={bc.lat_dd:.8f}° Lon={bc.lon_dd:.8f}° h={bc.h_elip:.4f}m
            </div>'''

        return f'''<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
<title>Informe GNSS — {m.get("proyecto","")}</title>
<style>
  body{{font-family:Arial,sans-serif;font-size:12px;color:#1a1a1a;background:#f5f5f0;margin:0;}}
  .page{{max-width:900px;margin:0 auto;background:white;}}
  .cover{{background:linear-gradient(135deg,#1a472a,#40916c);color:white;padding:36px 32px;}}
  .cover h1{{font-size:22px;margin:0 0 6px;}}
  .cover p{{margin:3px 0;color:#b7e4c7;font-size:11px;}}
  .sec{{padding:20px 32px;border-bottom:1px solid #eee;}}
  .sec h2{{color:#1a472a;font-size:13px;border-bottom:2px solid #2d6a4f;padding-bottom:4px;}}
  table{{width:100%;border-collapse:collapse;font-size:11px;margin:8px 0;}}
  th{{background:#1a472a;color:white;padding:6px 8px;text-align:left;}}
  td{{padding:5px 8px;border-bottom:1px solid #eee;}}
  tr:nth-child(even) td{{background:#f9f9f7;}}
  .footer{{background:#1a472a;color:#b7e4c7;text-align:center;padding:10px;font-size:10px;}}
</style></head><body><div class="page">
<div class="cover">
  <div style="font-size:28px;margin-bottom:10px;">🛰️</div>
  <h1>Informe Técnico — Post-Proceso GNSS</h1>
  <p>{m.get("proyecto","")}</p>
  <p>{m.get("profesional","")} · {m.get("cip","")}</p>
  <p>{m.get("lugar","")} · {now}</p>
</div>

<div class="sec"><h2>1. Resumen del procesamiento</h2>
  <p>Modo: <strong>{p.mode.upper()}</strong> | Solución: {p.solution_type} | Filtro: {p.kalman_filter}</p>
  <p>Épocas totales: <strong>{st.total}</strong></p>
  <div style="width:100%;height:20px;background:#eee;border-radius:3px;overflow:hidden;margin:8px 0;">
    {bar(fix_pct,"#4caf50")}{bar(float_pct,"#ffd600")}{bar(ppp_pct,"#6200ea")}{bar(other_pct,"#f44336")}
  </div>
  <table>
    <tr><th>Solución</th><th>Épocas</th><th>%</th><th>RMS (m)</th></tr>
    <tr><td>Fix (Q=1)</td><td>{st.fix_count}</td><td>{fix_pct:.1f}%</td><td>N:{st.rms_n:.5f} E:{st.rms_e:.5f} U:{st.rms_u:.5f}</td></tr>
    <tr><td>Float (Q=2)</td><td>{st.float_count}</td><td>{float_pct:.1f}%</td><td>—</td></tr>
    <tr><td>PPP (Q=6)</td><td>{st.ppp_count}</td><td>{ppp_pct:.1f}%</td><td>—</td></tr>
  </table>
</div>

<div class="sec"><h2>2. Base de referencia</h2>
  {'<p>Modo PPP — No aplica base de referencia.</p>' if p.mode == 'ppp' else f"""
  <table>
    <tr><th>Campo</th><th>Valor</th></tr>
    <tr><td>Fuente</td><td>{bc.fuente if bc else '—'}</td></tr>
    <tr><td>Lat (°)</td><td><code>{bc.lat_dd:.10f}</code></td></tr>
    <tr><td>Lon (°)</td><td><code>{bc.lon_dd:.10f}</code></td></tr>
    <tr><td>h elipsoidal (m)</td><td><code>{bc.h_elip:.4f}</code></td></tr>
    <tr><td>Corregida</td><td>{'SÍ' if bc.fue_corregida else 'NO'}</td></tr>
  </table>{traz_html}"""}
</div>

<div class="sec"><h2>3. Equipo y software</h2>
  <table>
    <tr><th>Campo</th><th>Valor</th></tr>
    <tr><td>Receptor</td><td>{m.get("receptor","")}</td></tr>
    <tr><td>Antena</td><td>{m.get("antena","")}</td></tr>
    <tr><td>Software</td><td>RTKLIB rnx2rtkp</td></tr>
  </table>
</div>

{'<div class="sec"><h2>4. Observaciones</h2><p>' + m.get("notas","") + '</p></div>' if m.get("notas") else ""}

<div class="footer">GNSS Post-Process v2.0 · {m.get("profesional","")} · {m.get("cip","")} · {now}</div>
</div></body></html>'''
