# COGO — Poligonal en Vivo

Dibuja un predio lado a lado sobre el lienzo introduciendo azimut (o rumbo) y distancia, con previsualización, error de cierre y compensación Bowditch.

*Disponible desde la versión 3.5.0 · Menú `Catastral`*

---

## Para qué sirve

Levantar un polígono a partir de un plano en papel, una libreta de campo o un expediente que solo trae azimuts y distancias, leyendo los lados uno por uno mientras se ve cómo se forma la figura.

El COGO nativo de QGIS trabaja con ángulo cartesiano (medido desde el Este, en sentido antihorario) y obliga a convertir cada lado. Aquí se escribe el azimut tal como viene en el documento.

Si ya se tiene el cuadro de vértices completo en Excel, Word o PDF, es más rápido pegarlo en la pestaña **Reconstruir predio** de [Memoria Descriptiva](memoria_descriptiva.md). Ambas herramientas usan el mismo núcleo de cálculo, así que el parseo de azimuts, el cierre y la compensación dan exactamente el mismo resultado.

---

## Antes de empezar

El proyecto debe estar en un **CRS proyectado** (por ejemplo, WGS 84 / UTM zona 19S). En coordenadas geográficas la herramienta no se abre, porque una distancia en metros no tiene sentido sobre grados.

---

## Cómo se usa

### 1. Fijar el origen

Con **Fijar con clic en el mapa** o escribiendo Este y Norte del primer vértice y pulsando **Usar**.

### 2. Corrección (opcional)

| Campo | Cuándo usarlo |
|---|---|
| **Declinación** | El documento da azimuts magnéticos. Con signo: Oeste es negativa en el Perú. |
| **Convergencia** | Se quiere pasar de Norte verdadero a Norte de cuadrícula. |

Déjelas en 0 si los azimuts ya están referidos a la cuadrícula UTM.

### 3. Agregar lados

Escriba el azimut y la distancia en metros y pulse **Agregar lado**. El azimut admite tres formas:

| Forma | Ejemplo |
|---|---|
| Decimal | `253.2583` |
| Grados, minutos y segundos | `253°15'30"` |
| Rumbo por cuadrante | `N 4°44' W` |

Cada lado se dibuja al instante. **Deshacer último** retira el lado más reciente.

El azimut es obligatorio en cada lado. Un lindero natural (quebrada, carretera) no tiene azimut y no puede trazarse aquí; para esos casos use **Reconstruir predio**.

### 4. Cerrar y guardar

**Cerrar figura** muestra el error de cierre lineal y relativo. Si marca **Compensar cierre (Bowditch)**, el error se reparte entre los lados en proporción a su longitud. Fuera de tolerancia la compensación se niega, salvo que marque también la casilla de forzado: compensar un cierre malo no lo corrige, lo esconde.

**Guardar geometría** valida el polígono antes de escribirlo. El destino es:

- la **capa activa**, si es de polígonos y está en el CRS del proyecto; o
- una capa temporal nueva, **COGO_poligonal**, con los campos `area_m2`, `area_ha`, `perimetro` y `compensada`.

La capa temporal vive en memoria: guárdela como GeoPackage antes de cerrar QGIS.

---

## Cuando algo falla

**«El proyecto está en un CRS geográfico».**
Cambie el CRS del proyecto a la zona UTM que corresponda y vuelva a abrir la herramienta.

**La figura se cruza sobre sí misma y no se guarda.**
Casi siempre es un azimut mal leído, típicamente un rumbo con el cuadrante invertido (E por W). Revise el lado en la lista y use **Deshacer último**.

**El error de cierre es grande.**
Revise primero la declinación: un plano antiguo en azimut magnético con la declinación en 0 queda girado en bloque, y el cierre se dispara.

---

## Ver también

- [Memoria Descriptiva](memoria_descriptiva.md) — pestaña *Reconstruir predio*, para pegar el cuadro completo
- [Segmentador de Parcelas](segmentador.md) — azimuts y distancias de un polígono existente
- [Calculadora de Geometría Vectorial](vector_geometry.md) — azimut magnético para trabajo de campo
