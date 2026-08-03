# -*- coding: utf-8 -*-
"""
Pruebas de service_catalog + wfs_source.

Corren SIN QGIS: `layer_scanner` solo usa `os`, y `wfs_source` importa
qgis.core de forma perezosa dentro de `validar_capa`. Ejecutar con:

    python -m unittest discover -s tools/superposition/tests -v
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import types
import unittest

# El __init__.py de tools/superposition importa core.base_tool, que a su
# vez arrastra qgis. Para probar la lógica pura se monta un paquete
# sintético que expone los módulos sin ejecutar esa cadena.
_AQUI = os.path.dirname(os.path.abspath(__file__))
_SUP = os.path.abspath(os.path.join(_AQUI, ".."))

_PKG = "yf_sup_test"
if _PKG not in sys.modules:
    _paquete = types.ModuleType(_PKG)
    _paquete.__path__ = [_SUP]
    sys.modules[_PKG] = _paquete


def _cargar(nombre):
    completo = "{}.{}".format(_PKG, nombre)
    if completo in sys.modules:
        return sys.modules[completo]
    spec = importlib.util.spec_from_file_location(
        completo, os.path.join(_SUP, nombre + ".py"))
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[completo] = modulo
    spec.loader.exec_module(modulo)
    return modulo


_cargar("layer_scanner")          # requerido por wfs_source
sc = _cargar("service_catalog")
tr = _cargar("traceability")
ws = _cargar("wfs_source")
CapaEncontrada = sys.modules[_PKG + ".layer_scanner"].CapaEncontrada


class TestCatalogoFabrica(unittest.TestCase):

    def setUp(self):
        self.cat = sc.CatalogoServicios()

    def test_grupo_peru_existe(self):
        self.assertIn("Perú", self.cat.grupos())

    def test_siete_servicios_precargados(self):
        self.assertEqual(len(self.cat.servicios("Perú")), 7)

    def test_entidades_cubiertas(self):
        entidades = {c.entidad for c in self.cat.capas(solo_activas=False)}
        self.assertEqual(entidades, {"SERFOR", "SERNANP", "MIDAGRI"})

    def test_zona_amortiguamiento_presente_y_activa(self):
        """Pesa tanto como el ANP en un análisis de superposición."""
        activas = {c.titulo: c for c in self.cat.capas()}
        self.assertIn("Zona de Amortiguamiento", activas)
        self.assertEqual(activas["Zona de Amortiguamiento"].rest_id, 8)

    def test_predio_rural_midagri(self):
        capa = next(c for c in self.cat.capas() if c.titulo == "Predio Rural")
        self.assertEqual(capa.entidad, "MIDAGRI")
        self.assertEqual(capa.rest_id, 0)
        self.assertTrue(capa.soporta_rest())

    def test_zonificacion_interna_inactiva(self):
        activas = [c.titulo for c in self.cat.capas()]
        for t in ("Zonificación ANP", "Zonificación ACR", "Zonificación ACP"):
            self.assertNotIn(t, activas)

    def test_advertencias_por_entidad_no_se_mezclan(self):
        """Cada entidad aporta su propio texto legal, sin duplicar."""
        textos = self.cat.advertencias_legales(self.cat.capas())
        self.assertEqual(len(textos), 3)
        self.assertTrue(any("29763" in t for t in textos))   # SERFOR
        self.assertTrue(any("26834" in t for t in textos))   # SERNANP
        self.assertTrue(any("SUNARP" in t for t in textos))  # MIDAGRI

    def test_concesiones_forestales_presente_y_activa(self):
        capas = self.cat.capas()
        titulos = [c.titulo for c in capas]
        self.assertIn("Concesiones Forestales", titulos)

    def test_typename_concesiones_es_el_verificado(self):
        capa = next(c for c in self.cat.capas()
                    if c.titulo == "Concesiones Forestales")
        self.assertEqual(
            capa.typename,
            "Servicios_OGC_Modalidad_Acceso:Concesiones_Forestales")
        self.assertEqual(capa.rest_id, 6)

    def test_focos_de_calor_inactivos_por_defecto(self):
        activos = [c.titulo for c in self.cat.capas(solo_activas=True)]
        self.assertNotIn("Focos de Calor", activos)
        todos = [c.titulo for c in self.cat.capas(solo_activas=False)]
        self.assertIn("Focos de Calor", todos)

    def test_ordenamiento_forestal_activo_por_rest(self):
        """WFS da 400, pero arcgisfeatureserver sobre /rest/ sí funciona."""
        activas = [c.titulo for c in self.cat.capas(solo_activas=True)]
        self.assertIn("Bosques de Producción Permanente", activas)
        capa = next(c for c in self.cat.capas()
                    if c.titulo == "Bosques de Producción Permanente")
        self.assertEqual(capa.tipo, "rest")
        self.assertFalse(capa.soporta_wfs())
        self.assertTrue(capa.soporta_rest())

    def test_urls_rest_llevan_el_segmento_rest(self):
        """Regresión: /services/ devuelve 403 en peticiones REST."""
        for c in self.cat.capas(solo_activas=False):
            if c.url_rest:
                self.assertIn("/rest/services/", c.url_rest,
                              "url_rest sin /rest/ en %s" % c.nombre_completo)

    def test_urls_wfs_no_llevan_el_segmento_rest(self):
        for c in self.cat.capas(solo_activas=False):
            if c.url_wfs:
                self.assertNotIn("/rest/", c.url_wfs)
                self.assertTrue(c.url_wfs.endswith("/WFSServer"))

    def test_todos_los_servicios_llevan_fecha_de_verificacion(self):
        self.assertEqual(self.cat.capas_sin_verificar(), [])

    def test_advertencia_serfor_una_sola_vez(self):
        """5 servicios del SERFOR comparten un único texto legal."""
        serfor = [c for c in self.cat.capas() if c.entidad == "SERFOR"]
        textos = self.cat.advertencias_legales(serfor)
        self.assertEqual(len(textos), 1)
        self.assertIn("29763", textos[0])


class TestPersistencia(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ruta = os.path.join(self.tmp, "config", "geoservicios.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_guardar_y_recargar(self):
        cat = sc.CatalogoServicios(ruta=self.ruta)
        cat.agregar_servicio(
            "Bolivia", "ABT — Concesiones",
            url_wfs="https://ejemplo.bo/wfs", tipo="wfs",
            capas=[{"titulo": "Concesiones", "typename": "abt:conc",
                    "rest_id": None, "activa": True}])
        cat.guardar()
        self.assertTrue(os.path.exists(self.ruta))

        recargado = sc.CatalogoServicios.cargar(self.ruta)
        self.assertIn("Bolivia", recargado.grupos())
        self.assertIn("Perú", recargado.grupos())

    def test_extensible_sin_tocar_codigo(self):
        cat = sc.CatalogoServicios(ruta=self.ruta)
        cat.agregar_grupo("Colombia")
        cat.guardar()
        with open(self.ruta, encoding="utf-8") as fh:
            crudo = json.load(fh)
        self.assertIn("Colombia", crudo["grupos"])

    def test_json_corrupto_no_rompe_ni_se_pierde(self):
        os.makedirs(os.path.dirname(self.ruta))
        with open(self.ruta, "w", encoding="utf-8") as fh:
            fh.write("{ esto no es json valido")
        cat = sc.CatalogoServicios.cargar(self.ruta)
        self.assertIn("Perú", cat.grupos())
        self.assertTrue(os.path.exists(self.ruta + ".corrupto"))

    def test_servicio_nuevo_sin_verificar_se_detecta(self):
        cat = sc.CatalogoServicios(ruta=self.ruta)
        cat.agregar_servicio(
            "Brasil", "SFB — Florestas", url_wfs="https://ejemplo.br/wfs",
            capas=[{"titulo": "Florestas", "typename": "sfb:f",
                    "rest_id": None, "activa": True}])
        sin_verificar = [c.titulo for c in cat.capas_sin_verificar()]
        self.assertIn("Florestas", sin_verificar)


class TestConstruccionURI(unittest.TestCase):

    def setUp(self):
        self.cat = sc.CatalogoServicios()
        self.concesiones = next(c for c in self.cat.capas()
                                if c.titulo == "Concesiones Forestales")

    def test_uri_wfs_restringe_bbox(self):
        uri = ws.construir_uri_wfs(self.concesiones)
        self.assertIn("restrictToRequestBBOX='1'", uri)

    def test_uri_wfs_contiene_typename_y_url(self):
        uri = ws.construir_uri_wfs(self.concesiones)
        self.assertIn(
            "typename='Servicios_OGC_Modalidad_Acceso:Concesiones_Forestales'",
            uri)
        self.assertIn("WFSServer", uri)

    def test_bbox_desactivable(self):
        uri = ws.construir_uri_wfs(self.concesiones, restringir_bbox=False)
        self.assertIn("restrictToRequestBBOX='0'", uri)

    def test_uri_rest_apunta_al_id_de_capa(self):
        bpp = next(c for c in self.cat.capas()
                   if c.titulo == "Bosques de Producción Permanente")
        uri = ws.construir_uri_rest(bpp)
        self.assertTrue(uri.endswith("/MapServer/2'"))

    def test_seleccion_de_proveedor(self):
        _, prov = ws.uri_para(self.concesiones)
        self.assertEqual(prov, ws.PROVIDER_WFS)
        bpp = next(c for c in self.cat.capas()
                   if c.titulo == "Bosques de Producción Permanente")
        _, prov_rest = ws.uri_para(bpp)
        self.assertEqual(prov_rest, ws.PROVIDER_REST)

    def test_capa_desde_servicio_es_remota(self):
        ce = ws.capa_desde_servicio(self.concesiones)
        self.assertIsInstance(ce, CapaEncontrada)
        self.assertTrue(ce.remota)
        self.assertEqual(ce.provider, "WFS")

    def test_entrada_incompleta_devuelve_none(self):
        rota = sc.ServicioCapa(
            grupo="X", servicio="Y", titulo="Z", typename="", rest_id=None,
            tipo="wfs", url_wfs="", url_rest="", srs="EPSG:4326",
            entidad="", advertencia_legal="", verificado="")
        self.assertIsNone(ws.capa_desde_servicio(rota))


class TestCapaEncontradaCompatibilidad(unittest.TestCase):
    """El cambio no debe romper el camino de archivos en disco."""

    def test_firma_antigua_sigue_funcionando(self):
        ce = CapaEncontrada("/datos/x.shp", "x", "/datos/x.shp")
        self.assertEqual(ce.provider, "ogr")
        self.assertFalse(ce.remota)

    def test_origen_corto_archivo(self):
        ce = CapaEncontrada("/datos/concesiones.shp", "c",
                            "/datos/concesiones.shp")
        self.assertEqual(ce.origen_corto(), "concesiones.shp")

    def test_origen_corto_remota_no_devuelve_basura(self):
        ce = CapaEncontrada(
            "uri", "Concesiones",
            "https://geo.serfor.gob.pe/geoservicios/services/X/MapServer/WFSServer",
            provider="WFS", remota=True,
            origen_etiqueta="SERFOR · Concesiones Forestales")
        self.assertEqual(ce.origen_corto(), "SERFOR · Concesiones Forestales")
        self.assertNotEqual(ce.origen_corto(), "WFSServer")


class TestTrazabilidadRemota(unittest.TestCase):

    def test_ficha_servicio_declara_su_naturaleza(self):
        f = tr.ficha_servicio("https://x/WFSServer", uri="u", provider="WFS",
                              crs="EPSG:4326", features=1,
                              nombre_capa="Concesiones")
        self.assertTrue(f["es_remota"])
        self.assertIsNone(f["sha256"])
        self.assertEqual(f["naturaleza"], "instantanea_remota")
        self.assertIn("consultado_iso", f)

    def test_verificar_no_da_falso_negativo(self):
        f = tr.ficha_servicio("https://x/WFSServer")
        res = tr.verificar_archivo(f)
        self.assertTrue(res.get("no_verificable"))
        self.assertFalse(res.get("hash_coincide"))

    def test_ficha_archivo_sigue_intacta(self):
        with tempfile.NamedTemporaryFile(suffix=".shp", delete=False) as fh:
            fh.write(b"contenido")
            ruta = fh.name
        try:
            f = tr.ficha_archivo(ruta)
            self.assertIsNotNone(f["sha256"])
            self.assertNotIn("es_remota", f)
            self.assertTrue(tr.verificar_archivo(f)["hash_coincide"])
        finally:
            os.unlink(ruta)


class TestControlDeRitmo(unittest.TestCase):
    """El 403 del SERFOR obliga a espaciar peticiones."""

    def test_existe_intervalo_minimo(self):
        self.assertGreaterEqual(ws.INTERVALO_MINIMO_S, 0.5)

    def test_throttle_espacia_por_host(self):
        import time
        ws._ultimo_acceso.clear()
        url = "https://geo.serfor.gob.pe/geoservicios/x"
        t0 = time.time()
        ws._throttle(url)
        ws._throttle(url)
        self.assertGreaterEqual(time.time() - t0, ws.INTERVALO_MINIMO_S * 0.9)

    def test_hosts_distintos_no_se_penalizan(self):
        import time
        ws._ultimo_acceso.clear()
        t0 = time.time()
        ws._throttle("https://a.gob.pe/x")
        ws._throttle("https://b.gob.pe/x")
        self.assertLess(time.time() - t0, ws.INTERVALO_MINIMO_S)


class TestFusionConFabrica(unittest.TestCase):
    """Un JSON guardado no debe congelar al usuario en esa versión."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ruta = os.path.join(self.tmp, "geoservicios.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _json_antiguo(self, servicios):
        """Simula un catálogo guardado con menos servicios."""
        cat = sc.CatalogoServicios(ruta=self.ruta)
        datos = {"version": 1, "grupos": {"Perú": {}}}
        for nombre in servicios:
            datos["grupos"]["Perú"][nombre] = (
                sc.CATALOGO_FABRICA["grupos"]["Perú"][nombre])
        with open(self.ruta, "w", encoding="utf-8") as fh:
            json.dump(datos, fh, ensure_ascii=False)
        return cat

    def test_servicios_nuevos_se_incorporan(self):
        self._json_antiguo(["SERFOR — Modalidad de Acceso"])
        cat = sc.CatalogoServicios.cargar(self.ruta)
        self.assertEqual(len(cat.servicios("Perú")), 7)
        self.assertTrue(any("SERNANP" in i for i in cat.incorporados))
        self.assertTrue(any("MIDAGRI" in i for i in cat.incorporados))

    def test_no_pisa_lo_que_el_usuario_edito(self):
        self._json_antiguo(["SERFOR — Modalidad de Acceso"])
        with open(self.ruta, encoding="utf-8") as fh:
            d = json.load(fh)
        d["grupos"]["Perú"]["SERFOR — Modalidad de Acceso"]["url_wfs"] = "MIA"
        with open(self.ruta, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False)

        cat = sc.CatalogoServicios.cargar(self.ruta)
        capa = next(c for c in cat.capas(solo_activas=False)
                    if c.servicio == "SERFOR — Modalidad de Acceso")
        self.assertEqual(capa.url_wfs, "MIA")

    def test_divergencia_se_detecta(self):
        self._json_antiguo(["SERFOR — Modalidad de Acceso"])
        with open(self.ruta, encoding="utf-8") as fh:
            d = json.load(fh)
        d["grupos"]["Perú"]["SERFOR — Modalidad de Acceso"]["url_rest"] = "vieja"
        with open(self.ruta, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False)

        cat = sc.CatalogoServicios.cargar(self.ruta)
        div = cat.divergencias_con_fabrica()
        self.assertTrue(any(c == "url_rest" and mio == "vieja"
                            for _, _, c, mio, _ in div))

    def test_borrado_deliberado_no_resucita(self):
        cat = sc.CatalogoServicios(ruta=self.ruta)
        cat.eliminar_servicio("Perú", "SERFOR — Unidad de Monitoreo Satelital")
        cat.guardar()
        recargado = sc.CatalogoServicios.cargar(self.ruta)
        self.assertNotIn("SERFOR — Unidad de Monitoreo Satelital",
                         recargado.servicios("Perú"))
        self.assertEqual(len(recargado.servicios("Perú")), 6)

    def test_restaurar_servicio_revierte(self):
        cat = sc.CatalogoServicios(ruta=self.ruta)
        cat.datos["grupos"]["Perú"]["MIDAGRI — Catastro Rural"]["url_rest"] = "x"
        self.assertTrue(cat.restaurar_servicio("Perú", "MIDAGRI — Catastro Rural"))
        capa = next(c for c in cat.capas() if c.entidad == "MIDAGRI")
        self.assertIn("/rest/services/", capa.url_rest)

    def test_fusion_es_idempotente(self):
        self._json_antiguo(["SERFOR — Modalidad de Acceso"])
        c1 = sc.CatalogoServicios.cargar(self.ruta)
        c1.guardar()
        c2 = sc.CatalogoServicios.cargar(self.ruta)
        self.assertEqual(c2.incorporados, [])
        self.assertEqual(len(c2.servicios("Perú")), 7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
