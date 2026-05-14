from __future__ import annotations

import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from qt_sim_gui import SimField, SimulatorWindow


class Curry9Window(SimulatorWindow):
    def __init__(self) -> None:
        fields = [
            SimField("监听 IP / Listen IP", "host", "127.0.0.1"),
            SimField("监听端口 / Listen Port", "port", 4455, "int"),
            SimField("通道数 / Channels", "channel_count", 65, "int"),
            SimField("采样率 / Sample Rate", "sample_rate", 1000, "int"),
            SimField("每包采样点 / Packet Samples", "packet_samples", 40, "int"),
            SimField("数据类型 / Data Type", "data_type", "float32", "choice", ("float32", "int16")),
            SimField("幅值 uV / Amplitude", "amplitude_uv", 80.0, "float"),
            SimField("主频 Hz / Signal", "signal_frequency_hz", 12.0, "float"),
            SimField("噪声 uV / Noise", "noise_uv", 2.0, "float"),
            SimField("标签前缀 / Label Prefix", "label_prefix", "Ch"),
            SimField("触发通道 / Trigger Index", "trigger_channel_index", 64, "int"),
            SimField("自动试次间隔 / Auto Trial Sec", "auto_event_interval_s", 3.0, "float"),
            SimField("保活间隔 / KeepAlive Sec", "keepalive_interval_s", 1.0, "float"),
            SimField("试次时长 / Trial Duration", "trial_duration_s", 1.0, "float"),
            SimField("开始事件码 / Start Code", "trial_start_code", 16, "int"),
            SimField("结束事件码 / End Code", "trial_end_code", 20, "int"),
        ]
        super().__init__(
            window_title="NeuroScanSim_Curry9",
            mode="curry9",
            hero_title="Curry 9 试次仿真器 / Trial Simulator",
            hero_subtitle="用于 acq_curry9 系统联调，支持连续 EEG、536 字节事件块和保活包。 / Continuous EEG, 536-byte event blocks, and keep-alive packets for acq_curry9 system debugging.",
            fields=fields,
            accent="#b45309",
        )
        self.add_action_button("发送试次对 / Send Trial Pair", self._send_trial_pair)
        self.add_action_button("发送开始事件 / Send Start Event", self._send_start_event)

    def _send_trial_pair(self) -> None:
        if self.server is None:
            self.append_log("[curry9] server is not running")
            return
        self.server.queue_trial_pair()

    def _send_start_event(self) -> None:
        if self.server is None:
            self.append_log("[curry9] server is not running")
            return
        values = self.collect_config_values()
        self.server.queue_manual_event(code=values["trial_start_code"], annotation="manual-start")


def main() -> None:
    app = QApplication(sys.argv)
    window = Curry9Window()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
