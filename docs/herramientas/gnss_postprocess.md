# Post-Proceso PPK / PPP

Post-procesa observaciones GNSS con RTKLIB: descarga las efemérides precisas, aplica correcciones de antena y valida la solución antes de darla por buena.

*Menú `Geodesia / GNSS` · Solo Windows*

---

## Para qué sirve

Un receptor GNSS de campo entrega posiciones con una precisión que, bajo dosel amazónico y lejos de una base, no basta para un plano catastral. El post-proceso corrige esas observaciones contra una base de coordenadas conocidas y produce posiciones centimétricas o submétricas, según las condiciones.

La herramienta reproduce el flujo que haría en Trimble Business Center, dentro de QGIS y con RTKLIB como motor.

!!! warning "Altura de antena del móvil"
    Debe introducir la altura **vertical hasta el ARP** (punto de referencia de antena), es decir, la medida directa sobre bastón. Si midió en diagonal con cinta sobre un trípode, **convierta antes**. Es el error que más veces invalida un levantamiento entero, y ningún programa puede detectarlo por usted.

---

## Antes de empezar

- Archivos RINEX del **móvil** (observación y navegación).
- Archivo RINEX de la **base**, o datos de una estación CORS.
- Coordenadas oficiales de la base — para Perú, la ficha del IGN.
- Conexión a internet la primera vez: RTKLIB (`rnx2rtkp.exe`, demo5 b34k) se descarga e instala solo.

---

## Cómo se usa

### 1. Cargar los archivos

Añada el archivo del móvil y el de la base. El archivo de navegación se detecta automáticamente, incluida la extensión corta `.O` de Trimble.

### 2. Revisar los datos de la base

La herramienta lee del encabezado RINEX el nombre del punto, la posición aproximada (convirtiendo de ECEF a geodésicas) y la altura de antena, y rellena el formulario.

**Esos valores son aproximados.** Corríjalos contra la ficha oficial del IGN antes de procesar: la posición del encabezado puede estar a varios metros de la coordenada publicada.

### 3. Elegir el modo

| Modo | Cuándo usarlo | Precisión |
|---|---|---|
| **Estático** | Punto ocupado varios minutos | Centimétrica |
| **Cinemático** | Levantamiento en movimiento | Centimétrica con FIX |
| **DGPS submétrico** | Bajo dosel o lejos de la base | 0.3 – 1 m |

!!! tip "Cuándo elegir DGPS submétrico"
    El modo DGPS resuelve por código, sin resolución de ambigüedades. Como no hay fase que fijar, **los falsos FIX son imposibles**. Bajo dosel cerrado o a gran distancia de la base, donde un FIX fiable no es alcanzable, una posición submétrica honesta vale más que una centimétrica falsa. Los resultados se rotulan como `SUBMÉTRICO DGPS`.

### 4. Antena y correcciones

El campo de antena es un desplegable con autocompletado de nombres IGS. Descargue el ANTEX maestro de IGS20 desde el propio diálogo, o cargue el ANTEX del fabricante.

Las correcciones PCV de satélite se activan solo con efemérides precisas, y las de receptor solo con un ANTEX válido y un nombre de antena reconocido. Sin esas condiciones no se aplican, para no dejarlas como una mención documental sin efecto real.

### 5. Procesar

**Ejecutar** lanza RTKLIB. Al terminar carga en QGIS el punto corregido con todos los atributos de calidad.

---

## Modos avanzados

### Ocupaciones múltiples en un archivo

Si el receptor (Geo7X, DA2) marcó eventos de ocupación dentro de un RINEX continuo, la herramienta resuelve **cada punto por separado, sin promediar entre puntos distintos**.

El procedimiento: se procesa el archivo completo en cinemático, lo que mantiene la continuidad de ambigüedades entre puntos, y después se recorta la solución por cada ventana temporal de ocupación para calcular su posición estática. Cada punto obtiene su propio informe de calidad y usted decide cuál acepta.

### Procesamiento por lotes

Procese varios móviles contra una misma base en una corrida: añada archivos o explore una carpeta de campaña. Sale una sola capa con todos los puntos corregidos y un resumen de campaña en el registro.

---

## Validación de la solución

Dos controles evitan aceptar resultados engañosos:

- **Antifalso-fix.** Las épocas FIX con dispersión horizontal superior a 0.5 m se descartan como falsos fijos.
- **FLOAT no convergido.** Por encima de 2 m se rotula como NO FIABLE, en vez de informar una calidad que no corresponde.

El promedio es una **media ponderada por 1/σ²**, la misma metodología de TBC, no una media aritmética.

---

## Cuando algo falla

**RTKLIB no se descarga.**
Necesita internet la primera vez. Con proxy, configúrelo en `Configuración → Opciones → Red`.

**La solución sale toda en FLOAT.**
Suele ser dosel denso, sesión corta o demasiada distancia a la base. Alargue la ocupación o pase a DGPS submétrico.

**Las coordenadas salen desplazadas de forma sistemática.**
Revise en este orden: coordenadas de la base contra la ficha IGN, altura de antena del móvil (vertical al ARP) y altura de antena de la base.

**El módulo abre vacío.**
Corregido en la versión 2.5.1. Actualice el plugin.

---

## Ver también

- [Memoria Descriptiva](memoria_descriptiva.md) — para documentar el levantamiento
