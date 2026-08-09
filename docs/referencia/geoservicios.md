# Geoservicios oficiales

Catálogo precargado en el [Analizador de Superposición](../herramientas/superposition.md), verificado en vivo contra los servidores el **30 de julio de 2026**.

!!! warning "Las URL de los servicios cambian"
    Los servidores institucionales se reorganizan sin aviso. Si una capa deja de responder, use **Probar conexión** en el diálogo de selección y, si hace falta, corrija la URL en el archivo del catálogo. Las correcciones que haga se conservan al actualizar el plugin.

## Perú

| Entidad | Capas | Marco legal aplicable |
|---|---|---|
| **SERFOR** | Concesiones forestales, permisos, cesiones en uso, unidad de aprovechamiento, BPP, bosques protectores, zonificación forestal, ecosistemas frágiles, hábitats críticos | Ley 29763, art. 62 |
| **SERNANP** | ANP nacional definitiva, zona de amortiguamiento, zona reservada, ACR, ACP | Ley 26834 |
| **MIDAGRI** | Predio rural, comunidades nativas, comunidades campesinas | Remisión a la Dirección Regional Agraria y a SUNARP |

Siete servicios, veintiuna capas.

## Dónde está el catálogo

Un archivo JSON en la carpeta `config` de su perfil de QGIS. Se abre desde el botón correspondiente del diálogo de selección de servicios.

## Añadir servicios propios

La estructura declara, por servicio: el tipo de proveedor (`wfs` para OGC WFS, `arcgisfeatureserver` para ArcGIS REST), la URL base y la lista de capas con su nombre e identificador.

No hace falta tocar código. Un usuario de Colombia, Bolivia o Ecuador puede construir su catálogo nacional del mismo modo.

## Qué ocurre al actualizar el plugin

Los servicios nuevos que traiga una versión se **fusionan** con el catálogo guardado:

- No se sobrescriben sus ediciones.
- Se respetan los servicios que haya borrado a propósito.
- Si la definición de un servicio diverge de la del plugin, se le avisa en vez de reemplazarla.

## Limitaciones

**Las descargas se acotan al predio.** La consulta se restringe al *bounding box* de la parcela. Sin esa restricción, consultar el catastro rural para un predio de 40 ha traería millones de entidades.

**Un geoservicio no se acredita como un archivo.** Vea [cómo leer el informe](../herramientas/superposition.md#trazabilidad-archivo-local-frente-a-geoservicio).

**La disponibilidad no está garantizada.** Son servidores de terceros. Una capa que no responde se reporta como **no evaluada**, nunca como libre de superposición.
