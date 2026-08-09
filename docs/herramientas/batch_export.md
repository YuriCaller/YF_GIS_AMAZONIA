# Exportar Expediente

Exporta capas y composiciones a una carpeta estructurada, lista para entregar.

*Disponible desde la versión 2.1.0 · Menú `Catastral`*

---

## Qué produce

En una sola acción, una carpeta con:

- **SHP** y **GPKG** de las capas seleccionadas
- **PDF** de las composiciones, al DPI que indique
- **XLSX** con las tablas de coordenadas
- **METADATOS.txt** con el detalle de lo exportado

Opcionalmente comprimido en ZIP.

---

## Plantillas

La estructura de carpetas se adapta a quién recibe el expediente: **GOREMAD**, **SERFOR**, **ACCA** o **Simple**.

---

## Cómo se usa

1. Elija la plantilla.
2. Marque capas y composiciones.
3. Indique la carpeta de destino y el DPI de los PDF.
4. Exporte.

---

## Cuando algo falla

**Faltan capas en la salida.**
Las capas temporales o en memoria deben guardarse antes.

**Los PDF salen pesados.**
Baje el DPI. Para revisión bastan 150; para impresión final, 300.

---

## Ver también

- [Memoria Descriptiva](memoria_descriptiva.md)
