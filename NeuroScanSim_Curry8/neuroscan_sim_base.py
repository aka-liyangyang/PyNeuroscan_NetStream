from __future__ import annotations

import math
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import numpy as np


REQUEST_CHANNEL_INFO = 3
REQUEST_BASIC_INFO = 6
REQUEST_STREAMING_START = 8
REQUEST_STREAMING_STOP = 9

CODE_INFO = 1
CODE_EEG = 2
CODE_EVENT = 3
CODE_KEEPALIVE = 4

CURRY9_EVENT_STRUCT_BYTES = 536


def _encode_u16_be(value: int) -> bytes:
    return int(value).to_bytes(2, byteorder="big", signed=False)


def _encode_u32_be(value: int) -> bytes:
    return int(value).to_bytes(4, byteorder="big", signed=False)


def build_packet_header(code: int, request: int, start_sample: int, body_size: int) -> bytes:
    return b"CTRL" + _encode_u16_be(code) + _encode_u16_be(request) + _encode_u32_be(start_sample) + _encode_u32_be(body_size) + _encode_u32_be(body_size)


def build_basic_info_body(channel_count: int, sample_rate: int, data_size: int) -> bytes:
    return (
        np.array([16], dtype="<u4").tobytes()
        + np.array([channel_count], dtype="<u4").tobytes()
        + np.array([sample_rate], dtype="<u4").tobytes()
        + np.array([data_size], dtype="<u4").tobytes()
    )


def build_channel_info_body(channel_count: int, label_prefix: str) -> bytes:
    block_size = 120
    body = bytearray(block_size * channel_count)
    for index in range(channel_count):
        label = f"{label_prefix}{index + 1}"[:6].encode("ascii", errors="ignore")
        start = index * block_size + 4
        body[start:start + len(label)] = label
    return bytes(body)


def build_curry8_event_body(event_type: int, start_event: int) -> bytes:
    body = bytearray(12)
    body[0:4] = np.array([event_type], dtype="<u4").tobytes()
    body[8:12] = np.array([start_event], dtype="<u4").tobytes()
    return bytes(body)


def build_curry9_event_body(event_type: int, latency: int, end_latency: int, annotation: str) -> bytes:
    body = bytearray(CURRY9_EVENT_STRUCT_BYTES)
    body[0:4] = np.array([event_type], dtype="<i4").tobytes()
    body[4:8] = np.array([latency], dtype="<i4").tobytes()
    body[8:12] = np.array([latency], dtype="<i4").tobytes()
    body[12:16] = np.array([end_latency], dtype="<i4").tobytes()
    encoded = annotation.encode("utf-16-le", errors="ignore")
    body[16:16 + min(len(encoded), CURRY9_EVENT_STRUCT_BYTES - 16)] = encoded[: CURRY9_EVENT_STRUCT_BYTES - 16]
    return bytes(body)


@dataclass
class SimulatorConfig:
    host: str = "127.0.0.1"
    port: int = 4455
    channel_count: int = 65
    sample_rate: int = 1000
    packet_samples: int = 40
    data_type: str = "float32"
    amplitude_uv: float = 80.0
    signal_frequency_hz: float = 10.0
    noise_uv: float = 2.0
    label_prefix: str = "Ch"
    trigger_channel_index: int = 64
    auto_event_interval_s: float = 2.0
    event_code: int = 1
    keepalive_interval_s: float = 1.0
    trial_duration_s: float = 1.0
    trial_start_code: int = 16
    trial_end_code: int = 20


@dataclass
class QueuedEvent:
    code: int
    latency: int
    end_latency: int
    annotation: str = ""


@dataclass
class ClientState:
    socket: socket.socket
    address: tuple[str, int]
    streaming: bool = False
    start_requested: bool = False
    sample_index: int = 0
    last_send_time: float = field(default_factory=time.time)
    last_keepalive_time: float = field(default_factory=time.time)
    last_auto_event_time: float = field(default_factory=lambda: 0.0)
    phase_offset: float = 0.0
    pending_events: List[QueuedEvent] = field(default_factory=list)


class NeuroScanSimulatorServer:
    def __init__(
        self,
        mode: str,
        config: SimulatorConfig,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        if mode not in {"curry8", "curry9"}:
            raise ValueError("mode must be 'curry8' or 'curry9'")
        self.mode = mode
        self.config = config
        self.log_callback = log_callback or (lambda message: None)
        self._server_socket: Optional[socket.socket] = None
        self._accept_thread: Optional[threading.Thread] = None
        self._stream_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        self._clients: List[ClientState] = []

    def log(self, message: str) -> None:
        self.log_callback(message)

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.config.host, self.config.port))
        self._server_socket.listen(5)
        self._server_socket.settimeout(0.5)
        self._accept_thread = threading.Thread(target=self._accept_loop, name=f"{self.mode}-accept", daemon=True)
        self._stream_thread = threading.Thread(target=self._stream_loop, name=f"{self.mode}-stream", daemon=True)
        self._accept_thread.start()
        self._stream_thread.start()
        self.log(f"[{self.mode}] listening on {self.config.host}:{self.config.port}")

    def stop(self) -> None:
        self._stop_event.set()
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None
        with self._lock:
            clients = list(self._clients)
            self._clients.clear()
        for client in clients:
            self._close_client(client)
        self.log(f"[{self.mode}] stopped")

    @property
    def is_running(self) -> bool:
        return self._server_socket is not None and not self._stop_event.is_set()

    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    def queue_manual_event(self, code: Optional[int] = None, annotation: str = "manual") -> None:
        with self._lock:
            targets = list(self._clients)
        for client in targets:
            event_code = self.config.event_code if code is None else code
            latency = max(1, client.sample_index + 1)
            if self.mode == "curry9" and event_code == self.config.trial_start_code:
                end_latency = latency + max(1, int(self.config.trial_duration_s * self.config.sample_rate))
            else:
                end_latency = latency
            client.pending_events.append(
                QueuedEvent(code=event_code, latency=latency, end_latency=end_latency, annotation=annotation)
            )
        self.log(f"[{self.mode}] queued manual event code={code if code is not None else self.config.event_code}")

    def queue_trial_pair(self) -> None:
        with self._lock:
            targets = list(self._clients)
        duration_samples = max(1, int(self.config.trial_duration_s * self.config.sample_rate))
        for client in targets:
            start_latency = max(1, client.sample_index + 1)
            end_latency = start_latency + duration_samples
            client.pending_events.append(
                QueuedEvent(
                    code=self.config.trial_start_code,
                    latency=start_latency,
                    end_latency=start_latency,
                    annotation="trial-start",
                )
            )
            client.pending_events.append(
                QueuedEvent(
                    code=self.config.trial_end_code,
                    latency=end_latency,
                    end_latency=end_latency,
                    annotation="trial-end",
                )
            )
        self.log(f"[{self.mode}] queued trial start/end pair")

    def _accept_loop(self) -> None:
        assert self._server_socket is not None
        while not self._stop_event.is_set():
            try:
                client_socket, address = self._server_socket.accept()
            except OSError:
                break
            client_socket.settimeout(0.5)
            state = ClientState(socket=client_socket, address=address)
            with self._lock:
                self._clients.append(state)
            self.log(f"[{self.mode}] client connected: {address[0]}:{address[1]}")
            thread = threading.Thread(target=self._client_loop, args=(state,), name=f"{self.mode}-client", daemon=True)
            thread.start()

    def _client_loop(self, client: ClientState) -> None:
        try:
            while not self._stop_event.is_set():
                header = self._recv_exact(client.socket, 20)
                if header is None:
                    break
                if header[0:4] != b"CTRL":
                    self.log(f"[{self.mode}] ignored invalid header from {client.address}")
                    continue
                request = int.from_bytes(header[6:8], byteorder="big", signed=False)
                if request == REQUEST_BASIC_INFO:
                    self._send_basic_info(client)
                elif request == REQUEST_CHANNEL_INFO:
                    self._send_channel_info(client)
                elif request == REQUEST_STREAMING_START:
                    client.streaming = True
                    client.start_requested = True
                    self.log(f"[{self.mode}] streaming started for {client.address[0]}:{client.address[1]}")
                elif request == REQUEST_STREAMING_STOP:
                    client.streaming = False
                    client.start_requested = False
                    self.log(f"[{self.mode}] streaming stopped for {client.address[0]}:{client.address[1]}")
                else:
                    self.log(f"[{self.mode}] unknown request={request} from {client.address}")
        except OSError:
            pass
        finally:
            self._remove_client(client)

    def _stream_loop(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                clients = list(self._clients)
            for client in clients:
                if not client.streaming:
                    continue
                try:
                    self._emit_stream_packets(client)
                except OSError:
                    self._remove_client(client)
            time.sleep(0.005)

    def _emit_stream_packets(self, client: ClientState) -> None:
        now = time.time()
        packet_interval = max(self.config.packet_samples / max(self.config.sample_rate, 1), 0.001)
        if now - client.last_send_time < packet_interval:
            if self.mode == "curry9" and now - client.last_keepalive_time >= self.config.keepalive_interval_s:
                self._send_keepalive(client)
                client.last_keepalive_time = now
            return

        if self.config.auto_event_interval_s > 0 and now - client.last_auto_event_time >= self.config.auto_event_interval_s:
            self._queue_auto_event(client)
            client.last_auto_event_time = now

        if client.pending_events:
            event = client.pending_events.pop(0)
            self._send_event(client, event)

        self._send_eeg(client)
        client.last_send_time = now

    def _queue_auto_event(self, client: ClientState) -> None:
        latency = max(1, client.sample_index + 1)
        if self.mode == "curry8":
            client.pending_events.append(
                QueuedEvent(code=self.config.event_code, latency=latency, end_latency=latency, annotation="auto")
            )
        else:
            duration_samples = max(1, int(self.config.trial_duration_s * self.config.sample_rate))
            client.pending_events.append(
                QueuedEvent(
                    code=self.config.trial_start_code,
                    latency=latency,
                    end_latency=latency,
                    annotation="auto-trial-start",
                )
            )
            client.pending_events.append(
                QueuedEvent(
                    code=self.config.trial_end_code,
                    latency=latency + duration_samples,
                    end_latency=latency + duration_samples,
                    annotation="auto-trial-end",
                )
            )

    def _send_basic_info(self, client: ClientState) -> None:
        data_size = 2 if self.config.data_type == "int16" else 4
        body = build_basic_info_body(self.config.channel_count, self.config.sample_rate, data_size)
        packet = build_packet_header(CODE_INFO, 2, 0, len(body)) + body
        client.socket.sendall(packet)
        self.log(f"[{self.mode}] basic info sent to {client.address}")

    def _send_channel_info(self, client: ClientState) -> None:
        body = build_channel_info_body(self.config.channel_count, self.config.label_prefix)
        packet = build_packet_header(CODE_INFO, 4, 0, len(body)) + body
        client.socket.sendall(packet)
        self.log(f"[{self.mode}] channel info sent to {client.address}")

    def _send_keepalive(self, client: ClientState) -> None:
        packet = build_packet_header(CODE_KEEPALIVE, REQUEST_STREAMING_START, client.sample_index, 0)
        client.socket.sendall(packet)

    def _send_event(self, client: ClientState, event: QueuedEvent) -> None:
        if self.mode == "curry8":
            body = build_curry8_event_body(event.code, event.latency)
        else:
            body = build_curry9_event_body(event.code, event.latency, event.end_latency, event.annotation)
        packet = build_packet_header(CODE_EVENT, REQUEST_STREAMING_START, event.latency, len(body)) + body
        client.socket.sendall(packet)
        self.log(f"[{self.mode}] event sent code={event.code} latency={event.latency}")

    def _send_eeg(self, client: ClientState) -> None:
        data = self._generate_eeg_block(client.sample_index, client.phase_offset)
        body = self._encode_eeg_payload(data)
        packet = build_packet_header(CODE_EEG, REQUEST_STREAMING_START, client.sample_index, len(body)) + body
        client.socket.sendall(packet)
        client.sample_index += self.config.packet_samples

    def _generate_eeg_block(self, start_sample: int, phase_offset: float) -> np.ndarray:
        samples = self.config.packet_samples
        channels = self.config.channel_count
        data = np.zeros((channels, samples), dtype=np.float32)
        time_axis = (np.arange(samples, dtype=np.float32) + start_sample) / max(self.config.sample_rate, 1)
        for channel in range(channels):
            if channel == self.config.trigger_channel_index:
                continue
            phase = phase_offset + channel * 0.13
            signal = self.config.amplitude_uv * np.sin(2 * math.pi * self.config.signal_frequency_hz * time_axis + phase)
            modulation = 0.15 * self.config.amplitude_uv * np.sin(2 * math.pi * (self.config.signal_frequency_hz / 2.0) * time_axis + phase * 0.5)
            noise = self.config.noise_uv * np.random.randn(samples).astype(np.float32)
            data[channel, :] = signal + modulation + noise
        return data

    def _encode_eeg_payload(self, data: np.ndarray) -> bytes:
        if self.config.data_type == "int16":
            packed = np.round(data).astype(np.int16)
        else:
            packed = data.astype(np.float32, copy=False)
        return np.asarray(packed, order="F").tobytes(order="F")

    def _recv_exact(self, sock: socket.socket, size: int) -> Optional[bytes]:
        chunks = bytearray()
        while len(chunks) < size and not self._stop_event.is_set():
            try:
                chunk = sock.recv(size - len(chunks))
            except socket.timeout:
                continue
            if not chunk:
                return None
            chunks.extend(chunk)
        return bytes(chunks) if len(chunks) == size else None

    def _remove_client(self, client: ClientState) -> None:
        with self._lock:
            if client in self._clients:
                self._clients.remove(client)
        self._close_client(client)
        self.log(f"[{self.mode}] client disconnected: {client.address[0]}:{client.address[1]}")

    def _close_client(self, client: ClientState) -> None:
        try:
            client.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            client.socket.close()
        except OSError:
            pass
