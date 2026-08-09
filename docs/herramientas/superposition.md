# Análisis de Superposición de Derechos

Contrasta un predio contra derechos preexistentes y áreas naturales protegidas, y emite un informe con el área superpuesta en hectáreas, el porcentaje del predio afectado y un nivel de severidad.

*Disponible desde la versión 3.0.5 · Menú `Búsqueda y Análisis`*

---

## Para qué sirve

Antes de tramitar una titulación, una concesión o un cambio de uso, hay que verificar que el predio no invade un derecho ya otorgado ni un área protegida. Hacerlo a mano significa descargar capas de varias entidades, reproyectarlas, intersecarlas una por una y redactar el resultado — un trabajo de horas que se repite en cada expediente y en el que un descuido puede sostener una conclusión falsa.

Esta herramienta hace ese contraste en una corrida y produce un informe que **declara explícitamente qué pudo verificar y qué no**.

!!! danger "Sobre el valor legal del informe"
    El informe es un **insumo técnico**, no un certificado. La información oficial y oponible sobre derechos otorgados la emiten las entidades competentes (SERFOR, SERNANP, la Dirección Regional Agraria, SUNARP). Un resultado sin superposición no sustituye la consulta formal ante esas entidades.

---

## Antes de empezar

- Una **capa vectorial con el predio** a evaluar, cargada en el proyecto. Un solo polígono o varios.
- Un **CRS proyectado** en el proyecto (para Madre de Dios, EPSG:32719 — UTM 19S / WGS84). En coordenadas geográficas el cálculo de áreas no es fiable.
- Para consultar geoservicios, **conexión a internet**. Para capas locales, no hace falta.

---

## Cómo se usa

### 1. Elegir el predio

Seleccione la capa y, si lo necesita, la entidad concreta. Si hay entidades seleccionadas en el lienzo, la herramienta ofrece limitarse a ellas.

### 2. Elegir las fuentes de contraste

Puede combinar dos orígenes en una misma corrida:

=== "Geoservicios oficiales"

    Pulse **Seleccionar geoservicios**. Se abre un árbol agrupado por país y entidad, con casillas por capa.

    El catálogo viene precargado y verificado para Perú, con siete servicios y veintiuna capas:

    - **SERFOR** — concesiones forestales, permisos, cesiones en uso, unidades de aprovechamiento, BPP, bosques protectores, zonificación forestal, ecosistemas frágiles, hábitats críticos
    - **SERNANP** — ANP nacionales definitivas, zonas de amortiguamiento, zonas reservadas, ACR, ACP
    - **MIDAGRI** — predio rural, comunidades nativas, comunidades campesinas

    El botón **Probar conexión** verifica cada capa antes de lanzar el análisis. Conviene usarlo: los servidores institucionales tienen caídas, y es mejor saberlo antes que a mitad de una corrida larga.

=== "Capas locales"

    Indique una carpeta con archivos vectoriales (`.shp`, `.gpkg`...). La herramienta los recorre y evalúa todos los que puedan leerse.

    Es la vía cuando trabaja con información entregada en mesa de partes, con una descarga previa o sin internet.

=== "Ambas a la vez"

    Nada impide combinarlas: por ejemplo, geoservicios de SERNANP más una capa local de catastro entregada por la Dirección Regional Agraria. El informe distingue el origen de cada resultado.

### 3. Ejecutar

Pulse **Analizar**. La barra de progreso indica la capa en curso y el botón **Cancelar** detiene el proceso.

!!! note "Cancelar no falsea el resultado"
    Si cancela, las capas pendientes se registran como **no evaluadas** y así constan en el informe. Nunca se omiten en silencio, porque eso produciría un informe que aparenta una cobertura que no tuvo.

---

## Qué produce

### Capa de resultado

Un polígono por cada superposición encontrada, con el área en hectáreas, el porcentaje del predio, la capa de origen y el nivel de severidad.

### Informe

En formato Word y HTML, con:

- **Ficha del predio** — identificación, área, CRS, vértices
- **Resultados por capa** — superposición encontrada o ausencia de ella
- **Capas no evaluadas** — bloque de advertencia destacado, cuando las haya
- **Trazabilidad de fuentes** — ver más abajo
- **Conclusión sugerida** — redactada para transcribirse al expediente
- **Advertencias legales** de cada entidad: artículo 62 de la Ley 29763 para SERFOR, Ley 26834 para SERNANP, y la remisión a la Dirección Regional Agraria y a SUNARP para MIDAGRI

---

## Cómo leer el informe

Tres puntos que conviene entender bien, porque determinan qué puede afirmar con el documento en la mano.

### Cobertura real

La conclusión declara *«contrastada contra N de T capas»*. Si N es menor que T, **el análisis está incompleto** y la salvedad aparece dentro del propio párrafo de conclusión, no en una sección aparte.

Esto se corrigió en la versión 3.0.5. Antes, las capas con error engrosaban el recuento de evaluadas: el informe afirmaba haber contrastado una fuente que en realidad nunca pudo leerse, y la conclusión que se transcribía al expediente sonaba limpia sin matizar nada.

### Cobertura nula

Si ninguna capa pudo consultarse, la conclusión **no dice que el predio esté libre**. Declara que no fue posible efectuar el análisis y desaconseja emplear el documento como sustento técnico.

### Trazabilidad: archivo local frente a geoservicio

No son equivalentes y el informe lo dice con todas sus letras:

| | Cómo se acredita | Se puede re-verificar |
|---|---|---|
| **Archivo local** | Huella SHA-256 del archivo | Sí. La huella prueba que es el mismo archivo |
| **Geoservicio** | Instantánea: URL, capa, fecha, hora y conteo de entidades | No de la misma forma. El servidor pudo cambiar |

Un geoservicio solo puede acreditarse como una fotografía del momento. Si el expediente exige poder demostrar más adelante contra qué exactamente se contrastó, **descargue la capa, guárdela y evalúela como archivo local**.

---

## El catálogo de geoservicios

El catálogo es un archivo JSON editable dentro de la carpeta `config` de su perfil de QGIS. Se abre desde el propio diálogo de selección de servicios.

**Puede añadir sus propios servicios sin tocar código.** La estructura declara, por servicio, el tipo de proveedor (OGC WFS o ArcGIS REST), la URL base y las capas disponibles. Un usuario de Colombia o Bolivia puede armar su propio catálogo nacional del mismo modo.

**Sus ediciones se respetan al actualizar.** Los servicios nuevos que lleguen con futuras versiones del plugin se incorporan al catálogo guardado sin pisar lo que usted haya cambiado, respetando además los servicios que haya borrado a propósito. Si la definición de un servicio diverge de la del plugin, se le avisa en vez de sobrescribirla.

**Las descargas se acotan al predio.** La consulta se restringe al *bounding box* de la parcela, de modo que nunca se descarga una capa nacional completa. Sin esa restricción, consultar el catastro rural de MIDAGRI para un predio de 40 hectáreas traería millones de entidades.

---

## Cuando algo falla

**Una capa aparece como «no evaluada».**
Es el comportamiento correcto, no un error de la herramienta. Revise el detalle: puede ser un servidor caído, un tiempo de espera agotado o un archivo corrupto. Repita el análisis más tarde para esa capa, o descárguela y evalúela en local. **No dé por libre de superposición un predio con capas sin evaluar.**

**«Probar conexión» falla en todas las capas.**
Casi siempre es la red. Si está en una entidad con proxy, configúrelo en `Configuración → Opciones → Red`. Compruebe también que otros servicios WMS le cargan.

**Las áreas no cuadran con el plano.**
Verifique el CRS del proyecto. En geográficas (EPSG:4326) el área calculada no corresponde a hectáreas sobre el terreno. Use EPSG:32719 para Madre de Dios.

**El resultado sale vacío pero se esperaba superposición.**
Confirme que el predio y la capa de contraste comparten un CRS coherente, y que el predio cae dentro de la cobertura del servicio consultado.

---

## Ver también

- [Caso real: cruce con la concesión Loboyoc II](../casos/superposicion_loboyoc.md) — verificación de 4.0566 ha de superposición
- [Referencia de geoservicios oficiales](../referencia/geoservicios.md)
