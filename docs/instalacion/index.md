# Instalar el plugin

## Desde el repositorio oficial de QGIS (recomendado)

1. En QGIS, abra `Complementos → Administrar e instalar complementos...`
2. Pestaña **Todos**, busque `YF GIS Amazonia`
3. Pulse **Instalar complemento**

Aparecerá un menú **YF GIS Amazonia Tools** en la barra de menús y una barra de herramientas con los módulos principales.

Las actualizaciones llegan por el mismo administrador. Conviene mantener activada la comprobación automática en la pestaña **Configuración**: varias versiones han corregido errores que afectan a la exactitud de los resultados, no solo a la comodidad de uso.

## Desde un archivo ZIP

Útil en equipos sin acceso al repositorio de QGIS.

1. Descargue el ZIP desde [las versiones publicadas en GitHub](https://github.com/YuriCaller/YF_GIS_AMAZONIA/releases)
2. `Complementos → Administrar e instalar complementos... → Instalar a partir de ZIP`
3. Seleccione el archivo y pulse **Instalar complemento**

!!! warning "No descomprima el ZIP a mano"
    Instálelo con el administrador. Descomprimirlo directamente en la carpeta de complementos suele dejar un nivel de carpeta de más, y QGIS entonces no encuentra el plugin.

## Requisitos

| | |
|---|---|
| **QGIS** | 3.22 o superior. Compatible con QGIS 4.x (Qt6) |
| **Sistema** | Windows, Linux o macOS |
| **Permisos** | Ninguno especial. No requiere administrador |
| **Internet** | Solo para instalar y para los geoservicios oficiales |

El [post-proceso GNSS](../herramientas/gnss_postprocess.md) usa binarios de RTKLIB para Windows y no está disponible en Linux ni macOS. El resto de la suite funciona en los tres sistemas.

## Después de instalar

Nada más es obligatorio. Si más adelante una herramienta necesita un componente adicional, se lo pedirá en ese momento y podrá instalarlo desde el propio QGIS — vea [componentes opcionales](dependencias.md).

## Comprobar la instalación

`Complementos → YF GIS Amazonia Tools → Acerca de` muestra la versión instalada y el índice de las herramientas disponibles. Si el menú no aparece, revise que el plugin figure marcado en el administrador de complementos y consulte el registro de mensajes de QGIS, pestaña **Complementos**.

## Desinstalar

Desde el administrador de complementos, botón **Desinstalar complemento**. Los [componentes opcionales](dependencias.md) instalados en el perfil no se eliminan; si quiere retirarlos, borre la carpeta `python/dependencies` de su perfil de QGIS.
