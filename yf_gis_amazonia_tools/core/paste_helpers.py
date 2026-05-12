# -*- coding: utf-8 -*-
"""
YF Go-To Tool - Smart Paste Helpers
Utilidades para extraer coordenadas de texto libre/desordenado.

Casos típicos:
- Excel: "485185\t8625060"
- CSV: "485185, 8625060"
- WhatsApp/correo: "el punto está en este 485185 norte 8625060"
- Multilínea: "Easting: 485185\nNorthing: 8625060"
- Lista: "V1: 485185, 8625060\nV2: 485200, 8624800"

Autor: Yuri Caller - TUCSA / gis-amazonia.pe
"""

import re


# ============================================================
# Detección de pares numéricos
# ============================================================

# Palabras clave que pueden preceder un valor de Este/Norte
EASTING_KEYWORDS = ['este', 'east', 'easting', 'x', 'utm_x', 'utmx', 'e:']
NORTHING_KEYWORDS = ['norte', 'north', 'northing', 'y', 'utm_y', 'utmy', 'n:']


def extract_number_pair(text):
    """
    Extrae el primer par de números de un texto libre.

    Heurísticas:
    1. Si hay keywords "este/norte", usa el orden semántico
    2. Si los números tienen magnitud UTM típica (6-7 dígitos para Norte, 6 dígitos para Este),
       interpretarlos como (Easting, Northing)
    3. Sin keywords, usar el orden de aparición

    Retorna (val1, val2) o None.
    """
    if not text:
        return None

    t = text.strip()

    # Estrategia 1: keywords semánticos
    east_val = _find_value_after_keyword(t, EASTING_KEYWORDS)
    north_val = _find_value_after_keyword(t, NORTHING_KEYWORDS)
    if east_val is not None and north_val is not None:
        return (east_val, north_val)

    # Estrategia 2: extraer todos los números y tomar los dos primeros plausibles
    numbers = _extract_numbers(t)
    if len(numbers) < 2:
        return None

    # Filtrar números que parezcan coordenadas (no IDs cortos, no años, etc.)
    plausible = [n for n in numbers if _looks_like_coordinate(n)]
    if len(plausible) >= 2:
        return (plausible[0], plausible[1])

    return (numbers[0], numbers[1])


def _extract_numbers(text):
    """Extrae todos los números (incluso decimales y negativos) de un texto."""
    # Manejar coma decimal estilo europeo: si vemos un número como "12,345" Y otros números,
    # convertir si parece decimal. Lógica conservadora: solo si está rodeado de dígitos sin
    # contexto de millares.

    # Patrón: número opcional con signo, parte entera, opcional decimal con . o ,
    pattern = r'-?\d+(?:[.,]\d+)?'
    raw_matches = re.findall(pattern, text)

    results = []
    for m in raw_matches:
        # Decidir si la coma es decimal o de millares
        # Heurística: si después de coma hay <= 3 dígitos y no parece millares
        # (no precede a otro grupo de 3), tratarlo como decimal
        if ',' in m and '.' not in m:
            # Convertir coma a punto para parsing
            normalized = m.replace(',', '.')
            try:
                val = float(normalized)
                results.append(val)
            except ValueError:
                pass
        else:
            try:
                val = float(m)
                results.append(val)
            except ValueError:
                pass

    return results


def _find_value_after_keyword(text, keywords):
    """
    Busca un número que aparezca después de una de las palabras clave.
    Tolerante a separadores: dos puntos, espacios, =
    """
    t = text.lower()
    for kw in keywords:
        # Patrón: keyword + separador + número
        # Ej: "este: 485185", "x = 485185", "Easting 485185"
        pattern = re.escape(kw) + r'\s*[:=]?\s*(-?\d+(?:[.,]\d+)?)'
        m = re.search(pattern, t)
        if m:
            try:
                val_str = m.group(1).replace(',', '.')
                return float(val_str)
            except ValueError:
                continue
    return None


def _looks_like_coordinate(num):
    """
    Heurística: el número parece una coordenada (no un ID, año, etc.).
    Acepta:
    - Decimales con parte fraccional (lat/lon): -180 a 180 con decimales
    - Positivos grandes (UTM): 10000 a 10000000
    Rechaza:
    - Enteros sin decimal entre -200 y 200 (probables IDs: V1, V2, año, etc.)
    """
    abs_n = abs(num)

    # UTM (rango amplio de valores positivos grandes)
    if 10000 < abs_n < 10000000:
        return True

    # Lat/Lon decimal: debe tener parte fraccional
    # (los IDs como V1, V2 son enteros)
    has_decimal = (num != int(num))
    if abs_n <= 180 and has_decimal:
        return True

    return False


# ============================================================
# Múltiples pares de coordenadas
# ============================================================

def extract_multiple_pairs(text):
    """
    Extrae múltiples pares de coordenadas de un texto multilínea.

    Estrategia:
    1. Dividir por líneas / saltos / ";"
    2. Por cada línea, extraer SOLO números plausibles (coordenadas)
       descartando IDs cortos como "V1:", "Punto 3:", etc.
    3. Si la línea tiene >= 2 números plausibles, formar par

    Retorna lista de tuplas [(val1, val2), ...]
    """
    if not text or not text.strip():
        return []

    pairs = []

    # Estrategia 1: por líneas (con separadores variados)
    line_splits = re.split(r'[\r\n;]+', text)
    line_splits = [l.strip() for l in line_splits if l.strip()]

    for line in line_splits:
        # Para múltiples líneas, ser ESTRICTO: solo aceptar números plausibles
        # como coordenadas. Esto descarta IDs como "V1", "Punto 3", etc.
        nums = _extract_numbers(line)
        plausible_in_line = [n for n in nums if _looks_like_coordinate(n)]

        # Si la línea tiene >= 2 plausibles, tomar los primeros 2
        if len(plausible_in_line) >= 2:
            pairs.append((plausible_in_line[0], plausible_in_line[1]))
            continue

        # Si no, intentar con la lógica completa por línea (keywords, etc.)
        pair = extract_number_pair(line)
        if pair is not None:
            # Verificar que ambos sean plausibles
            if _looks_like_coordinate(pair[0]) and _looks_like_coordinate(pair[1]):
                pairs.append(pair)

    if pairs:
        return pairs

    # Estrategia 2: todos los números plausibles del texto completo, en pares consecutivos
    nums = _extract_numbers(text)
    plausible = [n for n in nums if _looks_like_coordinate(n)]
    pairs = []
    for i in range(0, len(plausible) - 1, 2):
        pairs.append((plausible[i], plausible[i + 1]))
    return pairs


# ============================================================
# Identificación: ¿el texto es coordenada UTM o lat/lon?
# ============================================================

def guess_coordinate_type(val1, val2):
    """
    Adivina si (val1, val2) son lat/lon decimal o UTM (Easting/Northing).

    Reglas:
    - Si ambos < 200 en valor absoluto → lat/lon decimal
    - Si ambos > 10000 → UTM
    - Mixto → indeterminado
    """
    abs1, abs2 = abs(val1), abs(val2)

    if abs1 <= 90 and abs2 <= 180:
        return 'latlon'

    if 10000 < abs1 < 10000000 and 10000 < abs2 < 10000000:
        return 'utm'

    return 'unknown'


# ============================================================
# Tests para desarrollo
# ============================================================

if __name__ == '__main__':
    tests = [
        # Excel/tab
        ("485185\t8625060", (485185, 8625060)),
        # Coma simple
        ("485185, 8625060", (485185, 8625060)),
        # Espacio
        ("485185 8625060", (485185, 8625060)),
        # WhatsApp con keywords
        ("este 485185 norte 8625060", (485185, 8625060)),
        # Orden inverso con keywords
        ("Norte: 8625060, Este: 485185", (485185, 8625060)),
        # Mezclado con texto
        ("PEM Boca Manuani: 485185 8625060 (vertice 1)", (485185, 8625060)),
        # Multilínea con etiquetas
        ("Easting: 485185\nNorthing: 8625060", (485185, 8625060)),
        # Decimal lat/lon
        ("-12.5934, -69.1894", (-12.5934, -69.1894)),
        # WhatsApp típico
        ("la zona es -12,5934 -69,1894 cerca del río", (-12.5934, -69.1894)),
    ]

    print("=== TEST extract_number_pair ===")
    for input_text, expected in tests:
        result = extract_number_pair(input_text)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {input_text!r:55s} → {result}")

    print()
    print("=== TEST extract_multiple_pairs ===")
    multi = """
    V1: 485185, 8625060
    V2: 485200, 8624800
    V3: 484950, 8624900
    """
    pairs = extract_multiple_pairs(multi)
    for i, p in enumerate(pairs):
        print(f"  V{i+1}: {p}")
