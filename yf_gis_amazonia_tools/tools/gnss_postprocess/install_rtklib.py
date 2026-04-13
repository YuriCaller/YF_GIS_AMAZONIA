#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
install_rtklib.py
Descarga el binario rnx2rtkp de RTKLIB y lo coloca en rtklib_bin/.
Detecta automáticamente el sistema operativo (Windows / Linux / macOS).

Uso (desde consola Python de QGIS o terminal):
    python install_rtklib.py

O desde QGIS Python Console:
    import subprocess, sys
    subprocess.run([sys.executable, '/ruta/al/plugin/install_rtklib.py'])
"""
import os
import sys
import stat
import platform
import shutil
import zipfile
import tarfile
import urllib.request

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_DIR    = os.path.join(PLUGIN_DIR, 'rtklib_bin')

# Binarios compilados de RTKLIB (rtklibexplorer fork b34g — más preciso que original)
SOURCES = {
    'Windows': {
        'url':   'https://github.com/tomojitakasu/RTKLIB/releases/download/v2.4.3-b34/RTKLIB_bin_2.4.3b34.zip',
        'exe':   'rnx2rtkp.exe',
        'inner': 'bin/rnx2rtkp.exe',
        'type':  'zip',
    },
    'Linux': {
        'url':   'https://github.com/rtklibexplorer/RTKLIB/releases/download/b34g/rtklib_b34g_linux_x64.tar.gz',
        'exe':   'rnx2rtkp',
        'inner': 'rnx2rtkp',
        'type':  'tar',
    },
    'Darwin': {
        'url':   'https://github.com/rtklibexplorer/RTKLIB/releases/download/b34g/rtklib_b34g_macos.tar.gz',
        'exe':   'rnx2rtkp',
        'inner': 'rnx2rtkp',
        'type':  'tar',
    },
}


def _progress(count, block, total):
    pct = min(count * block / total * 100, 100)
    bar = '█' * int(pct / 5) + '░' * (20 - int(pct / 5))
    sys.stdout.write(f'\r  [{bar}] {pct:.0f}%')
    sys.stdout.flush()


def install():
    plat = platform.system()
    info = SOURCES.get(plat)
    if not info:
        print(f'❌ Plataforma no soportada: {plat}')
        sys.exit(1)

    os.makedirs(BIN_DIR, exist_ok=True)
    dest = os.path.join(BIN_DIR, info['exe'])

    if os.path.isfile(dest):
        print(f'✅ Ya existe: {dest}')
        print('   Para reinstalar, borra el archivo y vuelve a ejecutar.')
        return dest

    print(f'⬇  Descargando RTKLIB para {plat}...')
    print(f'   URL: {info["url"]}')

    tmp = os.path.join(BIN_DIR, '_tmp_rtklib_download')
    try:
        urllib.request.urlretrieve(info['url'], tmp, reporthook=_progress)
        print()  # nueva línea tras la barra
    except Exception as ex:
        print(f'\n❌ Error descargando: {ex}')
        print('   Descarga manualmente desde:')
        print(f'   {info["url"]}')
        print(f'   Y copia "{info["exe"]}" a: {BIN_DIR}')
        sys.exit(1)

    print('📦 Extrayendo binario...')
    try:
        if info['type'] == 'zip':
            with zipfile.ZipFile(tmp, 'r') as z:
                # Buscar el exe dentro del zip
                candidates = [n for n in z.namelist() if n.endswith(info['exe'])]
                if not candidates:
                    raise FileNotFoundError(f'{info["exe"]} no encontrado en el ZIP')
                member = candidates[0]
                with z.open(member) as src, open(dest, 'wb') as dst:
                    shutil.copyfileobj(src, dst)

        elif info['type'] == 'tar':
            with tarfile.open(tmp, 'r:gz') as t:
                candidates = [m for m in t.getmembers()
                              if m.name.endswith(info['exe']) and m.isfile()]
                if not candidates:
                    raise FileNotFoundError(f'{info["exe"]} no encontrado en el TAR')
                member = candidates[0]
                member.name = info['exe']  # extraer con nombre limpio
                t.extract(member, BIN_DIR)

    except Exception as ex:
        print(f'❌ Error extrayendo: {ex}')
        if os.path.exists(tmp):
            os.remove(tmp)
        sys.exit(1)

    os.remove(tmp)

    # Permisos de ejecución en Linux/macOS
    if plat != 'Windows':
        current = os.stat(dest).st_mode
        os.chmod(dest, current | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        print(f'✅ Permisos de ejecución aplicados.')

    # Verificar
    if os.path.isfile(dest):
        size = os.path.getsize(dest)
        print(f'✅ RTKLIB instalado: {dest}  ({size/1024:.0f} KB)')
    else:
        print('❌ El archivo no se generó correctamente.')
        sys.exit(1)

    return dest


def verify():
    """Verifica que el binario existe y es ejecutable."""
    plat = platform.system()
    exe  = 'rnx2rtkp.exe' if plat == 'Windows' else 'rnx2rtkp'
    dest = os.path.join(BIN_DIR, exe)

    if not os.path.isfile(dest):
        # Buscar en PATH del sistema
        system_bin = shutil.which('rnx2rtkp')
        if system_bin:
            print(f'✅ rnx2rtkp encontrado en PATH: {system_bin}')
            return system_bin
        print(f'❌ rnx2rtkp no encontrado. Ejecuta install_rtklib.py')
        return None

    print(f'✅ Binario bundled: {dest}')
    return dest


if __name__ == '__main__':
    if '--verify' in sys.argv:
        verify()
    else:
        install()
