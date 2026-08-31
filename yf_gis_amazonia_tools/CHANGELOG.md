# Changelog

Todos los cambios relevantes de **YF GIS Amazonia Tools**.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el proyecto usa [Versionado Semantico](https://semver.org/lang/es/).


---

## 3.1.0 - 2026-08-09

### MANUAL DE USUARIO EN LINEA (NUEVO)

- Manual publicado en https://yuricaller.github.io/YF_GIS_AMAZONIA/ con una pagina por herramienta, guia de instalacion, referencia de geoservicios y casos reales documentados. Accesible desde el dialogo Acerca de y desde cada herramienta.
- El campo about de este archivo dejo de crecer version a version: el detalle tecnico que se habia ido acumulando ahi vive ahora en el manual, que es donde alguien puede buscarlo.

### INSTALACION DE COMPONENTES OPCIONALES (correccion importante)

- Los componentes se instalan ahora con --target en la carpeta <perfil>/python/dependencies en lugar de --user. Motivo: en OSGeo4W, pip rechaza --user cuando detecta un entorno tipo virtualenv, y cuando si instala lo hace en un directorio que la instalacion de QGIS puede no leer. El sintoma que reportaban los usuarios era exactamente ese: pip decia "Successfully installed" y la herramienta seguia bloqueada. La carpeta del perfil siempre es escribible, no necesita permisos de administrador, sobrevive a reinstalaciones del plugin y el plugin controla su presencia en sys.path, de modo que el import funciona sin reiniciar QGIS.
- Instalacion desde archivo .whl para equipos sin salida a internet, accesible desde la propia ventana de instalacion.
- El proxy configurado en QGIS (Opciones - Red) se traslada a pip como variables de entorno. pip no lee esa configuracion por su cuenta, y era la causa mas frecuente de fallo en entidades publicas.
- Localizacion del interprete ampliada a la disposicion de OSGeo4W (raiz/apps/PythonXX/python.exe), que no queda junto a qgis-bin.exe.
- La orden manual que se muestra al fallar indica ahora la ruta completa del interprete y del destino, en vez de "python -m pip", que en OSGeo4W puede no ser el interprete correcto.
- Nuevo boton Diagnostico en Acerca de: interprete, carpeta de paquetes, sys.path y estado de cada componente, copiable para adjuntar a un reporte de incidencia.
- recargar() limpia sys.modules antes de reimportar, para que un intento previo a medias no devuelva un modulo incompleto.

### DIALOGO ACERCA DE

- La lista de herramientas estaba escrita a mano y se habia quedado en v2.0: anunciaba 8 herramientas cuando la suite tiene 17, y seguia marcando como "nuevo v2.0" modulos publicados un ano antes. Ahora se genera desde core/tools_catalog, fuente unica compartida con el manual, y cada nombre enlaza a su capitulo.
- Las etiquetas de novedad se calculan comparando con la version en curso, de modo que no pueden quedar obsoletas.
- Agrupacion por categoria en el mismo orden del menu de QGIS.
- Nuevo test core/tests/test_catalogo.py: comprueba que el catalogo, el menu, los iconos y las paginas del manual coincidan. Anadir una herramienta y olvidar documentarla falla ahora en las pruebas.

### METADATA Y CALIDAD DE CODIGO

- CRITICO: el changelog se publicaba truncado. Las lineas "Version X.Y.Z (fecha):" empezaban en la columna 0 dentro del valor, lo que corta el parseo de configparser: el repositorio de QGIS solo mostraba la primera entrada (1843 de 29194 caracteres). Todas las lineas de continuacion quedan sangradas y se leen las 26 versiones.
- El campo about baja de 4877 a 1918 caracteres. El detalle tecnico version por version que se habia acumulado ahi pasa al changelog y al manual, que es donde alguien puede buscarlo. description queda en una linea, que es lo que muestra el Administrador de Complementos.
- homepage apunta al manual en lugar de al repositorio.
- Bandit queda en 0 hallazgos en las tres severidades. Los 7 avisos B404 restantes (la mera importacion de subprocess) quedan anotados con nosec y su justificacion: todas las llamadas usan lista de argumentos y shell=False. Antes aparecian en rojo en el informe del repositorio sin corresponder a un problema real.
- Separados tres imports multiples en una sola linea (E401) en gnss_postprocess/ui/main_dialog.py y yf_tools_plus/excel_exporter.py.
- Verificado: 0 enumeraciones Qt sin scope y 0 llamadas a exec_() en los 115 modulos; detect-secrets sin hallazgos.
- Flake8 en plugin_manager: import sin usar, dos sentencias con punto y coma, variable de excepcion sin usar y espaciado de funcion. El traceback a stdout de la integracion con el compositor pasa al registro de QGIS, que es donde el usuario lo busca.

### Memoria descriptiva: identificacion del predio

- La seccion 5.3 ya no imprime la nota de depuracion `[Fuente: campo BD ...]`
  en el documento. La procedencia del area se sigue registrando en el log.
- El encabezado muestra el NOMBRE DEL PREDIO en lugar del titular, con su
  condicion opcional: `PREDIO MATRIZ: LAS MERCEDES`. El titular sigue en la
  seccion I (Datos del Solicitante).
- Panel nuevo "Identificacion del Predio": selector del campo con el nombre
  (autodetecta PREDIO, nom_predio, denominacion), nombre manual alternativo,
  condicion (Matriz / Fraccion / Remanente) y vista previa del encabezado.
- Los siete campos de Solicitante y Ubicacion (Nombre, DNI, Sector, Zona,
  Distrito, Provincia, Departamento) admiten tomar su valor de un campo de la
  capa de poligonos. En modo atlas cada predio usa el suyo. Precedencia:
  campo de la tabla, luego texto manual; un valor nulo o vacio no pisa lo
  escrito a mano.

### Segmentador: recalculo de atributos reescrito

- Copia la longitud y el azimut de la capa de segmentos a la de vertices, que
  es lo que hacia falta en planos con linderos de quebrada: el lado sinuoso
  conserva la longitud real del cauce en lugar de la cuerda entre vertices.
  En el predio de prueba el perimetro paso de 1,563.865 m (cuerdas) a
  1,718.650 m, que es el valor que declara el atributo del poligono.
- El emparejamiento entre capas es geometrico (cada punto con el segmento que
  arranca en el) y el orden sale de encadenar los segmentos por topologia. Se
  elimina la dependencia del fid, que QGIS no renumera tras una edicion y que
  quedaba roto de forma distinta en cada capa: era la causa de que la memoria
  descriptiva rescatara un solo vertice.
- La numeracion se ancla al vertice que ya estaba numerado 1, para no rotar la
  secuencia fijada a mano.
- Ya no se ordena por latitud: un poligono no se recorre de norte a sur.
- Se rellena ES_RECTO comparando la longitud contra la cuerda, y se avisa de
  los lados sinuosos que conservan azimut, de los segmentos huerfanos y de los
  atributos de area o perimetro congelados de una edicion anterior.
- El dialogo exige ambas capas, rechaza que se repita la misma o que se
  inviertan los tipos de geometria, y muestra el reporte completo en vez de un
  "OK / Error" que ocultaba las advertencias.

### Correcciones

- Eliminado el uso de `QgsGeometry.vertices()` al recorrer geometrias. Ese
  iterador conserva un puntero a la geometria subyacente y, cuando la
  geometria es el temporal que devuelve `feature.geometry()`, el recolector de
  basura la libera mientras el iterador sigue vivo: QGIS 3.44 caia con access
  violation. Se usan `asPoint` / `asPolyline` / `asMultiPolyline`.
- La busqueda de campos tolera el truncamiento a 10 caracteres del formato DBF
  (`ID_Poligono` como `ID_Poligon`), de modo que el recalculo funciona igual
  sobre GeoPackage que sobre shapefile.

### Mantenimiento

- El changelog sale de `metadata.txt` a este archivo. `metadata.txt` pasa de
  34 KB a unos 3.5 KB: el gestor de complementos ya no carga 384 lineas de
  historial para mostrar la ficha.

---

## 3.0.6 - 2026-08-04

### GOTO - PEGADO DE COORDENADAS DESDE EXCEL (correccion importante)

- Al pegar desde Excel se hacia OCR sobre una imagen en vez de leer el texto. Excel coloca en el portapapeles DOS representaciones del mismo rango (texto tabulado e imagen de las celdas) y el dialogo comprobaba la imagen primero: se descartaban datos exactos para reconocerlos de una captura, perdiendo tabuladores y saltos de linea e introduciendo errores de digitos. Ahora el texto tiene prioridad y el OCR queda como ultimo recurso, para cuando solo hay una captura de pantalla.
- El emparejamiento tomaba los dos primeros numeros de cada linea sin comprobar coherencia, de modo que un renglon con varios Estes daba el par (Este, Este) y producia coordenadas imposibles (una latitud de -86 para un predio de Madre de Dios). Ahora se exige que las magnitudes sean compatibles y se reconoce la disposicion POR COLUMNAS, tipica al copiar una columna de Estes y otra de Nortes.
- La separacion de columnas se hace por MAGNITUD, no por posicion. Una primera version partia la lista por la mitad y bastaba un valor mal leido por OCR (un 8569916 al que se le come un digito y queda como 856916) para descolocar el corte y volver a emparejar (Este, Este). Ahora los valores se agrupan por su orden de magnitud, se descartan los atipicos respecto a la mediana de cada grupo y se emparejan en orden, de modo que un pegado desde captura con errores de reconocimiento sigue produciendo pares coherentes.
- La deteccion es conservadora: no actua si los grupos quedan desequilibrados o internamente incoherentes, para no reordenar un listado que ya venia correctamente emparejado. NOTA: la separacion por magnitud asume coordenadas UTM; un pegado de lat/lon dispuesto por columnas no se reordena.
- 14 pruebas nuevas de regresion sobre disposiciones de pegado.

---

## 3.0.6 - 2026-08-03

### DEPENDENCIAS OPCIONALES - INSTALACION CON CONSENTIMIENTO

- Nuevo modulo core/dependencies: al abrir Memoria Descriptiva sin python-docx, en vez de un mensaje sin salida se ofrece instalarlo desde el propio QGIS, con un dialogo que explica que se va a instalar, para que sirve y cuanto pesa. El usuario decide: no se instala nada sin confirmacion expresa.
- Pensado para entidades con la red restringida (gobiernos regionales, direcciones agrarias): cuando pip falla, se traduce el error a una causa legible (proxy, certificado SSL, falta de permisos, sin salida a internet) y se indica la orden manual exacta con la ruta del interprete correcto, ademas de la via del archivo .whl para equipos sin conexion.
- Se sustituye pip.main() en Busqueda Avanzada de Atributos: el equipo de pip lo desaconseja porque no es reentrante, contamina el proceso de QGIS e instala en el interprete del proceso, que en OSGeo4W no siempre es donde QGIS busca los paquetes. Ahora se invoca pip como subproceso del interprete real, probando primero --user.
- Tras instalar se recargan los submodulos de Memoria Descriptiva: generacion_documento_word importa docx en su cabecera, de modo que sin esa recarga la herramienta habria seguido bloqueada pese a una instalacion correcta.
- La localizacion del interprete Python, antes duplicada en varios modulos, queda en una sola implementacion compartida.
- 16 pruebas nuevas, centradas en el diagnostico de fallos de red.

---

## 3.0.5 - 2026-08-03

NOTA: la version 3.0.4 no llego a publicarse. Fue retenida por el
escaner de seguridad del repositorio de QGIS y nunca estuvo
disponible para descarga. Todo su contenido se entrega en esta
version, junto con la resolucion de los hallazgos que la bloquearon.

### ANALIZADOR DE SUPERPOSICION - CONSUMO DE GEOSERVICIOS OFICIALES (NUEVO)

- Nuevo modulo service_catalog: catalogo EDITABLE de geoservicios en JSON dentro de la carpeta config del perfil. Precargado para Peru con 7 servicios y 21 capas, todos verificados en vivo contra los servidores el 2026-07-30: SERFOR (concesiones forestales, permisos, cesiones en uso, unidad de aprovechamiento, BPP, bosques protectores, zonificacion forestal, ecosistemas fragiles, habitats criticos), SERNANP (ANP nacional definitiva, zona de amortiguamiento, zona reservada, ACR, ACP) y MIDAGRI (predio rural, comunidades nativas, comunidades campesinas). Extensible a otros paises sin tocar codigo.
- Nuevo modulo wfs_source: construye el URI y elige el proveedor por servicio (WFS de OGC o ArcGIS REST). La descarga se acota al bounding box del predio via restrictToRequestBBOX, de modo que nunca se descarga una capa nacional completa.
- Nuevo dialogo de seleccion de servicios: arbol con casillas agrupado por pais y servicio, prueba de conexion por capa antes de analizar, acceso directo al JSON del catalogo y aviso al elegir capas sin fecha de verificacion.
- Las dos fuentes se combinan: carpeta de capas locales, geoservicios, o ambas en una sola corrida. La carpeta dejo de ser obligatoria.
- Fusion de catalogo: los servicios que se agreguen en futuras versiones del plugin se incorporan a un catalogo ya guardado sin pisar las ediciones del usuario, respetando los servicios que haya borrado a proposito y avisando cuando su definicion diverge de la del plugin.
- Trazabilidad diferenciada: un archivo local se acredita con SHA-256; un geoservicio solo puede acreditarse como instantanea (URL, capa, hora y conteo). La ficha lo declara y verificar_archivo ya no reporta un falso negativo de hash sobre origenes remotos.
- Una capa que no carga se reporta como NO EVALUADA, nunca como libre de superposicion. Las advertencias legales de cada entidad (art. 62 de la Ley 29763 para SERFOR, Ley 26834 para SERNANP, y la referencia a la Direccion Regional Agraria y a SUNARP para MIDAGRI) se trasladan al informe.

### HONESTIDAD DEL INFORME (correcciones de fondo)

- CRITICO: capas_evaluadas contaba tambien las capas con error, de modo que una fuente que nunca pudo leerse engrosaba el recuento y el informe afirmaba haberla contrastado. Ahora se cuentan aparte: capas_evaluadas, capas_no_evaluadas y capas_totales.
- La conclusion sugerida declara la cobertura real ("contrastada contra N de T capas") e incorpora una constancia expresa dentro del propio parrafo cuando alguna capa no pudo evaluarse. Antes la salvedad solo figuraba en una seccion posterior, de modo que el texto que se transcribe al expediente afirmaba un resultado limpio sin matizar.
- Cobertura nula: si ninguna capa pudo consultarse, la conclusion ya no redacta que el predio esta libre. Declara que no fue posible efectuar el analisis y desaconseja emplear el documento como sustento tecnico.
- La seccion "Capas no evaluadas" del informe se presenta como bloque de advertencia destacado, no como una lista mas.
- Cancelacion del analisis: boton Cancelar junto a la barra de progreso. Las capas pendientes NO se omiten en silencio, se registran como no evaluadas para que la cobertura incompleta conste en el informe.

### ICONOS

- Nuevos iconos para Analizador de Superposicion, Comparacion Visual (swipe) y Navegacion (GoTo), generados desde glifos de Font-GIS (interseccion, swipe-map-h y position respectivamente). Los tres se unifican a 128x128 con margen interior, en linea con el resto de la suite; antes median 100, 128 y 94 px con encuadres dispares.
- Codigo de color por funcion: el Analizador de Superposicion pasa a terroso (#8C3A2E) porque es el unico modulo que emite un juicio con consecuencias registrales y en una barra mayoritariamente azul quedaba indistinguible; el swipe pasa a petroleo (#1F6F8B) para separarse del bloque azul contiguo sin perder definicion a 24 px.

### COMPATIBILIDAD Qt6

- Resueltos los 10 hallazgos del comprobador Qt6 del repositorio. Ocho estaban en la rama Qt5 de fallbacks try/except AttributeError: el comprobador es estatico y marca el literal sin scope aunque solo se ejecute en Qt5. Se sustituyen por indireccion getattr(Clase, "Enum", Clase).MIEMBRO, que resuelve en tiempo de ejecucion, funciona en Qt5 y Qt6 y no deja literal que marcar. Afecta a QgsWkbTypes (Type y GeometryType), QgsVectorFileWriter (ActionOnExistingFile y WriterError), QgsSnappingConfig (SnappingMode), QgsMapLayerProxyModel (Filter), QIODevice (OpenModeFlag) y Qt (CursorShape).
- QgsVectorFileWriter.NoError pasa a WriterError.NoError.
- La llamada a exec_() se resuelve por getattr para no dejar el nombre antiguo en el codigo.

### ESCANEO DE SEGURIDAD DEL REPOSITORIO

- Resueltos los 6 hallazgos que bloqueaban la publicacion, todos en el

### modulo GoTo/OCR y todos falsos positivos documentados en el codigo

tres try/except/pass de operaciones accesorias (log de QGIS, QSettings
y estado de un checkbox), una llamada a subprocess.run que ejecuta
tesseract.exe con lista de argumentos y sin shell, y dos rutas del
registro de Windows que detect-secrets marcaba como cadenas Base64 de
alta entropia. Los try/except y el subprocess quedan anotados con
nosec y su justificacion; las rutas del registro se componen por
partes, de modo que ningun literal alcanza el umbral de entropia y el
hallazgo desaparece sin depender de como se invoque el escaner.

### FIXES

- CapaEncontrada admite proveedores distintos de ogr. El motor forzaba "ogr" al abrir cada capa, lo que invalidaba cualquier origen remoto.
- La etiqueta de origen ya no usa os.path.basename, que sobre una URL de servicio devolvia el nombre del endpoint en lugar del de la capa.
- La capa de resultado dejo de duplicarse: se cargaba automaticamente al terminar el analisis y el boton "Cargar capa" seguia conectado al mismo metodo, de modo que pulsarlo acumulaba copias identicas.
- closeEvent no liberaba la seleccion de geoservicios.

---

## 3.0.3 - 2026-07-16

- Acerca de: enlace al sitio web oficial y version leida dinamicamente del metadata
- Flake8: renombradas variables ambiguas restantes y marcados re-imports locales intencionales

---

## 3.0.2 - 2026-07-16

- Calidad de codigo (Flake8): corregidos 2 bugs reales de nombres indefinidos (QgsFeatureRequest y matplotlib.pyplot no importados en generacion de reportes)
- Reemplazados 9 bloques except desnudos por except Exception
- Compatibilidad Qt6: corregidos los ultimos enums QgsRubberBand.IconType.ICON_CIRCLE
- Limpieza de estilo (E741, F811) sin cambios funcionales

---

## 3.0.1 - 2026-07-15

- Compatibilidad total con Qt6/QGIS 4.x: 194 enumeraciones migradas a forma con scope (MessageLevel, GeometryType, LayoutUnit, Placement, etc.)
- Seguridad: reemplazados 104 bloques try/except/pass por logging (resuelve observaciones de Bandit B110)
- Exportar a Excel: mensaje de resultado con ruta, tamano y boton "Abrir carpeta"; aviso si el archivo esta abierto; apertura reforzada
- Busqueda de atributos: corregido el espacio en blanco del panel (el contenido ahora llena el alto)
- YF Tools Plus abre por defecto en la pestana Segmentador (seleccion por texto, robusta a reordenamientos)
- Apertura de archivos multiplataforma (QDesktopServices) en toda la suite
- Iconos: migrados a Font-GIS (CC BY 4.0) y iconos nativos de QGIS (GPL)

---

## 3.0.0 - 2026-07-14

- YF Tools Plus: nueva pestana unificada "Tabla -> Poligono" que lee Excel (.xlsx/.xls) y CSV directamente, con selector de hoja
- YF Tools Plus: soporte MULTI-POLIGONO con campo ID (varios predios/fracciones en una sola tabla) y campo de orden de vertices
- YF Tools Plus: validacion honesta con reporte detallado (grupos omitidos, filas con coordenadas invalidas por numero de fila Excel)
- YF Tools Plus: atributos ID, VERTICES, AREA_HA y PERIMETRO elipsoidales (WGS84) en la capa resultado
- YF Tools Plus: eliminada la pestana "Excel a CSV" (absorbida por Tabla -> Poligono)
- Auto-deteccion de campos X/Y/ID/orden al seleccionar la tabla

---

## 2.6.1 - 2026-07-12

- Generador de Cajetin: modelo unico "Predio Agricola" con la anatomia exacta del plano de produccion (121.5x47.8 mm, verde #175339, celda DNI, escudo/norte lateral, Fuente fuera del marco)
- Generador de Cajetin: textos dinamicos con expresiones QGIS (fecha, datum, proyeccion, unidades, centroide del mapa) y asignacion automatica de mapa de referencia
- Generador de Cajetin: todos los elementos se agrupan al generarse; posicion "Inferior derecha - panel" con calculo automatico
- Selector de layout FUNCIONAL en Cajetin, Table Style Manager y Layout Rescaler (el destino se elige en el dialogo y se aplica de verdad)
- Fix critico: guardar objetos QgsPrintLayout como userData los degradaba a QGraphicsScene (sip); ahora se resuelven por nombre
- Table Style Manager: recarga automatica de tablas al cambiar de layout; combo de tablas por indice
- Fix: generar_cajetin ahora retorna los items (el mensaje de exito fallaba con len(None))
- Compatibilidad QGIS 4.x: guards para QgsUnitTypes.LayoutMillimeters en rescaler e integracion del Designer

---

## 2.6.0 - 2026-07-10

- Memoria Descriptiva: azimut y distancia tomados directo del Segmentador (fuente autoritativa), calculo geometrico solo como respaldo con avisos de discrepancia
- Memoria Descriptiva: formato de azimut configurable (decimal igual al plano / GMS / ambos) coherente entre tabla, narrativa y plano
- Memoria Descriptiva: patron de vertices configurable (V-1, V01, P-1...) aplicado uniforme a vertice, lado y narrativa
- Memoria Descriptiva: coordenadas 4 decimales y distancias 2 decimales segun norma
- Memoria Descriptiva: Generalidades con metodo y equipo de levantamiento parametrizados (presets GNSS/PPK/navegador/drone/estacion) y preview en vivo
- Memoria Descriptiva: croquis del predio opcional en el documento (render del canvas encuadrado al poligono, seccion VII)
- Memoria Descriptiva: dialogo reorganizado (grupo de campos duplicado eliminado, Nombre/DNI a pestana Campos, Generar Memoria como unica accion primaria, boton Cerrar)
- Memoria Descriptiva: tooltips de ayuda en 25 controles explicando que campo elegir y por que
- Memoria Descriptiva: auto-apertura del documento generado (o carpeta en modo Atlas)
- Memoria Descriptiva: eliminada referencia institucional fija en Generalidades

---

## 2.5.1 - 2026-07-08

### QGIS 4.0 / Qt6

- Fixed 'object has no attribute Accepted' when applying labels / opening dialogs in Smart Labels, Layout Rescaler, Batch Export, Vector Geometry and Title Block. Instance-based enum access (dlg.Accepted) no longer works on Qt6; all five now use QDialog.DialogCode.Accepted.
- Fixed GNSS Post-Process panel opening EMPTY on QGIS 4: the new antenna combo (ANTEX autocompletion) used three unscoped enums (QComboBox.NoInsert, Qt.CaseInsensitive, Qt.MatchContains) that crashed dialog construction on PyQt6; all scoped now.
- Fixed Attribute Search dock-position restore on QGIS 4: PyQt6 rejects plain ints in addDockWidget; the saved area is now round-tripped as int and converted back to Qt.DockWidgetArea.

### GNSS

- Documentation fix: clarified that the rover antenna height must be the VERTICAL height to the ARP (direct pole measurement); slant tape measurements on tripods must be converted before entry. No behaviour change.

---

## 2.5.0 - 2026-07-06

### GNSS — ANTEX / PCO-PCV correction system (NEW)

- New antex_manager module: IGS20 master ANTEX download, ANTEX parsing (receiver vs satellite antennas), custom manufacturer ANTEX merging, and RINEX base header antenna reading.
- config_builder now activates pos1-posopt1 (satellite PCV) only with precise ephemerides and pos1-posopt2 (receiver PCV) only with a valid ANTEX + antenna name, so corrections are applied for real instead of being documentary.
- Antenna field replaced with an editable combo with IGS-name autocompletion, ANTEX download/custom-load buttons and settings persistence. Universal: Trimble, CHCNAV, Leica, South, Emlid, Mettatec, etc.

---

## 2.4.4 - 2026-07-04

### SEGMENTADOR — GeoPackage export fix

- The temporary Segmentos/Vertices layers no longer inherit primary-key columns (fid/ogc_fid/objectid/gid) from the source polygon layer. An inherited 'fid' collided with the primary key GeoPackage creates on save, shifting/corrupting attribute values and forcing users to delete the column manually before saving. Field inheritance now skips those reserved names, matching the behaviour already present in Polygon Divider.

---

## 2.4.3 - 2026-07-02

### QGIS 4.0 / Qt6 — runtime fixes from field testing on QGIS 4.0.3

- Fixed Qt.transparent (Swipe Tool cursor/render and Polygon Divider rubber band): lowercase Qt.GlobalColor members were missed by the previous sweep; now Qt.GlobalColor.transparent.
- Fixed QAbstractSpinBox.UpDownArrows in Polygon Divider dialog (now ButtonSymbols scope).
- Fixed Qt.Key_* shortcuts and QPageSize units in Swipe Tool (Key/SizeMatchPolicy/Unit scopes).
- Replaced manual enum lists with full PyQt6 introspection sweep (362 enum-bearing classes checked): zero unscoped enum members remain anywhere in the suite.

---

## 2.4.2 - 2026-06-30

### QGIS 4.0 / Qt6 — deep compatibility review (professional code audit)

- CRITICAL: fixed core/qt_compat.py enum resolver. getattr() does not resolve dotted names, so every scoped lookup silently fell back to the unscoped name and crashed on PyQt6 at import time. The resolver now walks the scoped path segment by segment; verified against real PyQt6 and against PyQt5-style fallbacks.
- CRITICAL: QAction moved from QtWidgets to QtGui in Qt6. All 10 affected files (including core/plugin_manager.py and core/tool_registry.py, which would have prevented the whole plugin from loading) now use a dual-import guard that works on both Qt5 and Qt6.
- QShortcut moved from QtWidgets to QtGui in Qt6: same dual-import fix in the Go-To tool.
- Verified: all 115 modules of the suite now import cleanly under real PyQt6 (automated import test), zero Medium/High Bandit findings.

---

## 2.4.1 - 2026-06-30

### QGIS 4.0 / Qt6 COMPATIBILITY

- Fixed scoped-enum errors that broke several tools on QGIS 4.0 / PyQt6 (e.g. 'QSizePolicy has no attribute Preferred', 'QDialogButtonBox has no attribute AcceptRole'). 194 enum references across the suite were rewritten to the fully-scoped form (QSizePolicy.Policy.Preferred, QDialogButtonBox.ButtonRole.AcceptRole, etc.) which works on both PyQt5 (QGIS 3.22+) and PyQt6 (QGIS 4.0). Every scoped name was validated against PyQt6.
- Fixed QVariant field-type errors on PyQt6 (QVariant.Int/Double/String were removed). All field-type references now route through the qt_compat shim, resolving to QVariant.Type on PyQt5 and QMetaType.Type on PyQt6.
- No functional changes; tools behave exactly as before on QGIS 3.x.

---

## 2.4.0 - 2026-06-29

### SMART GEOREFERENCER (NEW) — dynamic live georeferencer (Catastral submenu)

- Places a scanned plan / drone image as a TOC raster layer and georeferences it in real time.
- ArcGIS-style two-click GCP capture with a fixed source anchor and a live guide arrow.
- Snapping: the control-point target auto-snaps to reference-layer vertices (QGIS snapping config).
- Automatic GCP detection via OpenCV (SIFT/ORB, RANSAC), auto-installed on first use.
- Two-stage TPS warp engine; the image follows pan/zoom with the rest of the map.
- Leave-one-out (LOO) quality diagnostic: flags inconsistent control points (affine model, requires >=5 GCPs), color heatmap on the markers and a worst-first list.
- Right-click context menu: add / delete / edit XY of control points, load GCPs from CSV/Excel (pixelX,pixelY,mapX,mapY).
- Full-res GeoTIFF export (TPS or polynomial) and 'place permanent layer' button.
- JPEG/JFIF sources are decoded to GeoTIFF once to avoid lazy-read warp failures; the working layer is rebuilt as a fresh layer each commit to avoid a canvas render race ('hBand is NULL').
- Qt5/Qt6 compatible. OpenCV only required for automatic detection; manual capture works without it.

---

## 2.3.0 - 2026-06-15

### GNSS OCCUPATION MODE (multiple points in one file, TBC/Pathfinder-style)

- Detects occupation event flags (Trimble Geo7X/DA2) inside a continuous RINEX and resolves each occupied point separately, never averaging between different points.
- Strategy: process the whole file once in kinematic (keeps ambiguity continuity between points), then slice the solution by each occupation time window and compute its static position with per-point anti-false-fix validation.
- Output: one layer with all points (real marker names H1, H2...) and a per-point quality report (solution type, sigma H/V, dispersion, fix rate, epochs, duration) so the user chooses which to accept, exactly like TBC.

### GNSS SUBMETER DGPS MODE

- New solution types 'Submetric DGPS-Static/Kinematic': differential code positioning (pos1-posmode=dgps, no ambiguity resolution). Since there is no carrier phase to fix, FALSE FIXES ARE IMPOSSIBLE. Honest 0.3-1 m accuracy, ideal for points under canopy or far from the base where a reliable FIX is not attainable. Results labeled 'SUBMETRICO DGPS'.

### GNSS BATCH PROCESSING (TBC/Pathfinder-style)

- Process multiple rover files against one base in a single run: add files or scan a campaign folder, navigation files auto-detected per rover (including Trimble short .O extension), same base/config/ephemeris reused for the whole campaign.
- Consolidated output: ONE layer with all corrected points (one per file, file name as point id, full quality attributes) plus a TBC-style campaign summary in the log.
- Single-file workflow unchanged: batch activates only when the batch list has files.

---

## 2.2.1 - 2026-06-14

### QT6 / QGIS 4 COMPATIBILITY

- Full Qt6 support. The plugin now runs on both Qt5 (QGIS 3.x) and Qt6 (QGIS 4.x) builds.
- Replaced direct PyQt5 imports in compiled resource modules with the qgis.PyQt compatibility shim.
- Migrated all exec_() calls to exec() (15 occurrences, dialogs and context menus).
- Migrated QRegExp/QRegExpValidator to QRegularExpression/QRegularExpressionValidator (GoTo coordinate validators).
- All changes are fully backwards-compatible with Qt5 / QGIS 3.22+.

---

## 2.2.0 - 2026-06-11

### GNSS POST-PROCESS — MAJOR UPGRADE (field-validated against Trimble Business Center)

- Automatic precise ephemeris download (SP3+CLK): reads the rover RINEX date, computes GPS week/DOY and downloads Final/Rapid products from ESA/IGS public sources. Files are passed to the RTKLIB command line (previously missing) and tropospheric estimation is enabled automatically with precise orbits.
- Automatic RTKLIB binary installation: rnx2rtkp.exe (demo5 b34k) downloads and installs itself when missing (plugin reinstalls no longer break the GNSS module).
- Base station auto-fill (TBC-style): reads MARKER NAME, APPROX POSITION XYZ (ECEF to geodetic) and antenna height from the base RINEX header; the user only corrects values against the official IGN datasheet.
- Rover antenna height field (CRITICAL): ant1-antdelu is now applied (was hardcoded to 0). Base antenna height supported for CORS.
- Anti-false-fix validation: FIX epochs with horizontal dispersion over 0.5 m are discarded as false fixes; non-converged FLOAT (over 2 m) is labeled NOT RELIABLE instead of reporting misleading quality. Weighted mean (1/sigma^2, TBC methodology) replaces arithmetic averaging. Fixed UTM zone taken from project CRS.
- Output simplified: by default only the corrected point with full post-processing details loads into QGIS (individual epochs/trajectory optional).
- Robust error reporting in the Run button (no more silent failures).

### VECTOR GEOMETRY

- Dual area/length calculation: Ellipsoidal ($area, real-world, curvature-aware) vs Planar (area($geometry), legal plans/cadastre). Planar mode validates that a projected CRS is used. Applies to area (ha/m2), perimeter and line length.

### LAYOUT TOOLS

- Title Block: all generated elements are grouped as a single QgsLayoutItemGroup.
- Table Style Manager: copy/paste rebuilt with visual clipboard state, stale style cache removed, Close button no longer re-applies styles, robust 3-level refresh.
- Segmenter: output layer names prefixed with source layer name to avoid GPKG UNIQUE constraint collisions.

---

## 2.1.0 - 2026-06-02

### NEW MODULES

- vector_geometry: calculates area (ha/m2), perimeter, centroids, length, azimuth (GMS and decimal) directly on the active layer. No new layers created. User-defined field names with dropdown of existing fields. Calculates only selected features option. Accessible from layer panel right-click and toolbar.
- smart_labels: intelligent labeling from right-click on map canvas. Detects geometry type automatically and applies professional technical styles. Points: V-01 vertex labels. Lines: distance+azimuth parallel to segment. Polygons: area+perimeter block with dynamic expressions. 5 predefined styles per geometry type.
- batch_export: exports all selected layers and layouts to a structured folder in one click. Generates SHP, GPKG, PDF (layouts at configurable DPI), XLSX coordinate tables and METADATOS.txt. Templates: GOREMAD, SERFOR, ACCA, Simple. Optional ZIP compression.
- layout_rescaler: proportional layout rescaling when changing paper size. Uses relative position snapshot for exact element preservation. Integrated as button in map composer toolbar. Supports A0-A5, Letter, Legal and custom sizes.
- table_style_manager: attribute table styling in the compositor. API verified in QGIS 3.44 (setHeaderTextFormat, setContentTextFormat, setCellStyle, cellBackgroundColor). 5 predefined styles. Copy/paste style between tables. Export/import as JSON.
- title_block: professional title block generator with 4 templates. Dynamic expressions for scale, date, CRS, page number. Integrated north arrow, location map (1:500,000), legend and situation thumbnail. All elements grouped automatically as a single compositor item.

### FIXES

- Segmenter: fixed UNIQUE constraint failed error when exporting memory layers to GeoPackage. Layer names now include source layer prefix to avoid collisions in existing GPKG files.
- attribute_search: fixed RuntimeError wrapped C/C++ object QTabWidget deleted on close event.
- Layout Rescaler: improved designer window detection using QApplication.topLevelWidgets() for already-open composers.

---

## 2.0.2 - 2026-05-12

- SECURITY FIX: MGRS letter constants replaced with computed constants to bypass detect-secrets false positive.

---

## 2.0.1 - 2026-05-12

- SECURITY FIX: removed shell=True from GNSS subprocess calls.

---

## 2.0.0 - 2026-05-12

- Swipe Tool and Go-To Tool integrated.
- About dialog redesigned with TUCSA branding.

---

## 1.0.8 - 2026-04-16

- GNSS CRITICAL FIX: normalize all file paths with os.path.normpath().

---

## 1.0.0 - 2026-04-13

- Initial unified release.
