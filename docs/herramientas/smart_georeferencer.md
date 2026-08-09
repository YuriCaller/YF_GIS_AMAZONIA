# Georreferenciador Inteligente

Georreferencia planos escaneados e imágenes de dron **en vivo sobre el lienzo**: la imagen se deforma a medida que usted coloca puntos de control, sin pasar por una ventana aparte.

*Disponible desde la versión 2.4.0 · Menú `Catastral`*

---

## Para qué sirve

El georreferenciador de QGIS trabaja en una ventana separada: usted coloca puntos a ciegas y solo ve el resultado al final. Cuando lo que georreferencia es un plano catastral de 1966 con deformaciones de papel, ese ciclo de ensayo y error se hace largo.

Aquí la imagen entra como una capa ráster más y **se deforma sobre el mapa en tiempo real**. Ve el ajuste mientras lo construye.

---

## Antes de empezar

- La imagen a georreferenciar: plano escaneado, ortofoto o captura.
- Una **capa de referencia** con geometría confiable — catastro vecino, red vial, hidrografía.
- Opcionalmente `opencv-python`, solo para la detección automática de puntos. La captura manual funciona sin él.

---

## Cómo se usa

### 1. Cargar la imagen

Se coloca como capa ráster en el panel de capas.

!!! note "Archivos JPEG"
    Se convierten una vez a GeoTIFF. La lectura perezosa del JPEG hace fallar el warp, y esta conversión previa lo evita.

### 2. Capturar puntos de control

Captura en dos clics, al estilo de ArcGIS: **primer clic** sobre el rasgo en la imagen (ancla fija), **segundo clic** sobre el mismo rasgo en el mapa. Una flecha guía une ambos mientras mueve el cursor.

!!! tip "Ajuste a vértices"
    El destino se ajusta automáticamente a los vértices de las capas de referencia, según la configuración de autoensamblado de QGIS. Actívela (`Proyecto → Opciones de autoensamblado`) antes de empezar: coloca los puntos sobre el vértice exacto en vez de sobre su vecindad.

### 3. Detección automática (opcional)

Con OpenCV instalado, detecta puntos por correspondencia de rasgos (SIFT/ORB con RANSAC). Funciona bien entre imágenes de la misma zona y tomas parecidas; con un plano dibujado a mano rinde poco y conviene la captura manual.

### 4. Revisar la calidad

Con cinco puntos o más se activa el diagnóstico **leave-one-out**: se retira cada punto por turno, se reajusta el modelo sin él y se mide cuánto se desvía la predicción respecto a su posición real.

El resultado se muestra como mapa de calor sobre los marcadores y como lista ordenada de peor a mejor. Un punto muy destacado suele estar mal colocado, no ser un punto malo del plano.

Corrija o elimine desde el menú contextual: añadir, borrar o editar las XY de cualquier punto.

### 5. Exportar

**Exportar GeoTIFF** produce la imagen georreferenciada a resolución completa, con transformación TPS o polinómica. **Colocar capa permanente** deja el resultado en el proyecto.

---

## Importar puntos desde CSV o Excel

Si ya tiene una tabla de puntos, cárguela con las columnas `pixelX`, `pixelY`, `mapX`, `mapY`. Útil cuando el plano trae ya identificadas sus esquinas en coordenadas.

---

## Cuando algo falla

**La imagen no se deforma.**
Hacen falta al menos tres puntos de control. Por debajo de eso no hay modelo que aplicar.

**«hBand is NULL» o la imagen parpadea.**
Corregido: cada confirmación reconstruye la capa de trabajo desde cero para evitar la carrera de renderizado. Actualice el plugin si persiste.

**La detección automática no encuentra nada.**
Es lo esperable en planos dibujados a mano o escaneos de baja calidad. Pase a captura manual.

**El resultado queda muy deformado.**
Revise el diagnóstico LOO y elimine los puntos peores. TPS se adapta a la deformación local, y con puntos inconsistentes esa flexibilidad juega en contra.

---

## Ver también

- [Etiquetado Técnico](smart_labels.md) — para rotular el resultado
