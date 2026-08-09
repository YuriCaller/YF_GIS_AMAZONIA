# Calculadora de Geometría Vectorial

Calcula área, perímetro, centroide, coordenadas, longitud y azimut **directamente sobre la capa activa**, sin crear capas nuevas.

*Disponible desde la versión 2.1.0 · Menú `Catastral` y clic derecho en el panel de capas*

---

## Elipsoidal o plano: cuál elegir

Es la decisión que más consecuencias tiene en esta herramienta.

| Método | Qué calcula | Cuándo usarlo |
|---|---|---|
| **Elipsoidal** (`$area`) | Superficie real sobre el elipsoide | Análisis territorial, estadísticas, superficies grandes |
| **Plano** (`area($geometry)`) | Superficie sobre el plano de proyección | **Planos legales y catastro** |

Para un expediente catastral use **plano**: es el área que corresponde a lo representado en la lámina y a lo que verificará la entidad. La diferencia entre ambos métodos crece con la superficie y con la distancia al meridiano central.

El modo plano valida que el proyecto esté en un CRS proyectado y avisa si no lo está.

---

## Cómo se usa

1. Clic derecho sobre la capa en el panel, o desde el menú.
2. Elija qué calcular y el nombre del campo de destino — el desplegable muestra los campos existentes.
3. Opcionalmente, limite el cálculo a las entidades seleccionadas.

Funciona sobre polígonos, líneas y puntos. El azimut se entrega en grados-minutos-segundos o decimal.

---

## Cuando algo falla

**El área sale en un número enorme o absurdo.**
El proyecto está en coordenadas geográficas. Cambie a un CRS proyectado (EPSG:32719 para Madre de Dios).

**El campo no se actualiza.**
Compruebe que la capa admite edición y que el campo tiene tipo numérico con decimales suficientes.

---

## Ver también

- [Divisor de Polígonos](polygon_divider.md)
