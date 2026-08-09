# Generador de Sistemas Agroforestales

Diseña la distribución de un SAF dentro del predio, con seis métodos de siembra.

*Menú `Agroforestal / Ambiental`*

---

## Para qué sirve

Un expediente de sistema agroforestal necesita mostrar la distribución de individuos por especie sobre el predio, con distanciamientos coherentes y un conteo verificable. La herramienta genera esa distribución y la capa de puntos correspondiente.

---

## Cómo se usa

1. Seleccione el polígono del predio.
2. Elija el método de siembra y los distanciamientos.
3. Genere.

Sale una capa de puntos con la posición de cada individuo y el conteo por especie.

---

## Cuando algo falla

**Salen muchos menos individuos de los esperados.**
Revise las unidades del distanciamiento y el CRS: en coordenadas geográficas el espaciado no corresponde a metros.

**Los puntos se salen del predio.**
Verifique que el polígono sea válido — `Vectorial → Herramientas de geometría → Comprobar validez`.
