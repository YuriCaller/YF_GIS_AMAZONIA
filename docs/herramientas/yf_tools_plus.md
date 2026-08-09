# YF Tools Plus

Utilidades de coordenadas y geometría, con la pestaña **Tabla → Polígono** que arma predios directamente desde Excel o CSV.

*Menú `Catastral`*

---

## Tabla → Polígono

Construye polígonos desde una tabla de coordenadas, sin pasos intermedios de conversión.

### Cómo se usa

1. Seleccione el archivo `.xlsx`, `.xls` o `.csv`. Si es Excel, elija la hoja.
2. Los campos X, Y, ID y orden de vértices **se detectan automáticamente**; corrija si hace falta.
3. Genere.

### Varios predios en una tabla

Con el campo **ID**, una misma tabla puede contener varios predios o fracciones: cada grupo se convierte en su propio polígono. El campo de orden de vértices controla la secuencia dentro de cada grupo.

### Validación

El reporte indica qué grupos se omitieron y qué filas tenían coordenadas inválidas, **identificadas por su número de fila en Excel** para que pueda ir directamente a corregirlas.

La capa resultante lleva los atributos `ID`, `VERTICES`, `AREA_HA` y `PERIMETRO`, calculados de forma elipsoidal sobre WGS84.

---

## Otras pestañas

**Segmentador** — es la pestaña que abre por defecto. Vea [Segmentador de Parcelas](segmentador.md).

**Coordenadas y geometría** — cálculo de vértices, área y perímetro sobre la capa activa.

---

## Cuando algo falla

**No detecta los campos X e Y.**
Los encabezados deben estar en la primera fila de la hoja. Si la tabla trae un título o filas en blanco encima, quítelos.

**Un grupo se omite.**
Necesita al menos tres vértices válidos. El reporte indica qué filas se descartaron y por qué.

**El polígono sale cruzado.**
Los vértices están en orden incorrecto. Use el campo de orden, o revise la secuencia en la tabla.

---

## Ver también

- [Divisor de Polígonos](polygon_divider.md)
- [Memoria Descriptiva](memoria_descriptiva.md)
