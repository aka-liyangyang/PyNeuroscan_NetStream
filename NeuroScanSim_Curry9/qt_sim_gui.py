from __future__ import annotations

import queue
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from neuroscan_sim_base import NeuroScanSimulatorServer, SimulatorConfig


@dataclass(frozen=True)
class SimField:
    label: str
    key: str
    default: Any
    kind: str = "str"
    choices: Iterable[str] = ()


class SimulatorWindow(QMainWindow):
    def __init__(
        self,
        window_title: str,
        mode: str,
        hero_title: str,
        hero_subtitle: str,
        fields: list[SimField],
        accent: str,
    ) -> None:
        super().__init__()
        self.mode = mode
        self.fields = fields
        self.accent = accent
        self.server: Optional[NeuroScanSimulatorServer] = None
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.inputs: Dict[str, QWidget] = {}
        self.action_layout: Optional[QHBoxLayout] = None
        self.status_value: Optional[QLabel] = None
        self.client_value: Optional[QLabel] = None
        self.log_view: Optional[QPlainTextEdit] = None
        self.status_row: Optional[QFrame] = None

        self.setWindowTitle(window_title)
        self.resize(1100, 760)
        self._build_ui(hero_title, hero_subtitle)
        self._apply_styles()

        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self._drain_logs)
        self.log_timer.start(120)

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._refresh_runtime_state)
        self.status_timer.start(300)

    def _build_ui(self, hero_title: str, hero_subtitle: str) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)

        root.addWidget(self._build_hero(hero_title, hero_subtitle))

        content = QHBoxLayout()
        content.setSpacing(16)
        root.addLayout(content, stretch=1)

        left = QVBoxLayout()
        left.setSpacing(16)
        content.addLayout(left, stretch=3)

        right = QVBoxLayout()
        right.setSpacing(16)
        content.addLayout(right, stretch=2)

        left.addWidget(self._build_config_card(), stretch=1)
        left.addWidget(self._build_controls_card(), stretch=0)
        right.addWidget(self._build_status_card(), stretch=0)
        right.addWidget(self._build_log_card(), stretch=1)

    def _build_hero(self, title: str, subtitle: str) -> QWidget:
        frame = QFrame()
        frame.setObjectName("heroCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("heroTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("heroSubtitle")
        subtitle_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        return frame

    def _build_config_card(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("panelCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(16)

        title = QLabel("通信与数据参数 / Communication and Data")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)
        for index, field in enumerate(self.fields):
            label = QLabel(field.label)
            label.setObjectName("fieldLabel")
            widget = self._create_input(field)
            row = index // 2
            col = (index % 2) * 2
            grid.addWidget(label, row, col)
            grid.addWidget(widget, row, col + 1)
            self.inputs[field.key] = widget
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        layout.addLayout(grid)
        return frame

    def _build_controls_card(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("panelCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)

        title = QLabel("操作区 / Actions")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)

        start_button = QPushButton("启动仿真 / Start Simulator")
        start_button.clicked.connect(self.start_server)
        start_button.setObjectName("primaryButton")

        stop_button = QPushButton("停止仿真 / Stop")
        stop_button.clicked.connect(self.stop_server)
        stop_button.setObjectName("secondaryButton")

        buttons.addWidget(start_button)
        buttons.addWidget(stop_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.action_layout = QHBoxLayout()
        self.action_layout.setSpacing(10)
        self.action_layout.addStretch(1)
        layout.addLayout(self.action_layout)
        return frame

    def _build_status_card(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("panelCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)

        title = QLabel("运行状态 / Runtime")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        self.status_row, self.status_value = self._metric_row(layout, "状态 / Status", "已停止 / Stopped")
        _, self.client_value = self._metric_row(layout, "客户端 / Clients", "0")
        self._metric_row(layout, "模式 / Mode", self.mode)
        return frame

    def _build_log_card(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("panelCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("运行日志 / Logs")
        title.setObjectName("panelTitle")
        clear_button = QPushButton("清空 / Clear")
        clear_button.setObjectName("ghostButton")
        clear_button.clicked.connect(self._clear_logs)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(clear_button)
        layout.addLayout(header)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName("logView")
        self.log_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        log_font = QFont("Consolas", 10)
        self.log_view.setFont(log_font)
        layout.addWidget(self.log_view)
        return frame

    def _metric_row(self, parent: QVBoxLayout, label_text: str, value_text: str) -> tuple[QFrame, QLabel]:
        row = QFrame()
        row.setObjectName("metricRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        label = QLabel(label_text)
        label.setObjectName("metricLabel")
        value = QLabel(value_text)
        value.setObjectName("metricValue")
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(label)
        layout.addStretch(1)
        layout.addWidget(value)
        parent.addWidget(row)
        return row, value

    def _create_input(self, field: SimField) -> QWidget:
        if field.kind == "choice":
            widget = QComboBox()
            for item in field.choices:
                widget.addItem(str(item))
            widget.setCurrentText(str(field.default))
            return widget
        widget = QLineEdit(str(field.default))
        widget.setObjectName("fieldInput")
        return widget

    def _apply_styles(self) -> None:
        accent = self.accent
        accent_rgb = QColor(accent).getRgb()
        accent_soft = f"rgba({accent_rgb[0]}, {accent_rgb[1]}, {accent_rgb[2]}, 0.12)"
        accent_line = f"rgba({accent_rgb[0]}, {accent_rgb[1]}, {accent_rgb[2]}, 0.35)"
        self.setStyleSheet(
            f"""
            QMainWindow {{
                background: #f4efe6;
            }}
            #heroCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #fffaf2, stop:0.45 #f6efe3, stop:1 #ece3d2);
                border: 1px solid #d8ccb8;
                border-radius: 22px;
            }}
            #heroTitle {{
                color: #1f2937;
                font-size: 28px;
                font-weight: 700;
            }}
            #heroSubtitle {{
                color: #5b6472;
                font-size: 13px;
                line-height: 1.5;
            }}
            #panelCard {{
                background: #fffdf9;
                border: 1px solid #ded5c8;
                border-radius: 20px;
            }}
            #panelTitle {{
                color: #243041;
                font-size: 15px;
                font-weight: 700;
            }}
            #fieldLabel {{
                color: #4b5563;
                font-size: 12px;
                font-weight: 600;
            }}
            QLineEdit, QComboBox {{
                background: #ffffff;
                color: #1f2937;
                border: 1px solid #d7d0c3;
                border-radius: 10px;
                padding: 8px 10px;
                min-height: 20px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 1px solid {accent};
                background: #fffefb;
            }}
            QPushButton {{
                border-radius: 11px;
                padding: 10px 16px;
                font-weight: 600;
            }}
            #primaryButton {{
                color: white;
                background: {accent};
                border: 1px solid {accent};
            }}
            #primaryButton:hover {{
                background: {QColor(accent).lighter(108).name()};
            }}
            #secondaryButton {{
                color: #2f3b48;
                background: #ece6da;
                border: 1px solid #d9d0c2;
            }}
            #secondaryButton:hover, #ghostButton:hover {{
                background: #e4dccf;
            }}
            #ghostButton {{
                color: #465365;
                background: transparent;
                border: 1px solid #d9d0c2;
            }}
            #metricRow {{
                background: {accent_soft};
                border: 1px solid {accent_line};
                border-radius: 14px;
            }}
            #metricRow[state="connected"] {{
                background: rgba(22, 163, 74, 0.18);
                border: 1px solid rgba(22, 163, 74, 0.45);
            }}
            #metricRow[state="listening"] {{
                background: rgba(37, 99, 235, 0.14);
                border: 1px solid rgba(37, 99, 235, 0.35);
            }}
            #metricRow[state="error"] {{
                background: rgba(220, 38, 38, 0.16);
                border: 1px solid rgba(220, 38, 38, 0.38);
            }}
            #metricLabel {{
                color: #5c6575;
                font-size: 12px;
                font-weight: 600;
            }}
            #metricValue {{
                color: #17212f;
                font-size: 13px;
                font-weight: 700;
            }}
            #logView {{
                background: #171a1f;
                color: #d8f4ec;
                border: 1px solid #2b313a;
                border-radius: 14px;
                padding: 8px;
            }}
            """
        )

    def add_action_button(self, text: str, callback: Any) -> None:
        if self.action_layout is None:
            return
        button = QPushButton(text)
        button.setObjectName("ghostButton")
        button.clicked.connect(callback)
        self.action_layout.insertWidget(self.action_layout.count() - 1, button)

    def append_log(self, message: str) -> None:
        self.log_queue.put(message)

    def collect_config_values(self) -> Dict[str, Any]:
        values: Dict[str, Any] = {}
        for field in self.fields:
            widget = self.inputs[field.key]
            if isinstance(widget, QComboBox):
                raw = widget.currentText()
            else:
                raw = widget.text().strip()
            values[field.key] = self._convert_value(field, raw)
        return values

    def _convert_value(self, field: SimField, raw: str) -> Any:
        if field.kind == "int":
            return int(raw)
        if field.kind == "float":
            return float(raw)
        return raw

    def start_server(self) -> None:
        try:
            values = self.collect_config_values()
            self.stop_server()
            self.server = NeuroScanSimulatorServer(
                mode=self.mode,
                config=SimulatorConfig(**values),
                log_callback=self.append_log,
            )
            self.server.start()
            self.append_log(f"[{self.mode}] simulator started on {values['host']}:{values['port']}")
            self._set_status(f"监听中 / Listening: {values['host']}:{values['port']}", "listening")
        except Exception as exc:
            QMessageBox.critical(self, "启动失败 / Start Failed", str(exc))
            self._set_status("启动失败 / Start failed", "error")

    def stop_server(self) -> None:
        if self.server is not None:
            self.server.stop()
            self.server = None
        self._set_status("已停止 / Stopped", "stopped")
        if self.client_value is not None:
            self.client_value.setText("0")

    def _set_status(self, text: str, state: str = "stopped") -> None:
        if self.status_value is not None:
            self.status_value.setText(text)
        if self.status_row is not None:
            self.status_row.setProperty("state", state)
            self.status_row.style().unpolish(self.status_row)
            self.status_row.style().polish(self.status_row)

    def _drain_logs(self) -> None:
        if self.log_view is None:
            return
        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_view.appendPlainText(message)
            scrollbar = self.log_view.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def _refresh_runtime_state(self) -> None:
        if self.server is None:
            return
        client_count = self.server.client_count()
        if self.client_value is not None:
            self.client_value.setText(str(client_count))
        if client_count > 0:
            self._set_status(f"已连接 / Connected: {client_count}", "connected")
        elif self.server.is_running:
            status_text = self.status_value.text() if self.status_value is not None else ""
            if "Listening" not in status_text and "监听中" not in status_text:
                self._set_status("监听中 / Listening", "listening")

    def _clear_logs(self) -> None:
        if self.log_view is not None:
            self.log_view.clear()

    def closeEvent(self, event: Any) -> None:
        self.stop_server()
        super().closeEvent(event)
