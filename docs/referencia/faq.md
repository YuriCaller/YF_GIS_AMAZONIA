# Preguntas frecuentes

## Instalación

**¿Necesito permisos de administrador?**
No. Ni el plugin ni sus componentes opcionales los requieren.

**¿Funciona en QGIS 4?**
Sí. La suite es compatible con Qt5 (QGIS 3.22+) y Qt6 (QGIS 4.x).

**¿Funciona en Linux o macOS?**
Sí, salvo el [post-proceso GNSS](../herramientas/gnss_postprocess.md), que usa binarios de RTKLIB para Windows.

**Instalé python-docx y la herramienta sigue bloqueada.**
Es el problema más reportado y tiene página propia: [componentes opcionales](../instalacion/dependencias.md). Casi siempre el paquete quedó en un Python distinto del que usa QGIS.

## Uso

**¿Por qué mis áreas no coinciden con el plano?**
Dos causas habituales. Primera, el proyecto está en coordenadas geográficas: use un CRS proyectado (EPSG:32719 para Madre de Dios). Segunda, el plano usa área plana y usted calculó elipsoidal, o al revés — vea [Calculadora de Geometría Vectorial](../herramientas/vector_geometry.md).

**¿Qué CRS debo usar en Madre de Dios?**
EPSG:32719 (UTM zona 19 sur, WGS84).

**¿El informe de superposición sirve como certificado?**
No. Es un insumo técnico. La información oficial y oponible la emiten SERFOR, SERNANP, la Dirección Regional Agraria y SUNARP.

**Una capa aparece como «no evaluada». ¿Es un error?**
No, es el comportamiento correcto. Significa que esa capa no pudo leerse y por tanto **no se verificó**. Nunca interprete un predio con capas sin evaluar como libre de superposición.

## Datos y privacidad

**¿El plugin envía mis datos a algún sitio?**
No. Las únicas conexiones salientes son: la consulta a los geoservicios oficiales que usted elija, la descarga de componentes opcionales desde PyPI si la autoriza, la descarga de RTKLIB y las efemérides al usar GNSS, y la apertura del manual en su navegador.

**¿Dónde se guarda el catálogo de geoservicios?**
En la carpeta `config` de su perfil de QGIS. Es suyo y editable.

## Contribuir

**Encontré un error.**
Repórtelo en [GitHub](https://github.com/YuriCaller/YF_GIS_AMAZONIA/issues). Adjunte el texto de **Acerca de → Diagnóstico**: ahorra la mitad de las preguntas de ida y vuelta.

**¿Puedo añadir geoservicios de mi país?**
Sí, sin tocar código. Vea [geoservicios oficiales](geoservicios.md).
