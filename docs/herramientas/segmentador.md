# Segmentador de Parcelas

Calcula azimuts, ángulos internos y distancias por lado, y genera las capas de segmentos y vértices del predio.

*Menú `Catastral`*

---

## Para qué sirve

Es la base de todo el cuadro de lados de un plano catastral: qué distancia y qué rumbo tiene cada lindero. La [Memoria Descriptiva](memoria_descriptiva.md) toma de aquí sus azimuts y distancias, tratando esta salida como la **fuente autoritativa**.

---

## Cómo se usa

1. Seleccione la capa de polígonos y el predio.
2. Ejecute.

Se generan dos capas: **Segmentos**, con distancia y azimut por lado, y **Vértices**, numerados en secuencia.

---

## Cuando algo falla

**«UNIQUE constraint failed» al exportar a GeoPackage.**
Las capas temporales ya no heredan columnas de clave primaria (`fid`, `ogc_fid`, `objectid`, `gid`) del polígono de origen. Antes, un `fid` heredado chocaba con la clave que crea el GeoPackage al guardar, desplazando valores de atributos. Actualice el plugin.

**Los azimuts no coinciden con el plano.**
Verifique el CRS: el azimut se calcula sobre la cuadrícula del sistema proyectado. Un plano en otro sistema dará rumbos distintos.

**Los vértices salen desordenados.**
Siguen el orden de la geometría. Si el polígono se digitalizó de forma irregular, reordénelo antes.

---

## Ver también

- [Memoria Descriptiva](memoria_descriptiva.md)
- [Etiquetado Técnico](smart_labels.md)
