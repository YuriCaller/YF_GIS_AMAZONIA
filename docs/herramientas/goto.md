# Navegación a Coordenadas (Go-To)

Lleva el mapa a una coordenada concreta, escrita a mano, pegada desde Excel o leída de una captura de pantalla.

*Menú `Navegación`*

---

## Para qué sirve

Un expediente llega con un cuadro de vértices en papel, en un PDF o en una hoja de Excel. Antes de dibujar nada hay que ver dónde cae ese predio. Esta herramienta va de la coordenada al mapa en un paso.

---

## Formatos admitidos

| Formato | Ejemplo |
|---|---|
| Grados decimales | `-12.5931, -69.1892` |
| Grados, minutos, segundos | `12°35'35.2"S 69°11'21.1"W` |
| UTM | `19L 456789 8608123` |
| MGRS | `19LDL5678908123` |

---

## Pegado desde Excel

Copie una o dos columnas de coordenadas en Excel y péguelas en el diálogo. Se reconocen tanto la disposición por filas (`Este  Norte` en cada renglón) como **por columnas**, que es lo habitual al copiar una columna de Estes y otra de Nortes.

!!! info "Por qué esto no era trivial"
    Excel deja en el portapapeles **dos representaciones** del mismo rango: el texto tabulado y una imagen de las celdas. Hasta la versión 3.0.6 el diálogo miraba la imagen primero y hacía OCR sobre ella: se descartaban los datos exactos para reconocerlos de una captura, perdiendo tabuladores y saltos de línea e introduciendo errores de dígitos. Ahora el texto tiene prioridad y el OCR queda como último recurso.

    El emparejamiento también se corrigió. Antes se tomaban los dos primeros números de cada línea sin comprobar coherencia, de modo que un renglón con varios Estes producía el par (Este, Este) y coordenadas imposibles — una latitud de −86 para un predio de Madre de Dios. Ahora las magnitudes deben ser compatibles.

**Limitación conocida:** la separación por magnitud asume coordenadas UTM. Un pegado de latitud/longitud dispuesto por columnas no se reordena.

---

## Lectura por OCR

Cuando solo tiene una captura de pantalla o una foto del cuadro de vértices, péguela y se leerá por reconocimiento de texto. Dos motores: el nativo de Windows (`winsdk`) y Tesseract como respaldo.

!!! warning "Revise siempre lo que reconoce el OCR"
    El reconocimiento confunde dígitos con regularidad. La detección descarta los valores atípicos respecto a la mediana de cada grupo, pero **no puede corregir un dígito mal leído dentro del rango plausible**. Contraste los pares resultantes contra el original antes de usarlos.

---

## Marcadores

Guarde ubicaciones frecuentes —una base GNSS, la oficina, un vértice de referencia— y vuelva a ellas con un clic.

---

## Cuando algo falla

**Las coordenadas caen en el lugar equivocado.**
Casi siempre es la zona UTM o el hemisferio. Para Madre de Dios, zona 19 sur (EPSG:32719).

**El pegado desde Excel no reordena los pares.**
La detección es deliberadamente conservadora: no actúa si los grupos quedan desequilibrados o internamente incoherentes, para no descolocar un listado que ya venía bien emparejado. Revise que copió columnas completas.

**El OCR no lee nada.**
Necesita `winsdk` o Tesseract. Vea [componentes opcionales](../instalacion/dependencias.md). Con una imagen de baja resolución, escriba a mano.
