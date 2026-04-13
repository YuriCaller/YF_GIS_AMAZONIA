# gnss_engine package
# Los procesadores (ppk/ppp) dependen de Qt y se importan bajo demanda
# desde la UI para no romper imports en entornos sin QGIS.
from .coord_converter import CoordConverter, BaseCoords
from .config_builder  import ConfigBuilder, ProcessingParams
