from __future__ import annotations

import asyncio
import logging
import sys
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QAction, QFont, QFontDatabase, QColor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QMenu,
    QStyle,
)

from f1_engineer.app import EngineerApp
from f1_engineer.config import Gender, PersonaId, Region, Talkativeness
from f1_engineer.personas.catalog import PERSONAS
from f1_engineer.radio.log import RadioMessage

log = logging.getLogger(__name__)

# Pit-wall palette
C_BG = "#07090d"
C_SURFACE = "#10141c"
C_ELEVATED = "#161b26"
C_BORDER = "#2a3142"
C_BORDER_SOFT = "#1c2230"
C_TEXT = "#eef2f8"
C_MUTED = "#8b95a8"
C_DIM = "#5a6478"
C_RED = "#e10600"
C_RED_HOT = "#ff2d22"
C_DRIVER = "#6ec8e8"
C_ENGINEER = "#ff9a90"
C_SYSTEM = "#6b7385"
C_WARN = "#e8b84a"
C_LIVE = "#3dd68c"


STYLESHEET = f"""
QWidget#root {{
    background: {C_BG};
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    border-radius: 12px;
}}
QWidget#chrome {{
    background: {C_SURFACE};
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    border-bottom: 1px solid {C_BORDER_SOFT};
}}
QWidget#body {{
    background: {C_BG};
    border-bottom-left-radius: 12px;
    border-bottom-right-radius: 12px;
}}
QLabel#brand {{
    color: {C_TEXT};
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 2.4px;
}}
QLabel#statusLine {{
    font-size: 11px;
    font-weight: 600;
}}
QLabel#engineerName {{
    color: {C_TEXT};
    font-size: 16px;
    font-weight: 700;
}}
QLabel#engineerMeta {{
    color: {C_MUTED};
    font-size: 11px;
}}
QLabel#fieldLabel {{
    color: {C_DIM};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#sectionLabel {{
    color: {C_MUTED};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.4px;
}}
QLabel#warn {{
    color: {C_WARN};
    font-size: 11px;
    background: rgba(232, 184, 74, 0.08);
    border: 1px solid rgba(232, 184, 74, 0.25);
    border-radius: 8px;
    padding: 8px 10px;
}}
QLabel#rapport {{
    color: {C_MUTED};
    font-size: 11px;
    font-weight: 600;
}}
QLabel#hint {{
    color: {C_DIM};
    font-size: 10px;
}}
QComboBox {{
    background: {C_ELEVATED};
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
    padding: 7px 10px;
    min-height: 18px;
    font-size: 12px;
}}
QComboBox:hover {{ border-color: #3d4658; }}
QComboBox:focus {{ border-color: {C_RED}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {C_ELEVATED};
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    selection-background-color: #243044;
    outline: none;
    padding: 4px;
}}
QLineEdit {{
    background: {C_ELEVATED};
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    border-radius: 10px;
    padding: 11px 14px;
    font-size: 13px;
    selection-background-color: #3a4458;
}}
QLineEdit:focus {{ border-color: {C_RED}; }}
QTextEdit#log {{
    background: {C_SURFACE};
    color: {C_TEXT};
    border: 1px solid {C_BORDER_SOFT};
    border-radius: 10px;
    padding: 12px 14px;
    font-size: 12px;
}}
QCheckBox {{
    color: {C_MUTED};
    font-size: 12px;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border-radius: 4px;
    border: 1px solid {C_BORDER};
    background: {C_ELEVATED};
}}
QCheckBox::indicator:checked {{
    background: {C_RED};
    border-color: {C_RED};
}}
QPushButton#primary {{
    background: {C_RED};
    color: white;
    border: none;
    border-radius: 10px;
    padding: 11px 18px;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.3px;
}}
QPushButton#primary:hover {{ background: {C_RED_HOT}; }}
QPushButton#primary:pressed {{ background: #b00500; }}
QPushButton#ghost {{
    background: transparent;
    color: {C_MUTED};
    border: 1px solid {C_BORDER};
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 12px;
    font-weight: 700;
}}
QPushButton#ghost:hover {{
    color: {C_TEXT};
    border-color: #3d4658;
    background: {C_ELEVATED};
}}
QPushButton#iconBtn {{
    background: transparent;
    color: {C_MUTED};
    border: none;
    border-radius: 8px;
    padding: 4px 10px;
    font-size: 16px;
    font-weight: 600;
}}
QPushButton#iconBtn:hover {{
    color: {C_TEXT};
    background: {C_ELEVATED};
}}
QFrame#divider {{
    background: {C_BORDER_SOFT};
    max-height: 1px;
}}
QFrame#accentBar {{
    background: {C_RED};
    border-radius: 2px;
}}
QFrame#livePill {{
    background: rgba(61, 214, 140, 0.12);
    border: 1px solid rgba(61, 214, 140, 0.35);
    border-radius: 999px;
}}
QFrame#idlePill {{
    background: rgba(90, 100, 120, 0.15);
    border: 1px solid {C_BORDER};
    border-radius: 999px;
}}
"""


class AsyncBridge(QObject):
    status = Signal(str)
    radio = Signal(object)
    tick = Signal()

    def __init__(self, app: EngineerApp) -> None:
        super().__init__()
        self.app = app
        self.loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.create_task(self.app.start())
        self.loop.run_forever()

    def submit(self, coro) -> None:
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, self.loop)

    def stop(self) -> None:
        if self.loop:

            async def _shutdown() -> None:
                await self.app.stop()
                self.loop.stop()

            asyncio.run_coroutine_threadsafe(_shutdown(), self.loop)


def _field(label: str, widget: QWidget) -> QVBoxLayout:
    col = QVBoxLayout()
    col.setSpacing(5)
    lbl = QLabel(label.upper())
    lbl.setObjectName("fieldLabel")
    col.addWidget(lbl)
    col.addWidget(widget)
    return col


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


class OverlayWindow(QMainWindow):
    def __init__(self, app: EngineerApp, bridge: AsyncBridge) -> None:
        super().__init__()
        self.app = app
        self.bridge = bridge
        self.setWindowTitle("F1 Race Engineer")
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.resize(500, 600)
        self.setMinimumSize(420, 520)
        self._drag_pos = None
        self.setStyleSheet(STYLESHEET)
        self._build()
        self._wire_hotkey()

        app.radio_log.subscribe(lambda m: bridge.radio.emit(m))
        bridge.radio.connect(self._on_radio)
        bridge.status.connect(self._on_status)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_status)
        self._timer.start(500)

    def _build(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Title chrome
        chrome = QWidget()
        chrome.setObjectName("chrome")
        chrome_l = QHBoxLayout(chrome)
        chrome_l.setContentsMargins(16, 12, 10, 12)
        chrome_l.setSpacing(12)

        accent = QFrame()
        accent.setObjectName("accentBar")
        accent.setFixedSize(3, 32)
        chrome_l.addWidget(accent)

        brand_col = QVBoxLayout()
        brand_col.setSpacing(2)
        brand = QLabel("RACE ENGINEER")
        brand.setObjectName("brand")
        brand_col.addWidget(brand)

        self.status_pill = QFrame()
        self.status_pill.setObjectName("idlePill")
        pill_l = QHBoxLayout(self.status_pill)
        pill_l.setContentsMargins(10, 3, 10, 3)
        pill_l.setSpacing(6)
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(f"color: {C_DIM}; font-size: 9px;")
        self.conn = QLabel("Listening")
        self.conn.setObjectName("statusLine")
        self.conn.setStyleSheet(f"color: {C_MUTED};")
        pill_l.addWidget(self.status_dot)
        pill_l.addWidget(self.conn)
        brand_col.addWidget(self.status_pill, alignment=Qt.AlignmentFlag.AlignLeft)
        chrome_l.addLayout(brand_col)
        chrome_l.addStretch()

        min_btn = QPushButton("–")
        min_btn.setObjectName("iconBtn")
        min_btn.setFixedSize(32, 32)
        min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        min_btn.setToolTip("Minimize")
        min_btn.clicked.connect(self.showMinimized)
        chrome_l.addWidget(min_btn)
        outer.addWidget(chrome)

        # Body
        body = QWidget()
        body.setObjectName("body")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        # Engineer identity
        id_row = QHBoxLayout()
        id_text = QVBoxLayout()
        id_text.setSpacing(3)
        self.engineer_lbl = QLabel("")
        self.engineer_lbl.setObjectName("engineerName")
        self.engineer_meta = QLabel("")
        self.engineer_meta.setObjectName("engineerMeta")
        id_text.addWidget(self.engineer_lbl)
        id_text.addWidget(self.engineer_meta)
        id_row.addLayout(id_text, stretch=1)
        self.rapport_lbl = QLabel("Rapport  —")
        self.rapport_lbl.setObjectName("rapport")
        self.rapport_lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        id_row.addWidget(self.rapport_lbl)
        layout.addLayout(id_row)

        # Pickers 2x2
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        self.persona = QComboBox()
        for pid, pdef in PERSONAS.items():
            self.persona.addItem(pdef.label, pid.value)
        self.gender = QComboBox()
        self.gender.addItem("Woman", Gender.WOMAN.value)
        self.gender.addItem("Man", Gender.MAN.value)
        row1.addLayout(_field("Persona", self.persona), 1)
        row1.addLayout(_field("Gender", self.gender), 1)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(10)
        self.region = QComboBox()
        for r in Region:
            self.region.addItem(r.name.title(), r.value)
        self.talk = QComboBox()
        for t in Talkativeness:
            self.talk.addItem(t.value.title(), t.value)
        row2.addLayout(_field("Region", self.region), 1)
        row2.addLayout(_field("Talk", self.talk), 1)
        layout.addLayout(row2)

        # Voice
        voice_col = QVBoxLayout()
        voice_col.setSpacing(5)
        voice_col.addWidget(self._label("VOICE", "fieldLabel"))
        voice_row = QHBoxLayout()
        voice_row.setSpacing(8)
        self.voice = QComboBox()
        self._reload_voices()
        voice_row.addWidget(self.voice, 1)
        import_btn = QPushButton("Import")
        import_btn.setObjectName("ghost")
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.setToolTip("Import WAV for voice cloning")
        import_btn.clicked.connect(self._import_voice)
        voice_row.addWidget(import_btn)
        voice_col.addLayout(voice_row)
        layout.addLayout(voice_col)

        # Options
        opts = QHBoxLayout()
        opts.setSpacing(18)
        self.mute = QCheckBox("Mute audio")
        self.fx = QCheckBox("Radio FX")
        self.fx.setChecked(self.app.settings.radio_fx)
        opts.addWidget(self.mute)
        opts.addWidget(self.fx)
        opts.addStretch()
        layout.addLayout(opts)

        self.warn = QLabel("")
        self.warn.setObjectName("warn")
        self.warn.setWordWrap(True)
        self.warn.hide()
        layout.addWidget(self.warn)

        div = QFrame()
        div.setObjectName("divider")
        div.setFixedHeight(1)
        layout.addWidget(div)

        layout.addWidget(self._label("RADIO", "sectionLabel"))
        self.log_view = QTextEdit()
        self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True)
        mono = QFont("Cascadia Mono", 10)
        if not mono.exactMatch():
            mono = QFont("Consolas", 10)
        self.log_view.setFont(mono)
        layout.addWidget(self.log_view, 1)

        # Composer
        chat = QHBoxLayout()
        chat.setSpacing(8)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Message engineer…")
        self.input.returnPressed.connect(self._send_text)
        send = QPushButton("Send")
        send.setObjectName("primary")
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.clicked.connect(self._send_text)
        ptt = QPushButton("PTT")
        ptt.setObjectName("ghost")
        ptt.setCursor(Qt.CursorShape.PointingHandCursor)
        ptt.setToolTip("Record 2.5s from mic")
        ptt.clicked.connect(self._ptt_burst)
        chat.addWidget(self.input, 1)
        chat.addWidget(send)
        chat.addWidget(ptt)
        layout.addLayout(chat)

        tip = QLabel(f"Hold `{self.app.settings.ptt_hotkey}` to talk   ·   drag header to move")
        tip.setObjectName("hint")
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(tip)

        outer.addWidget(body, 1)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 180))
        root.setGraphicsEffect(shadow)

        self._select_data(self.persona, self.app.settings.engineer_persona.value)
        self._select_data(self.gender, self.app.settings.engineer_gender.value)
        self._select_data(self.region, self.app.settings.engineer_region.value)
        self._select_data(self.talk, self.app.settings.talkativeness.value)

        self.persona.currentIndexChanged.connect(self._apply_identity)
        self.gender.currentIndexChanged.connect(self._apply_identity)
        self.region.currentIndexChanged.connect(self._apply_identity)
        self.voice.currentIndexChanged.connect(self._apply_voice)
        self.talk.currentIndexChanged.connect(self._apply_talk)
        self.mute.toggled.connect(lambda v: self.app.set_mute(v))
        self.fx.toggled.connect(lambda v: self.app.set_radio_fx(v))

        self._refresh_status()

    def _label(self, text: str, object_name: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName(object_name)
        return lbl

    def _select_data(self, box: QComboBox, value: str) -> None:
        for i in range(box.count()):
            if box.itemData(i) == value:
                box.setCurrentIndex(i)
                return

    def _reload_voices(self) -> None:
        self.voice.blockSignals(True)
        self.voice.clear()
        for p in self.app.profiles():
            tag = "custom" if p.custom else p.region.upper()
            self.voice.addItem(f"{p.display_name}  ·  {tag}", p.id)
        want = self.app.settings.voice_profile_id or self.app.presentation.voice_profile_id
        self._select_data(self.voice, want)
        self.voice.blockSignals(False)

    def _apply_identity(self) -> None:
        self.app.set_persona(PersonaId(self.persona.currentData()))
        self.app.set_gender(Gender(self.gender.currentData()))
        self.app.set_region(Region(self.region.currentData()))
        data = self.voice.currentData()
        if not data or not str(data).startswith("custom_"):
            pid = f"{self.app.settings.engineer_region.value}_{self.app.settings.engineer_gender.value}"
            self.app.set_voice_profile(pid)
            self._reload_voices()
        self._refresh_status()

    def _apply_voice(self) -> None:
        vid = self.voice.currentData()
        if vid:
            self.app.set_voice_profile(vid)
        self._refresh_status()

    def _apply_talk(self) -> None:
        self.app.set_talkativeness(Talkativeness(self.talk.currentData()))

    def _import_voice(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import voice reference", "", "Audio (*.wav *.mp3 *.flac)"
        )
        if not path:
            return
        name, ok = _simple_input(self, "Name for this voice:")
        if not ok:
            return
        try:
            profile = self.app.import_voice_file(path, name or Path(path).stem)
            self._reload_voices()
            self._select_data(self.voice, profile.id)
            QMessageBox.information(
                self,
                "Voice imported",
                f"Saved as {profile.id}.\nAdd ElevenLabs key or [xtts] for natural cloning.",
            )
        except Exception as e:
            QMessageBox.warning(self, "Import failed", str(e))

    def _send_text(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.bridge.submit(self.app.handle_driver_text(text))

    def _ptt_burst(self) -> None:
        async def _rec() -> None:
            from f1_engineer.voice.stt import record_seconds

            self.bridge.status.emit("Listening…")
            audio = await asyncio.to_thread(record_seconds, 2.5)
            await self.app.handle_ptt_audio(audio)

        self.bridge.submit(_rec())

    def _wire_hotkey(self) -> None:
        try:
            import keyboard

            key = self.app.settings.ptt_hotkey or "grave"
            keyboard.add_hotkey(key, lambda: self._ptt_burst())
            log.info("PTT hotkey bound: %s", key)
        except Exception:
            log.warning("Could not bind global PTT hotkey — use overlay PTT button")

    def _on_radio(self, msg: RadioMessage) -> None:
        color = {
            "driver": C_DRIVER,
            "call": C_ENGINEER,
            "reply": C_ENGINEER,
            "system": C_SYSTEM,
        }.get(msg.kind, C_TEXT)
        self.log_view.append(
            f'<div style="margin:0 0 8px 0;line-height:1.35;">'
            f'<span style="color:{color};font-weight:700;">{_escape(msg.speaker)}</span>'
            f'<span style="color:{C_DIM};">  </span>'
            f'<span style="color:{C_TEXT};">{_escape(msg.text)}</span>'
            f"</div>"
        )

    def _on_status(self, text: str) -> None:
        self.conn.setText(text)

    def _refresh_status(self) -> None:
        snap = self.app.snapshot()
        conn = snap["connection"]
        self.conn.setText(conn)
        live = conn.startswith("Live") or conn.startswith("Mock")
        if live:
            self.status_pill.setObjectName("livePill")
            self.status_dot.setStyleSheet(f"color: {C_LIVE}; font-size: 9px;")
            self.conn.setStyleSheet(f"color: {C_LIVE};")
        else:
            self.status_pill.setObjectName("idlePill")
            self.status_dot.setStyleSheet(f"color: {C_DIM}; font-size: 9px;")
            self.conn.setStyleSheet(f"color: {C_MUTED};")
        # force stylesheet refresh on dynamic objectName change
        self.status_pill.style().unpolish(self.status_pill)
        self.status_pill.style().polish(self.status_pill)

        self.engineer_lbl.setText(snap["engineer"])
        self.engineer_meta.setText(
            f"{snap['persona']}  ·  {snap['region'].upper()}  ·  {snap['gender']}"
        )
        self.rapport_lbl.setText(f"Rapport  {snap['rapport']:.0f}")

        if snap["degraded_voice"] and snap["degraded_reason"]:
            self.warn.setText(snap["degraded_reason"])
            self.warn.show()
        elif not snap["llm"]:
            self.warn.setText("No OPENAI_API_KEY — using template replies only.")
            self.warn.show()
        else:
            self.warn.hide()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_pos = None


def _simple_input(parent, prompt: str) -> tuple[str, bool]:
    from PySide6.QtWidgets import QInputDialog

    text, ok = QInputDialog.getText(parent, "Voice name", prompt)
    return text, bool(ok)


def run_overlay(app: EngineerApp | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    qt = QApplication(sys.argv)
    qt.setQuitOnLastWindowClosed(False)
    qt.setStyle("Fusion")

    for family in ("Segoe UI Variable Display", "Segoe UI Variable", "Segoe UI"):
        if family in QFontDatabase.families():
            qt.setFont(QFont(family, 10))
            break

    eng = app or EngineerApp()
    bridge = AsyncBridge(eng)
    win = OverlayWindow(eng, bridge)

    tray = QSystemTrayIcon(qt)
    tray.setIcon(qt.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
    tray.setToolTip("F1 Race Engineer")
    menu = QMenu()
    show_act = QAction("Show overlay")
    show_act.triggered.connect(win.show)
    quit_act = QAction("Quit")
    quit_act.triggered.connect(qt.quit)
    menu.addAction(show_act)
    menu.addAction(quit_act)
    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: win.show()
        if reason == QSystemTrayIcon.ActivationReason.Trigger
        else None
    )
    tray.show()

    bridge.start()
    win.show()
    code = qt.exec()
    bridge.stop()
    return code
