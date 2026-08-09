# Historial de versiones

El historial completo y detallado está en el archivo `metadata.txt` del plugin y en [las versiones publicadas en GitHub](https://github.com/YuriCaller/YF_GIS_AMAZONIA/releases). Aquí se resumen los cambios que afectan a cómo se usa la suite.

## 3.0.7

- **Manual de usuario en línea**, accesible desde el diálogo «Acerca de» y desde cada herramienta.
- **Instalación de componentes opcionales rehecha.** Ahora se instalan en el perfil de QGIS con `--target`, en vez de `--user`. Resuelve el fallo más reportado: `pip` informaba *Successfully installed* y la herramienta seguía bloqueada porque el paquete quedaba en un Python que QGIS no lee. Se añade instalación desde archivo `.whl` para equipos sin internet, reutilización automática del proxy configurado en QGIS y un botón de **Diagnóstico**.
- **«Acerca de» rehecho.** Anunciaba 8 herramientas de 17 y mantenía etiquetas «nuevo v2.0» un año después. La lista se genera ahora desde un catálogo único, con enlace al manual por herramienta.

## 3.0.6

- **Pegado de coordenadas desde Excel en Go-To.** Se hacía OCR sobre la imagen del rango en vez de leer el texto, perdiendo precisión. Ahora el texto tiene prioridad. Se corrigió además el emparejamiento, que podía producir pares (Este, Este) y coordenadas imposibles.
- **Instalación de dependencias con consentimiento**, con diagnóstico legible de los fallos de red.

## 3.0.5

- **Analizador de Superposición**: consumo de geoservicios oficiales (SERFOR, SERNANP, MIDAGRI) vía WFS y ArcGIS REST, con catálogo editable.
- **Honestidad del informe**: las capas con error ya no se contaban como evaluadas. La conclusión declara la cobertura real y no afirma que un predio esté libre cuando no pudo verificarlo.
- Iconos unificados y compatibilidad Qt6 completa.

## 3.0.0 – 3.0.3

- **YF Tools Plus**: pestaña Tabla → Polígono, que lee Excel y CSV con soporte multipolígono.
- Compatibilidad total con QGIS 4.x / Qt6.

## 2.x

- **2.6.1** — Generador de Cajetín con modelo Predio Agrícola y selector de layout funcional.
- **2.6.0** — Memoria Descriptiva: azimut tomado del Segmentador como fuente autoritativa, formato configurable, croquis opcional.
- **2.5.0** — GNSS: sistema ANTEX con corrección PCO/PCV.
- **2.4.0** — Georreferenciador Inteligente.
- **2.3.0** — Divisor de Polígonos. GNSS: ocupaciones múltiples, DGPS submétrico y procesamiento por lotes.
- **2.2.0** — GNSS: efemérides precisas automáticas, autocompletado de base, validación antifalso-fix.
- **2.1.0** — Geometría Vectorial, Etiquetado Técnico, Exportar Expediente, herramientas de compositor.
- **2.0.0** — Swipe y Go-To.

## 1.0.0

Primera versión unificada (abril de 2026).
