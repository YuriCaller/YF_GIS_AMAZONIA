# Etiquetado Técnico

Aplica etiquetas técnicas según el tipo de geometría, desde el clic derecho sobre el lienzo.

*Disponible desde la versión 2.1.0*

---

## Qué aplica a cada geometría

La herramienta detecta el tipo y aplica el estilo correspondiente:

| Geometría | Etiqueta |
|---|---|
| **Puntos** | Vértices numerados: `V-01`, `V-02`... |
| **Líneas** | Distancia y azimut, paralelos al segmento |
| **Polígonos** | Bloque con área y perímetro |

Las etiquetas usan expresiones dinámicas (`$area`, `$perimeter`, `$length`), de modo que **se actualizan si la geometría cambia**. No hay que volver a etiquetar tras editar un vértice.

Hay cinco estilos predefinidos por tipo de geometría.

---

## Cómo se usa

Clic derecho sobre el lienzo con la capa activa, y elija el estilo.

---

## Cuando algo falla

**Las etiquetas no aparecen.**
Compruebe que las etiquetas están activadas para la capa y que la escala de visualización lo permite.

**El área etiquetada no coincide con la del plano.**
La expresión `$area` es elipsoidal. Para catastro conviene el área plana — vea la [Calculadora de Geometría Vectorial](vector_geometry.md).

---

## Ver también

- [Segmentador de Parcelas](segmentador.md)
