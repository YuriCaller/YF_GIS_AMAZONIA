# Generador de Cajetín

Inserta el cajetín del plano en el compositor, con expresiones dinámicas que se actualizan solas y todos los elementos agrupados.

*Menú `Layout / Compositor`*

---

## Para qué sirve

El cajetín es lo que se rehace en cada plano y lo que más errores acumula: una escala que quedó de la lámina anterior, una fecha vieja, un datum que no corresponde. Al generarlo con expresiones, esos campos se leen del proyecto y no pueden desactualizarse.

---

## Cómo se usa

1. Abra el compositor de impresión con su lámina.
2. Ejecute la herramienta y **elija el layout de destino** en el desplegable.
3. Elija la posición y genere.

Todos los elementos se agrupan como un solo objeto, de modo que puede moverlo sin descolocar sus partes.

---

## Campos dinámicos

Se leen del proyecto y del mapa asociado:

- Escala del mapa de referencia
- Fecha
- Datum y proyección
- Unidades
- Centroide del mapa

El mapa de referencia se asigna automáticamente al generar.

---

## Modelo Predio Agrícola

Reproduce la anatomía exacta del plano de producción: 121.5 × 47.8 mm, verde `#175339`, celda de DNI, escudo y norte laterales, y la línea de Fuente fuera del marco.

---

## Cuando algo falla

**Se genera en el layout equivocado.**
Corregido en la versión 2.6.1: el destino se elige en el diálogo y se aplica de verdad. El fallo venía de guardar objetos `QgsPrintLayout` como `userData`, lo que los degradaba a `QGraphicsScene`; ahora se resuelven por nombre. Actualice el plugin.

**Las expresiones muestran texto en vez del valor.**
El cajetín necesita un mapa de referencia asignado. Compruebe que la lámina tiene al menos un elemento de mapa.

---

## Ver también

- [Gestor de Estilos de Tabla](layout_tools.md)
- [Redimensionar Composición](layout_rescaler.md)
