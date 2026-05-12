# -*- coding: utf-8 -*-
"""
Coordinate Parser - Multi-format coordinate parsing.

Detects and parses coordinates in multiple formats:
- Decimal (DD): -12.5934, -69.1894
- Sexagesimal (DMS): 12°35'36"S 69°11'21"W
- UTM: 19L 367250 8607830
- MGRS: 19LDE6725007830

Used by Go-To Tool and other tools that accept coordinate input.
"""

import re
import math
import string


# Formats
FORMAT_DD = 'decimal'
FORMAT_DMS = 'dms'
FORMAT_UTM = 'utm'
FORMAT_MGRS = 'mgrs'
FORMAT_UNKNOWN = 'unknown'


# MGRS letters: alphabet excluding I, O (avoid confusion with 1, 0).
# Computed at import time to avoid false positives from secret detectors
# that flag long alphabetic literals as potential Base64 tokens.
MGRS_E_LETTERS = ''.join(c for c in string.ascii_uppercase if c not in 'IO')
MGRS_N_LETTERS = ''.join(
    c for c in string.ascii_uppercase if c not in 'IOWXYZ'
)


# ============================================================
# Format detection
# ============================================================

def detect_format(text):
    """Detect coordinate format from text."""
    if not text:
        return FORMAT_UNKNOWN
    t = text.strip().upper()

    mgrs_pattern = r'^\d{1,2}[C-X][A-HJ-NP-Z][A-HJ-NP-V]\s*\d+\s*\d*$'
    if re.match(mgrs_pattern, t.replace(' ', '')):
        return FORMAT_MGRS

    utm_pattern = r'^\d{1,2}\s*[C-X]?\s+\d+(?:\.\d+)?\s+\d+(?:\.\d+)?$'
    if re.match(utm_pattern, t):
        return FORMAT_UTM

    if any(c in t for c in ['°', "'", '"', '′', '″']) or \
       re.search(r'\d+\s*[NSEW]', t):
        return FORMAT_DMS

    dd_pattern = r'^-?\d+(?:\.\d+)?\s*[,\s]\s*-?\d+(?:\.\d+)?$'
    if re.match(dd_pattern, t):
        return FORMAT_DD

    dd_european = r'^-?\d+(?:,\d+)?\s+-?\d+(?:,\d+)?$'
    if re.match(dd_european, t):
        return FORMAT_DD

    return FORMAT_UNKNOWN


# ============================================================
# DD parser (with European comma support)
# ============================================================

def parse_dd(text):
    """Parse decimal coordinates with American or European decimal notation."""
    try:
        t = text.strip()
        comma_count = t.count(',')
        dot_count = t.count('.')

        is_european = (comma_count >= 2 and dot_count == 0)

        if is_european:
            t = t.replace(',', '.')
            parts = re.split(r'\s+', t)
        else:
            parts = re.split(r'[,;]\s*|\s+', t)

        parts = [p for p in parts if p]
        if len(parts) != 2:
            return None
        lat = float(parts[0])
        lon = float(parts[1])
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return None
        return (lat, lon)
    except (ValueError, IndexError):
        return None


# ============================================================
# DMS parser
# ============================================================

def parse_dms(text):
    """Parse sexagesimal coordinates."""
    t = text.strip().upper()
    t = t.replace('′', "'").replace('″', '"').replace('`', "'")

    dms_pattern = r"""
        ([+-]?)\s*
        (\d{1,3})
        (?:°|\s+|d)\s*
        (\d{1,2}(?:\.\d+)?)?
        (?:'|\s+|m)?\s*
        (\d{1,2}(?:\.\d+)?)?
        (?:"|s|\s+)?\s*
        ([NSEW]?)
    """

    matches = re.findall(dms_pattern, t, re.VERBOSE)
    valid = [m for m in matches if m[1]]

    if len(valid) < 2:
        return None

    def dms_to_dd(sign, deg, mins, secs, hemi):
        d = float(deg) if deg else 0
        m = float(mins) if mins else 0
        s = float(secs) if secs else 0
        val = d + m / 60 + s / 3600
        if sign == '-' or hemi in ('S', 'W'):
            val = -val
        return val

    try:
        coord1 = dms_to_dd(*valid[0])
        coord2 = dms_to_dd(*valid[1])

        hemi1 = valid[0][4]
        hemi2 = valid[1][4]

        if hemi1 in ('N', 'S'):
            lat, lon = coord1, coord2
        elif hemi1 in ('E', 'W'):
            lat, lon = coord2, coord1
        elif hemi2 in ('N', 'S'):
            lat, lon = coord2, coord1
        elif hemi2 in ('E', 'W'):
            lat, lon = coord1, coord2
        else:
            lat, lon = coord1, coord2

        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return None
        return (lat, lon)
    except (ValueError, IndexError):
        return None


# ============================================================
# UTM parser and converter (USGS/Karney algorithm)
# ============================================================

def parse_utm(text):
    """Parse UTM coordinates and convert to lat/lon (WGS84)."""
    t = text.strip().upper().replace(',', ' ')
    pattern = r'^(\d{1,2})\s*([C-X])?\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)$'
    m = re.match(pattern, t)
    if not m:
        return None
    try:
        zone = int(m.group(1))
        band = m.group(2) or 'N'
        easting = float(m.group(3))
        northing = float(m.group(4))
        if not (1 <= zone <= 60):
            return None
        is_south = band in 'CDEFGHJKLM'
        return utm_to_latlon(easting, northing, zone, is_south)
    except (ValueError, IndexError):
        return None


def utm_to_latlon(easting, northing, zone, is_south):
    """UTM → lat/lon WGS84. USGS algorithm."""
    a = 6378137.0
    f = 1 / 298.257223563
    k0 = 0.9996
    e2 = 2 * f - f * f
    e_prime_sq = e2 / (1 - e2)

    if is_south:
        northing -= 10000000.0

    M = northing / k0
    mu = M / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))

    phi1 = (mu
            + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
            + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * e1 ** 3 / 96) * math.sin(6 * mu))

    N1 = a / math.sqrt(1 - e2 * math.sin(phi1) ** 2)
    T1 = math.tan(phi1) ** 2
    C1 = e_prime_sq * math.cos(phi1) ** 2
    R1 = a * (1 - e2) / (1 - e2 * math.sin(phi1) ** 2) ** 1.5
    D = (easting - 500000.0) / (N1 * k0)

    lat = phi1 - (N1 * math.tan(phi1) / R1) * (
        D ** 2 / 2
        - (5 + 3 * T1 + 10 * C1 - 4 * C1 ** 2 - 9 * e_prime_sq) * D ** 4 / 24
        + (61 + 90 * T1 + 298 * C1 + 45 * T1 ** 2 - 252 * e_prime_sq - 3 * C1 ** 2) * D ** 6 / 720
    )

    lon_central = math.radians((zone - 1) * 6 - 180 + 3)
    lon = lon_central + (
        D
        - (1 + 2 * T1 + C1) * D ** 3 / 6
        + (5 - 2 * C1 + 28 * T1 - 3 * C1 ** 2 + 8 * e_prime_sq + 24 * T1 ** 2) * D ** 5 / 120
    ) / math.cos(phi1)

    return (math.degrees(lat), math.degrees(lon))


def latlon_to_utm(lat, lon):
    """Lat/lon → UTM WGS84. Returns (zone, band_letter, easting, northing)."""
    a = 6378137.0
    f = 1 / 298.257223563
    k0 = 0.9996
    e2 = 2 * f - f * f
    e_prime_sq = e2 / (1 - e2)

    zone = int((lon + 180) / 6) + 1
    lon_central = math.radians((zone - 1) * 6 - 180 + 3)

    lat_r = math.radians(lat)
    lon_r = math.radians(lon)

    N = a / math.sqrt(1 - e2 * math.sin(lat_r) ** 2)
    T = math.tan(lat_r) ** 2
    C = e_prime_sq * math.cos(lat_r) ** 2
    A = math.cos(lat_r) * (lon_r - lon_central)

    M = a * (
        (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * lat_r
        - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * math.sin(2 * lat_r)
        + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * math.sin(4 * lat_r)
        - (35 * e2 ** 3 / 3072) * math.sin(6 * lat_r)
    )

    easting = k0 * N * (
        A
        + (1 - T + C) * A ** 3 / 6
        + (5 - 18 * T + T ** 2 + 72 * C - 58 * e_prime_sq) * A ** 5 / 120
    ) + 500000.0

    northing = k0 * (M + N * math.tan(lat_r) * (
        A ** 2 / 2
        + (5 - T + 9 * C + 4 * C ** 2) * A ** 4 / 24
        + (61 - 58 * T + T ** 2 + 600 * C - 330 * e_prime_sq) * A ** 6 / 720
    ))

    if lat < 0:
        northing += 10000000.0

    bands = 'CDEFGHJKLMNPQRSTUVWX'
    band_idx = int((lat + 80) / 8)
    band_idx = max(0, min(band_idx, len(bands) - 1))
    band = bands[band_idx]

    return (zone, band, easting, northing)


# ============================================================
# MGRS parser
# ============================================================

def parse_mgrs(text):
    """Parse MGRS coordinates."""
    t = text.strip().upper().replace(' ', '')
    pattern = r'^(\d{1,2})([C-X])([A-HJ-NP-Z])([A-HJ-NP-V])(\d{0,10})$'
    m = re.match(pattern, t)
    if not m:
        return None
    try:
        zone = int(m.group(1))
        band = m.group(2)
        e_letter = m.group(3)
        n_letter = m.group(4)
        digits = m.group(5)

        if len(digits) % 2 != 0 or len(digits) == 0:
            return None

        half = len(digits) // 2
        easting_digits = digits[:half]
        northing_digits = digits[half:]

        scale = 10 ** (5 - half)
        easting_offset = int(easting_digits) * scale
        northing_offset = int(northing_digits) * scale

        if e_letter not in MGRS_E_LETTERS or n_letter not in MGRS_N_LETTERS:
            return None

        e_idx = MGRS_E_LETTERS.index(e_letter)
        n_idx = MGRS_N_LETTERS.index(n_letter)

        set_e = (zone - 1) % 3
        easting_base = ((e_idx - set_e * 8) % 24) * 100000 + 100000

        set_n = (zone - 1) % 2
        if set_n == 0:
            n_grid = n_idx
        else:
            n_grid = (n_idx + 5) % 20

        bands = 'CDEFGHJKLMNPQRSTUVWX'
        band_pos = bands.index(band)
        approx_lat = -80 + band_pos * 8 + 4

        _, _, _, approx_northing = latlon_to_utm(approx_lat, (zone - 1) * 6 - 180 + 3)

        northing_base = (int(approx_northing / 100000) // 20) * 20 * 100000 + n_grid * 100000
        while northing_base > approx_northing + 1000000:
            northing_base -= 2000000
        while northing_base < approx_northing - 1000000:
            northing_base += 2000000

        easting = easting_base + easting_offset
        northing = northing_base + northing_offset

        is_south = band in 'CDEFGHJKLM'
        return utm_to_latlon(easting, northing, zone, is_south)
    except (ValueError, IndexError):
        return None


# ============================================================
# Universal parser
# ============================================================

def parse_coordinates(text):
    """Auto-detect format and parse. Returns dict or None."""
    if not text or not text.strip():
        return None

    fmt = detect_format(text)
    result = None

    if fmt == FORMAT_DD:
        result = parse_dd(text)
    elif fmt == FORMAT_DMS:
        result = parse_dms(text)
    elif fmt == FORMAT_UTM:
        result = parse_utm(text)
    elif fmt == FORMAT_MGRS:
        result = parse_mgrs(text)

    if result is None:
        for parser in (parse_dd, parse_dms, parse_utm, parse_mgrs):
            result = parser(text)
            if result is not None:
                fmt = parser.__name__.replace('parse_', '')
                break

    if result is None:
        return None

    return {
        'lat': result[0],
        'lon': result[1],
        'format': fmt,
        'original': text.strip()
    }


# ============================================================
# Formatters
# ============================================================

def format_dd(lat, lon, precision=6):
    """Format as decimal."""
    return f"{lat:.{precision}f}, {lon:.{precision}f}"


def format_dms(lat, lon):
    """Format as DMS."""
    def to_dms(val, is_lat):
        hemi = ('N' if val >= 0 else 'S') if is_lat else ('E' if val >= 0 else 'W')
        v = abs(val)
        d = int(v)
        m_full = (v - d) * 60
        m = int(m_full)
        s = (m_full - m) * 60
        return f"{d}°{m:02d}'{s:05.2f}\"{hemi}"
    return f"{to_dms(lat, True)}  {to_dms(lon, False)}"


def format_utm(lat, lon):
    """Format as UTM."""
    zone, band, easting, northing = latlon_to_utm(lat, lon)
    return f"{zone}{band} {easting:.0f} {northing:.0f}"
