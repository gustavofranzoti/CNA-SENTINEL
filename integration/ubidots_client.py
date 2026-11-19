from email.utils import parsedate_to_datetime
import logging
from math import isfinite
from queue import SimpleQueue
from sys import float_info
from threading import Event, Lock, Thread, TIMEOUT_MAX
from time import monotonic, time

from .config import DEFAULT_UBIDOTS_INTERVAL_SECONDS

ZONE_STATES = {"NORMAL": 0, "ATENCAO": 1, "ALERTA": 2, "CRITICO": 3, "ONLINE": 4, "OFFLINE": 5}
ZONE_EVENTS = {"ALERTA": 2, "CRITICO": 3}
DRONE_STATES = {
    "DISPONIVEL": 0,
    "DECOLANDO": 1,
    "EM_ROTA": 2,
    "NA_ZONA": 3,
    "INSPECIONANDO": 4,
    "RETORNANDO": 5,
    "CONCLUIDO": 6,
}
CATEGORY_CODES = {
    "z1_estado": ZONE_STATES,
    "z2_estado": ZONE_STATES,
    "z1_ultimo_evento": ZONE_EVENTS,
    "z2_ultimo_evento": ZONE_EVENTS,
    "estado_drone": DRONE_STATES,
    "zona_inspecionada": {"Z1": 1, "Z2": 2},
    "resultado_inspecao": {"SEM_RESULTADO": 0, "NADA_ENCONTRADO": 1, "ANOMALIA_CONFIRMADA": 2},
}


class UbidotsClient:
    def __init__(self, token=None, device=None, session=None, *, min_interval=DEFAULT_UBIDOTS_INTERVAL_SECONDS):
        if not isfinite(min_interval) or min_interval <= 0:
            raise ValueError("UBIDOTS_MIN_INTERVAL_SECONDS deve ser um número finito maior que zero")
        self.token, self.device, self.session = token, device, session
        self.min_interval = min_interval
        self.published = []
        self.log = logging.getLogger(__name__)
        self._queue = SimpleQueue()
        self._lock = Lock()
        self._closing = False
        self._stop = Event()
        self._worker = None

    def _format_payload(self, variables):
        payload = {}
        for label, value in variables.items():
            codes = CATEGORY_CODES.get(label)
            if codes is not None and isinstance(value, str):
                payload[label] = {"value": codes.get(value, -1), "context": {"label": value}}
            elif (codes is None and type(value) in (int, float)
                  and -float_info.max <= value <= float_info.max):
                payload[label] = value
            else:
                self.log.warning("Valor inválido para a variável Ubidots %s", label)
        return payload

    def publish(self, variables: dict):
        """Retorna True quando o payload entra na fila HTTP."""
        payload = self._format_payload(variables)
        if not payload:
            return False
        if not self.token or not self.device:
            self.log.info("Ubidots não configurado; payload apenas local: %s", payload)
            self.published.append(payload)
            return False

        with self._lock:
            if self._closing:
                return False
            self._queue.put_nowait(payload)
            if self._worker is None:
                self._worker = Thread(target=self._send_queued, name="ubidots-sender", daemon=True)
                self._worker.start()
        self.log.info("Atualização Ubidots enfileirada (%d variáveis)", len(payload))
        return True

    def close(self, timeout=2.0):
        with self._lock:
            if not self._closing:
                self._closing = True
                if self._worker is not None:
                    self._queue.put_nowait(None)
            worker = self._worker
        if worker is not None:
            try:
                worker.join(timeout)
            finally:
                self._stop.set()
            if worker.is_alive():
                self.log.warning("Prazo de encerramento do Ubidots atingido. Há atualizações pendentes na memória.")

    def _send_queued(self):
        next_attempt = 0.0
        while not self._stop.is_set():
            payload = self._queue.get()
            if payload is None:
                return
            backoff = min(self.min_interval, 60.0)
            while not self._stop.is_set():
                delay = next_attempt - monotonic()
                if delay > 0:
                    self.log.info("Envio Ubidots aguardando %.2f s pelo limite de frequência", delay)
                    if self._stop.wait(min(delay, TIMEOUT_MAX)):
                        return
                    continue
                started_at, retry_after = self._post(payload)
                next_attempt = started_at + self.min_interval
                if retry_after is None:
                    break
                delay = max(self.min_interval, backoff, retry_after)
                self.log.info("Atualização Ubidots será tentada novamente em %.2f s", delay)
                next_attempt = monotonic() + delay
                backoff = min(backoff * 2, 60.0)

    @staticmethod
    def _retry_after_seconds(header):
        if not header:
            return 0.0
        try:
            seconds = float(header)
        except ValueError:
            try:
                seconds = parsedate_to_datetime(header).timestamp() - time()
            except (ValueError, OSError, OverflowError):
                return 0.0
        return max(0.0, seconds) if isfinite(seconds) else 0.0

    def _post(self, payload):
        """Retorna o instante de envio e a espera solicitada para uma retentativa."""
        import requests

        if self.session is None:
            self.session = requests
        url = f"https://industrial.api.ubidots.com/api/v1.6/devices/{self.device}"
        started_at = monotonic()
        try:
            response = self.session.post(
                url, headers={"X-Auth-Token": self.token, "Content-Type": "application/json"},
                json=payload, timeout=5, allow_redirects=False,
            )
        except requests.RequestException as exc:
            self.log.warning("Falha na comunicação com o Ubidots (%s)", type(exc).__name__)
            return started_at, 0.0
        if response.status_code == 429 or 500 <= response.status_code < 600:
            self.log.warning("Ubidots retornou HTTP %s. Atualização mantida no início da fila.", response.status_code)
            return started_at, self._retry_after_seconds(response.headers.get("Retry-After"))
        if not 200 <= response.status_code < 300:
            safe_body = response.text.replace(self.token, "[redigido]")[:500]
            self.log.warning("Ubidots retornou HTTP %s. Resposta %r", response.status_code, safe_body)
            return started_at, None
        self.published.append(payload)
        self.log.info("Atualização Ubidots enviada (%d variáveis)", len(payload))
        return started_at, None
