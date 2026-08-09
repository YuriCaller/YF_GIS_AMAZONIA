# Caso real: superposición con una concesión forestal

Verificación de un predio en trámite de titulación que resultó superpuesto con una concesión forestal ya otorgada. Es el caso con el que se validó el [Analizador de Superposición](../herramientas/superposition.md) durante todo su desarrollo.

!!! info "Sobre este caso"
    Los datos corresponden a un expediente real de Madre de Dios. Se documenta el procedimiento y el resultado técnico; no se reproduce documentación del expediente ni datos personales más allá de lo necesario para entender el flujo.

---

## El problema

Un predio rural en trámite de titulación ante la Dirección Regional Agraria. Antes de armar el expediente había que verificar que no invadiera derechos ya otorgados —concesiones forestales, áreas protegidas, comunidades— porque una superposición detectada después, ya en trámite, significa observación y meses de retraso.

La verificación a mano habría exigido descargar las capas de SERFOR y SERNANP, reproyectarlas, intersecar una por una y redactar el resultado.

---

## El procedimiento

**1. Preparación.** Proyecto en EPSG:32719 (UTM 19S / WGS84) y el polígono del predio cargado, procedente del levantamiento GNSS post-procesado.

**2. Selección de fuentes.** Geoservicios de SERFOR (concesiones forestales, permisos, cesiones en uso, BPP) y de SERNANP (ANP, zonas de amortiguamiento). Se probó la conexión capa por capa antes de lanzar el análisis.

**3. Ejecución.** Consulta acotada al *bounding box* del predio.

---

## El resultado

**Superposición de 4.0566 ha** entre el predio y la concesión forestal **Loboyoc II**.

El informe recogió el área superpuesta en hectáreas, el porcentaje del predio afectado, el nivel de severidad, la trazabilidad del servicio consultado (URL, capa, fecha, hora y conteo de entidades) y la advertencia legal de SERFOR conforme al artículo 62 de la Ley 29763.

---

## Qué se aprendió

Tres cosas que cambiaron el diseño de la herramienta.

**El recuento de capas mentía.** Las capas con error de carga engrosaban el recuento de evaluadas, de modo que el informe afirmaba haber contrastado fuentes que nunca pudo leer. Desde la versión 3.0.5 se cuentan por separado `capas_evaluadas`, `capas_no_evaluadas` y `capas_totales`, y la conclusión declara la cobertura real.

**La salvedad tiene que ir dentro de la conclusión.** Antes figuraba en una sección posterior del informe. Como lo que se transcribe al expediente es el párrafo de conclusión, el texto que llegaba al trámite afirmaba un resultado limpio sin matizar que faltaban capas por evaluar. Ahora la constancia va dentro del propio párrafo.

**Un geoservicio no se acredita como un archivo.** El SHA-256 de un archivo prueba que es el mismo archivo. Un geoservicio solo admite una instantánea: URL, capa, hora y conteo. Cuando el expediente exige poder demostrar más adelante contra qué exactamente se contrastó, conviene descargar la capa, archivarla y evaluarla en local.

---

## Ver también

- [Análisis de Superposición de Derechos](../herramientas/superposition.md)
- [Referencia de geoservicios oficiales](../referencia/geoservicios.md)
