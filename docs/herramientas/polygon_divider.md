# Divisor de Polígonos

Divide un predio por área exacta, en partes iguales o por porcentajes, usando una línea de corte que usted traza o define por ángulo.

*Disponible desde la versión 2.3.0 · Menú `Catastral`*

---

## Para qué sirve

División y partición de herencias, segregación de un lote, reserva de un área de servidumbre. Casos en los que no basta partir por la mitad a ojo: la fracción resultante debe tener **exactamente** el área que dice el documento.

Equivale a la herramienta *Divide* de ArcGIS Pro, con geometría nativa de QGIS y sin dependencias externas.

---

## Cómo se usa

### 1. Elegir el polígono y el criterio

| Criterio | Qué pide |
|---|---|
| **Área exacta** | Hectáreas de la primera fracción |
| **N partes iguales** | Número de fracciones |
| **Porcentajes** | Lista de porcentajes que sume 100 |

### 2. Definir la línea de corte

Trácela sobre el lienzo o defínala por ángulo. Se resalta en rojo antes de aplicarse, para que compruebe la orientación.

La línea marca la **dirección** del corte; la posición exacta la calcula la herramienta para cumplir el área pedida.

### 3. Elegir la salida

**Capa GeoPackage separada** (recomendado) — deja intacto el predio original y crea una capa nueva con los atributos heredados más los campos `fraccion`, `area_ha`, `porcentaje`, `fecha_division` y `poligono_padre_id`, con etiquetado automático.

**Edición en el sitio** — modifica el predio original. Pide confirmación explícita, porque no hay vuelta atrás sin deshacer.

---

## Cuando algo falla

**El área resultante no es exacta.**
Revise el CRS del proyecto. En coordenadas geográficas el cálculo de área no corresponde a hectáreas sobre el terreno.

**«UNIQUE constraint failed» al guardar en GeoPackage.**
La capa de salida ya no hereda columnas de clave primaria (`fid`, `ogc_fid`, `objectid`, `gid`) del polígono de origen, que es lo que provocaba la colisión. Actualice el plugin.

**El corte deja una fracción en varias piezas.**
Ocurre con predios cóncavos o con entrantes pronunciados. Pruebe otra orientación de la línea.

---

## Ver también

- [Segmentador de Parcelas](segmentador.md)
- [Calculadora de Geometría Vectorial](vector_geometry.md) — para verificar áreas
