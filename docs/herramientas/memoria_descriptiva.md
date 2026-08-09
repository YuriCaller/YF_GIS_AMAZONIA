# Memoria Descriptiva

Genera la memoria descriptiva del predio en formato Word, con cuadro de vértices, narrativa de colindancias y croquis, a partir del polígono cargado en QGIS.

*Menú `Catastral` · Requiere el componente `python-docx`*

---

## Para qué sirve

La memoria descriptiva acompaña a casi todo trámite de saneamiento físico-legal: es el documento que describe el predio en palabras y en cifras, vértice por vértice y lindero por lindero. Redactarla a mano desde una tabla de coordenadas es lento y propenso a discrepancias entre lo que dice el texto, lo que dice el cuadro y lo que muestra el plano.

Esta herramienta la construye desde la geometría, de modo que **las tres cosas provienen de la misma fuente**.

---

## Antes de empezar

- Una capa de polígonos con el predio, en un **CRS proyectado** (para Madre de Dios, EPSG:32719).
- El componente `python-docx`. Si falta, la herramienta ofrece instalarlo — vea [componentes opcionales](../instalacion/dependencias.md).
- Idealmente, haber pasado antes por el [Segmentador de Parcelas](segmentador.md): la memoria toma de ahí los azimuts y distancias.

---

## Cómo se usa

### 1. Elegir el predio y los campos

En la pestaña **Campos**, indique la capa, el nombre del titular y el DNI. Los veinticinco controles del diálogo llevan una ayuda emergente que explica qué campo elegir y por qué.

### 2. Configurar el formato

Tres decisiones determinan la coherencia del documento con el plano:

**Formato de azimut.** Decimal (igual que el plano), en grados-minutos-segundos, o ambos. Elija el mismo que use el plano perimétrico para que no haya discrepancia entre documento y lámina.

**Patrón de vértices.** `V-1`, `V01`, `P-1`... El patrón elegido se aplica de forma uniforme al vértice, al lado y a la narrativa.

**Precisión.** Coordenadas con cuatro decimales y distancias con dos, conforme a la norma.

### 3. Generalidades

Método y equipo de levantamiento se parametrizan con preajustes: GNSS diferencial, PPK, navegador, dron o estación total. La vista previa muestra en vivo cómo quedará redactado el párrafo.

### 4. Generar

**Generar Memoria** produce el documento y lo abre. En modo Atlas, abre la carpeta con todos los documentos generados.

---

## De dónde salen los datos

Este punto importa cuando el resultado no cuadra con lo esperado.

**Azimut y distancia se toman del Segmentador**, que es la fuente autoritativa. El cálculo geométrico propio se usa solo como respaldo, y cuando ambos discrepan, la herramienta lo advierte en vez de elegir en silencio.

Si ve un aviso de discrepancia, revise primero la capa de segmentos: casi siempre significa que la geometría cambió después de generarla y hay que volver a correr el Segmentador.

---

## Qué produce

Un documento Word con:

1. Generalidades — método, equipo, fecha
2. Ubicación política y geográfica
3. Descripción del perímetro — narrativa lado por lado con colindantes
4. Cuadro de vértices — coordenadas UTM
5. Cuadro de lados — distancia y azimut
6. Área y perímetro
7. Croquis del predio (opcional) — render del lienzo encuadrado al polígono

---

## Cuando algo falla

**«La biblioteca python-docx no está instalada».**
Pulse instalar en la ventana que aparece. Si falla, vea [componentes opcionales](../instalacion/dependencias.md): la página cubre proxies, certificados y la instalación sin internet.

**Instalé python-docx y sigue bloqueada.**
Desde la versión 3.0.6 la herramienta recarga sus submódulos tras instalar, así que no debería ocurrir. Si pasa, reinicie QGIS.

**Las colindancias salen vacías o incompletas.**
La detección necesita capas adyacentes cargadas en el proyecto. Sin ellas, no hay con qué identificar al colindante.

**El área no coincide con el plano.**
Revise el CRS del proyecto y si el plano usa área elipsoidal o plana. La [Calculadora de Geometría Vectorial](vector_geometry.md) permite comparar ambas.

---

## Ver también

- [Segmentador de Parcelas](segmentador.md) — fuente de azimuts y distancias
- [Generador de Cajetín](title_block.md) — para el plano que acompaña a la memoria
- [Exportar Expediente](batch_export.md) — para armar la entrega completa
