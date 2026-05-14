from __future__ import annotations

import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from qt_sim_gui import SimField, SimulatorWindow


class Curry8Window(SimulatorWindow):
    def __init__(self) -> None:
        fields = [
            SimField("监听 IP / Listen IP", "host", "127.0.0.1"),
            SimField("监听端口 / Listen Port", "port", 4455, "int"),
            SimField("通道数 / Channels", "channel_count", 65, "int"),
            SimField("采样率 / Sample Rate", "sample_rate", 1000, "int"),
            SimField("每包采样点 / Packet Samples", "packet_samples", 120, "int"),
            SimField("数据类型 / Data Type", "data_type", "float32", "choice", ("float32", "int16")),
            SimField("幅值 uV / Amplitude", "amplitude_uv", 80.0, "float"),
            SimField("主频 Hz / Signal", "signal_frequency_hz", 10.0, "float"),
            SimField("噪声 uV / Noise", "noise_uv", 2.0, "float"),
            SimField("标签前缀 / Label Prefix", "label_prefix", "Ch"),
            SimField("触发通道 / Trigger Index", "trigger_channel_index", 64, "int"),
            SimField("自动事件间隔 / Auto Event Sec", "auto_event_interval_s", 2.0, "float"),
            SimField("事件码 / Event Code", "event_code", 1, "int"),
        ]
        super().__init__(
            window_title="NeuroScanSim_Curry8",
            mode="curry8",
            hero_title="Curry 8 EEG 仿真器 / Simulator",
            hero_subtitle="用于 acq_curry8 系统联调，持续发送 EEG 数据包并支持可配置事件注入。 / Continuous EEG packets with configurable event injection for acq_curry8 integration testing.",
            fields=fields,
            accent="#0f766e",
        )
        self.add_action_button("发送事件 / Send Event", self._send_event)

    def _send_event(self) -> None:
        if self.server is None:
            self.append_log("[curry8] server is not running")
            return
        values = self.collect_config_values()
        self.server.queue_manual_event(code=values["event_code"], annotation="manual")


def main() -> None:
    app = QApplication(sys.argv)
    window = Curry8Window()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
