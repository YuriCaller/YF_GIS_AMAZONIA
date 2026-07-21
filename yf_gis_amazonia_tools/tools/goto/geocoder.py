# -*- coding: utf-8 -*-
"""
YF Go-To Tool - Geocoder
Búsqueda de lugares por nombre usando Nominatim (OpenStreetMap).

Para uso intensivo se recomienda usar un servidor Nominatim propio
o un servicio comercial. Aquí usamos el servidor público con respeto
a la política de uso (https://operations.osmfoundation.org/policies/nominatim/).

Autor: Yuri Caller - TUCSA / gis-amazonia.pe
"""

import logging
import json
from qgis.PyQt.QtCore import QObject, QUrl, QUrlQuery, pyqtSignal, QTimer
from qgis.PyQt.QtNetwork import (
    QNetworkAccessManager, QNetworkRequest, QNetworkReply
)


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "YF-GoTo-Tool/1.0 (gis-amazonia.pe)"


class NominatimGeocoder(QObject):
    """
    Geocoder asíncrono usando Nominatim.

    Uso:
        geocoder.resultsReady.connect(handler)
        geocoder.search("Puerto Maldonado")
    """

    resultsReady = pyqtSignal(list)     # list of dicts
    searchError = pyqtSignal(str)
    searchStarted = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.nam = QNetworkAccessManager(self)
        self._current_reply = None

    def search(self, query, country_codes='pe', limit=10):
        """
        Busca lugares por nombre.

        Args:
            query: Texto de búsqueda
            country_codes: Códigos ISO de países separados por coma (default 'pe')
                          Pasar '' para búsqueda mundial
            limit: Número máximo de resultados
        """
        if not query or not query.strip():
            self.searchError.emit("Consulta vacía")
            return

        # Cancelar búsqueda anterior si existe
        if self._current_reply is not None:
            try:
                self._current_reply.abort()
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
            self._current_reply = None

        url = QUrl(NOMINATIM_URL)
        params = QUrlQuery()
        params.addQueryItem("q", query.strip())
        params.addQueryItem("format", "json")
        params.addQueryItem("limit", str(limit))
        params.addQueryItem("addressdetails", "1")
        if country_codes:
            params.addQueryItem("countrycodes", country_codes)
        url.setQuery(params)

        request = QNetworkRequest(url)
        request.setRawHeader(b"User-Agent", USER_AGENT.encode())
        request.setRawHeader(b"Accept-Language", b"es,en")

        self.searchStarted.emit()
        self._current_reply = self.nam.get(request)
        self._current_reply.finished.connect(self._on_finished)

    def _on_finished(self):
        reply = self._current_reply
        if reply is None:
            return

        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self.searchError.emit(f"Error de red: {reply.errorString()}")
                return

            raw = bytes(reply.readAll()).decode('utf-8', errors='replace')
            data = json.loads(raw)

            results = []
            for item in data:
                try:
                    lat = float(item.get('lat'))
                    lon = float(item.get('lon'))
                    name = item.get('display_name', '')
                    place_type = item.get('type', '')
                    category = item.get('class', '')
                    importance = float(item.get('importance', 0))
                    results.append({
                        'lat': lat,
                        'lon': lon,
                        'name': name,
                        'type': place_type,
                        'category': category,
                        'importance': importance,
                    })
                except (ValueError, TypeError):
                    continue  # nosec B112 - entrada malformada: se omite a proposito

            self.resultsReady.emit(results)
        except json.JSONDecodeError as e:
            self.searchError.emit(f"Error parseando respuesta: {e}")
        except Exception as e:
            self.searchError.emit(f"Error inesperado: {e}")
        finally:
            reply.deleteLater()
            self._current_reply = None

    def cancel(self):
        if self._current_reply is not None:
            try:
                self._current_reply.abort()
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
            self._current_reply = None
