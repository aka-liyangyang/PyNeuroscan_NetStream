from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import yaml

LOCAL_CONFIG_PATH = Path(__file__).with_name("config.yaml")


@dataclass
class DeviceConfig:
    host: str = "127.0.0.1"
    port: int = 4455
    channels: int = 65
    sample_rate: int = 1000
    timeout_seconds: float = 5.0
    reconnect_interval_seconds: float = 1.0


@dataclass
class StreamConfig:
    downsample_factor: int = 4
    eeg_channel_indices: List[int] = field(default_factory=lambda: list(range(64)))
    trigger_channel_index: Optional[int] = 64


@dataclass
class AppConfig:
    device: DeviceConfig = field(default_factory=DeviceConfig)
    stream: StreamConfig = field(default_factory=StreamConfig)


@dataclass
class EegFrame:
    start_sample: int
    sample_rate: int
    data: np.ndarray
    trigger: np.ndarray
    channel_labels: List[str]


class CurryProtocol:
    REQUEST_CHANNEL_INFO = 3
    REQUEST_BASIC_INFO = 6
    REQUEST_STREAMING_START = 8
    REQUEST_STREAMING_STOP = 9

    @staticmethod
    def build_header(request: int, samples: int = 0, body_size: int = 0) -> bytes:
        return (
            b"CTRL"
            + (2).to_bytes(2, "big")
            + int(request).to_bytes(2, "big")
            + int(samples).to_bytes(4, "big")
            + int(body_size).to_bytes(4, "big")
            + int(body_size).to_bytes(4, "big")
        )


class Curry8Reader:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.socket: Optional[socket.socket] = None
        self.info: Dict[str, Any] = {}
        self.latest_frame: Optional[EegFrame] = None
        self.pending_event: Optional[Dict[str, int]] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.RLock()

    def log(self, message: str) -> None:
        print(f"[acq_curry8] {message}", flush=True)

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.log(f"starting reader, target={self.config.device.host}:{self.config.device.port}")
        self.thread = threading.Thread(target=self._read_loop, name="curry8-reader", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        self._disconnect()
        self.log("reader stopped")

    def get_latest_frame(self) -> Optional[EegFrame]:
        with self.lock:
            return self.latest_frame

    def _connect(self) -> None:
        self._disconnect()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.config.device.timeout_seconds)
        sock.connect((self.config.device.host, self.config.device.port))
        sock.setblocking(True)
        self.socket = sock
        self.log("connected to Curry8 host")
        self._request_basic_info()
        self._request_channel_info()

    def _disconnect(self) -> None:
        if self.socket is None:
            return
        try:
            self.socket.sendall(CurryProtocol.build_header(CurryProtocol.REQUEST_STREAMING_STOP))
        except OSError:
            pass
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.socket.close()
        self.socket = None
        self.log("socket disconnected")

    def _read_loop(self) -> None:
        while self.running:
            try:
                if self.socket is None:
                    self.log("trying to connect ...")
                    self._connect()
                self._request_stream_packet()
            except (ConnectionError, OSError, ValueError) as exc:
                self.log(f"stream read failed: {exc}")
                self._disconnect()
                if not self.running:
                    break
                time.sleep(self.config.device.reconnect_interval_seconds)

    def _recv_exact(self, size: int) -> bytes:
        if self.socket is None:
            raise ConnectionError("socket is not connected")
        buffer = bytearray()
        while len(buffer) < size:
            chunk = self.socket.recv(size - len(buffer))
            if not chunk:
                raise ConnectionError("connection closed by peer")
            buffer.extend(chunk)
        return bytes(buffer)

    def _read_packet(self) -> tuple[Dict[str, int], bytes]:
        header = self._recv_exact(20)
        packet_size = int.from_bytes(header[12:16], "big")
        return {
            "code": int.from_bytes(header[4:6], "big"),
            "request": int.from_bytes(header[6:8], "big"),
            "start_sample": int.from_bytes(header[8:12], "big"),
            "packet_size": packet_size,
        }, self._recv_exact(packet_size)

    def _request_basic_info(self) -> None:
        assert self.socket is not None
        self.socket.sendall(CurryProtocol.build_header(CurryProtocol.REQUEST_BASIC_INFO))
        _, body = self._read_packet()
        self.info = {
            "eeg_channels": int(np.frombuffer(body[4:8], dtype="<u4")[0]),
            "sample_rate": int(np.frombuffer(body[8:12], dtype="<u4")[0]),
            "data_size": int(np.frombuffer(body[12:16], dtype="<u4")[0]),
        }
        self.log(f"basic info: {self.info}")

    def _request_channel_info(self) -> None:
        assert self.socket is not None
        self.socket.sendall(CurryProtocol.build_header(CurryProtocol.REQUEST_CHANNEL_INFO))
        _, body = self._read_packet()
        labels: List[str] = []
        block_size = 120
        for index in range(self.info["eeg_channels"]):
            label = body[index * block_size + 4: index * block_size + 10]
            labels.append(label.decode("ascii", errors="ignore").replace("\x00", ""))
        self.info["channels"] = labels
        self.log(f"channel info: count={len(labels)}, labels={labels}")

    def _request_stream_packet(self) -> None:
        assert self.socket is not None
        self.socket.sendall(CurryProtocol.build_header(CurryProtocol.REQUEST_STREAMING_START))
        packet, body = self._read_packet()
        if packet["code"] == 3:
            self.pending_event = {
                "event_type": int(np.frombuffer(body[0:4], dtype="<u4")[0]),
                "start_event": int(np.frombuffer(body[8:12], dtype="<u4")[0]),
            }
            self.log(f"event packet: {self.pending_event}")
            return
        if packet["code"] != 2:
            self.log(f"ignored packet code={packet['code']} request={packet['request']}")
            return
        frame = self._build_frame(packet["start_sample"], self._decode_eeg(body))
        with self.lock:
            self.latest_frame = frame
        self._log_frame(frame)

    def _decode_eeg(self, body: bytes) -> np.ndarray:
        data_size = self.info["data_size"]
        if data_size == 2:
            values = np.frombuffer(body, dtype=np.int16)
        elif data_size == 4:
            values = np.frombuffer(body, dtype=np.float32)
        else:
            raise ValueError(f"unsupported data_size={data_size}")
        channels = self.info["eeg_channels"]
        sample_count = len(values) // channels
        values = values[: sample_count * channels]
        return np.reshape(values, (channels, sample_count), order="F").astype(np.float32, copy=False)

    def _build_frame(self, start_sample: int, eeg: np.ndarray) -> EegFrame:
        trigger = self._select_trigger_source(eeg)
        if self.pending_event is not None:
            event_index = self.pending_event["start_event"] - start_sample - 1
            if self.pending_event["start_event"] == start_sample:
                trigger[0, 0] = self.pending_event["event_type"]
            elif 0 <= event_index < trigger.shape[1]:
                trigger[0, event_index] = self.pending_event["event_type"]
            self.pending_event = None

        eeg_data = self._downsample(eeg)
        trigger_data = self._downsample(trigger)
        return EegFrame(
            start_sample=start_sample,
            sample_rate=max(1, self.info["sample_rate"] // max(self.config.stream.downsample_factor, 1)),
            data=eeg_data[self.config.stream.eeg_channel_indices, :].copy(),
            trigger=trigger_data,
            channel_labels=self._selected_labels(),
        )

    def _downsample(self, packet: np.ndarray) -> np.ndarray:
        factor = max(self.config.stream.downsample_factor, 1)
        if factor == 1:
            return packet.copy()
        downsampled = packet[:, ::factor].copy()
        event_indices = np.where(packet[-1, :] != 0)[0]
        for index in event_indices:
            downsampled[-1, index // factor] = packet[-1, index]
        return downsampled

    def _select_trigger_source(self, eeg: np.ndarray) -> np.ndarray:
        trigger_index = self.config.stream.trigger_channel_index
        if trigger_index is None:
            return np.zeros((1, eeg.shape[1]), dtype=np.float32)
        if 0 <= trigger_index < eeg.shape[0]:
            return eeg[trigger_index: trigger_index + 1, :].astype(np.float32, copy=True)
        return np.zeros((1, eeg.shape[1]), dtype=np.float32)

    def _selected_labels(self) -> List[str]:
        labels = self.info.get("channels", [])
        if not labels:
            return [f"Ch{index + 1}" for index in self.config.stream.eeg_channel_indices]
        return [labels[index] for index in self.config.stream.eeg_channel_indices if index < len(labels)]

    def _log_frame(self, frame: EegFrame) -> None:
        trigger_nonzero = frame.trigger[0][frame.trigger[0] != 0].tolist()
        preview_channels = min(2, frame.data.shape[0])
        preview_samples = min(8, frame.data.shape[1])
        eeg_preview = frame.data[:preview_channels, :preview_samples].tolist()
        self.log(
            "EEG frame: "
            f"start_sample={frame.start_sample}, sample_rate={frame.sample_rate}, "
            f"data_shape={frame.data.shape}, trigger_shape={frame.trigger.shape}, "
            f"trigger_nonzero={trigger_nonzero}, eeg_preview={eeg_preview}"
        )


def load_config(config_path: str | Path = LOCAL_CONFIG_PATH, stream_key: str = "EEG") -> AppConfig:
    with Path(config_path).open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}
    stream_raw = raw.get("stream")
    if stream_raw is None:
        stream_raw = (raw.get("streams") or {}).get(stream_key, {})
    return AppConfig(
        device=DeviceConfig(**(raw.get("device") or {})),
        stream=StreamConfig(**(stream_raw or {})),
    )


def main() -> None:
    reader = Curry8Reader(load_config())
    reader.start()
    last_report_time = 0.0
    try:
        while True:
            time.sleep(0.1)
            frame = reader.get_latest_frame()
            if frame is not None:
                print(
                    f"[acq_curry8] latest frame summary: start={frame.start_sample}, "
                    f"trigger_max={float(frame.trigger.max())}, data_mean={float(frame.data.mean()):.3f}",
                    flush=True,
                )
            elif time.time() - last_report_time >= 2.0:
                print("[acq_curry8] waiting for first EEG frame ...", flush=True)
                last_report_time = time.time()
    except KeyboardInterrupt:
        pass
    finally:
        reader.stop()


if __name__ == "__main__":
    main()
