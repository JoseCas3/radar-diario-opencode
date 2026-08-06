from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import date
from io import BytesIO

import requests
from pypdf import PdfReader
from pypdf.errors import PyPdfError

logger = logging.getLogger(__name__)

BASE_URL = "https://www.diariooficial.gob.sv"
TIMEOUT_SEGUNDOS = 30
MAX_REINTENTOS = 3
BACKOFF_INICIAL = 2
MAX_CARACTERES_PDF = 1_000_000


@dataclass
class PublicacionDiario:
    id: int
    fecha_inicio: str
    nombre_archivo: str


class DiarioOficialScraper:
    """Extrae el texto del Diario Oficial de El Salvador para la fecha solicitada."""

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: int = TIMEOUT_SEGUNDOS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._sesion = requests.Session()
        self._sesion.headers.update({"User-Agent": "RadarDiarioOficial/1.0"})

    def obtener_texto_diario(
        self,
        fecha: date | None = None,
        max_caracteres: int = MAX_CARACTERES_PDF,
    ) -> str | None:
        """Obtiene el texto completo del Diario Oficial para la fecha dada (hoy por defecto).

        Retorna None si no existe publicación para la fecha solicitada.
        """
        fecha_obj = fecha or date.today()
        publicacion = self._buscar_publicacion(fecha_obj)
        if publicacion is None:
            logger.info(
                "No hay publicación del Diario Oficial para %s", fecha_obj.isoformat()
            )
            return None
        pdf_bytes = self._descargar_pdf(publicacion.id)
        paginas = self._extraer_texto_pdf(pdf_bytes)
        texto = self._unir_limitado(paginas, max_caracteres)
        logger.info(
            "Texto extraído del Diario Oficial %s: %d caracteres en %d páginas",
            fecha_obj.isoformat(),
            len(texto),
            len(paginas),
        )
        return texto

    def obtener_texto_ultima_publicacion(
        self,
        max_caracteres: int = MAX_CARACTERES_PDF,
    ) -> tuple[str, date] | None:
        """Obtiene el texto de la publicación más reciente disponible.

        Retorna una tupla (texto, fecha_publicacion) o None si no hay publicaciones.
        """
        hoy = date.today()
        publicacion = self._buscar_ultima_publicacion(hoy.year)
        if publicacion is None and hoy.year > 2020:
            publicacion = self._buscar_ultima_publicacion(hoy.year - 1)
        if publicacion is None:
            logger.info("No se encontró ninguna publicación disponible")
            return None
        fecha_pub = date.fromisoformat(publicacion.fecha_inicio)
        pdf_bytes = self._descargar_pdf(publicacion.id)
        paginas = self._extraer_texto_pdf(pdf_bytes)
        texto = self._unir_limitado(paginas, max_caracteres)
        logger.info(
            "Texto extraído de última publicación (%s): %d caracteres en %d páginas",
            publicacion.fecha_inicio,
            len(texto),
            len(paginas),
        )
        return texto, fecha_pub

    def _buscar_ultima_publicacion(self, year: int) -> PublicacionDiario | None:
        try:
            meses = self._obtener_meses_disponibles(year)
        except Exception:
            logger.warning("No se pudieron obtener meses del año %d", year)
            return None
        if not meses:
            return None
        for mes in sorted(meses, reverse=True):
            diarios = self._obtener_diarios_disponibles(year, mes)
            if not diarios:
                logger.info("Mes %d/%d sin diarios disponibles", mes, year)
                continue
            ultima = sorted(
                diarios, key=lambda d: d.fecha_inicio, reverse=True
            )[0]
            logger.info(
                "Última publicación encontrada: ID=%s, %s",
                ultima.id,
                ultima.nombre_archivo,
            )
            return ultima
        return None

    def _buscar_publicacion(self, fecha_obj: date) -> PublicacionDiario | None:
        meses = self._obtener_meses_disponibles(fecha_obj.year)
        if fecha_obj.month not in meses:
            logger.info(
                "El mes %d/%d no tiene publicaciones en el Diario Oficial",
                fecha_obj.month,
                fecha_obj.year,
            )
            return None
        diarios = self._obtener_diarios_disponibles(fecha_obj.year, fecha_obj.month)
        fecha_str = fecha_obj.isoformat()
        for diario in diarios:
            if diario.fecha_inicio == fecha_str:
                logger.info(
                    "Publicación encontrada: ID=%d, %s",
                    diario.id,
                    diario.nombre_archivo,
                )
                return diario
        return None

    def _obtener_meses_disponibles(self, year: int) -> list[int]:
        try:
            respuesta = self._reintentar_http(
                "meses-disponibles",
                f"{self._base_url}/api/v1/meses-disponibles",
                "POST",
                json={"year": year},
            )
            return [int(item["month"]) for item in respuesta.json()]
        except (requests.RequestException, KeyError, ValueError) as e:
            logger.error(
                "Error al consultar meses disponibles año=%d: %s", year, e
            )
            raise

    def _obtener_diarios_disponibles(
        self, year: int, month: int
    ) -> list[PublicacionDiario]:
        try:
            respuesta = self._reintentar_http(
                "diarios-disponibles",
                f"{self._base_url}/api/v1/diarios-disponibles",
                "POST",
                data={"year": str(year), "month": str(month)},
            )
            datos = respuesta.json()
        except (requests.RequestException, KeyError, ValueError, TypeError) as e:
            logger.error(
                "Error al consultar diarios disponibles año=%d mes=%d: %s",
                year,
                month,
                e,
            )
            raise
        return [
            PublicacionDiario(
                id=item["Id"],
                fecha_inicio=item["FechaInicio"],
                nombre_archivo=item["NombreArchivo"],
            )
            for item in datos
        ]

    def _descargar_pdf(self, id_publicacion: int) -> bytes:
        url = f"{self._base_url}/seleccion/{id_publicacion}"
        try:
            respuesta = self._reintentar_http(
                "descargar-pdf", url, "GET"
            )
            logger.info("PDF descargado: %d bytes", len(respuesta.content))
            return respuesta.content
        except requests.RequestException as e:
            logger.error("Error al descargar PDF ID=%d: %s", id_publicacion, e)
            raise

    def _reintentar_http(self, operacion: str, url: str, metodo: str, **kwargs):
        """Ejecuta una petición HTTP con reintentos y backoff exponencial."""
        for intento in range(1, MAX_REINTENTOS + 1):
            try:
                respuesta = self._sesion.request(
                    metodo, url, timeout=self._timeout, **kwargs
                )
                respuesta.raise_for_status()
                return respuesta
            except requests.RequestException as e:
                if intento < MAX_REINTENTOS:
                    espera = BACKOFF_INICIAL**intento
                    logger.warning(
                        "Error en %s (intento %d/%d): %s. Reintentando en %ds...",
                        operacion,
                        intento,
                        MAX_REINTENTOS,
                        e,
                        espera,
                    )
                    time.sleep(espera)
                else:
                    logger.error(
                        "Fallaron los %d intentos en %s: %s",
                        MAX_REINTENTOS,
                        operacion,
                        e,
                    )
                    raise

    def _extraer_texto_pdf(self, pdf_bytes: bytes) -> list[str]:
        """Extrae el texto de cada página de un PDF en memoria usando pypdf.

        Retorna una lista con el texto limpio de cada página que sí tiene contenido.
        """
        try:
            with BytesIO(pdf_bytes) as stream:
                reader = PdfReader(stream)
                paginas: list[str] = []
                for numero, pagina in enumerate(reader.pages, start=1):
                    cruda = pagina.extract_text() or ""
                    limpia = self._limpiar_texto(cruda)
                    if limpia:
                        paginas.append(limpia)
                    else:
                        logger.warning(
                            "Página %d sin texto extraíble (%d de %d totales)",
                            numero,
                            len(paginas),
                            len(reader.pages),
                        )
                logger.info(
                    "Páginas extraídas del PDF: %d de %d totales",
                    len(paginas),
                    len(reader.pages),
                )
                return paginas
        except (ValueError, TypeError, OSError, PyPdfError) as e:
            logger.error("Error al extraer texto del PDF: %s", e)
            raise

    def _limpiar_texto(self, texto: str) -> str:
        """Limpia el texto de una página: une palabras partidas, normaliza blancos y quita ruido.

        Solo elimina líneas de ruido seguro (números de página y membretes), nunca contenido único.
        """
        lineas_filtradas: list[str] = []
        for linea in texto.splitlines():
            linea_limpia = linea.strip()
            if not linea_limpia or self._es_ruido_repetido(linea_limpia):
                continue
            lineas_filtradas.append(linea_limpia)
        unido = "\n".join(lineas_filtradas)
        unido = re.sub(r"[ \t]{2,}", " ", unido)
        unido = re.sub(r"([a-záéíóúüñ])-\n([a-záéíóúüñ])", r"\1\2", unido)
        return unido

    def _es_ruido_repetido(self, linea: str) -> bool:
        """Determina si una línea es ruido repetitivo del membrete del Diario Oficial."""
        if re.fullmatch(r"\d{1,4}", linea):
            return True
        if re.fullmatch(r"p[áa]g(?:\.|ina)?\.?\s*\d{1,4}", linea, re.IGNORECASE):
            return True
        if linea in ("REPÚBLICA DE EL SALVADOR", "REPUBLICA DE EL SALVADOR"):
            return True
        if linea == "DIARIO OFICIAL":
            return True
        return False

    def _unir_limitado(
        self, paginas: list[str], max_caracteres: int = MAX_CARACTERES_PDF
    ) -> str:
        """Une páginas completas hasta alcanzar max_caracteres, sin partir una página.

        Siempre incluye al menos la primera página; recorta el resto de forma entera.
        """
        partes: list[str] = []
        total = 0
        for pagina in paginas:
            if partes and total + len(pagina) + 1 > max_caracteres:
                logger.warning(
                    "Texto recortado: %d de %d páginas (límite %d caracteres)",
                    len(partes),
                    len(paginas),
                    max_caracteres,
                )
                break
            partes.append(pagina)
            total += len(pagina) + 1
        return "\n".join(partes)
