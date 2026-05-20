"""状态栏控制器：macOS 用系统托盘图标，Windows/Linux 用控制台输出。"""

from __future__ import annotations

import os
import sys

from src.keyboard.inputState import InputState

if sys.platform == "darwin":
    # ── macOS：原始 AppKit 实现 ──────────────────────────────────────
    from dataclasses import dataclass
    from typing import Dict, Optional, Tuple

    from AppKit import NSImageOnly, NSImageScaleProportionallyDown
    from Cocoa import (
        NSApplication,
        NSApplicationActivationPolicyProhibited,
        NSImage,
        NSMenu,
        NSMenuItem,
        NSStatusBar,
        NSVariableStatusItemLength,
    )
    from PyObjCTools import AppHelper

    @dataclass(frozen=True)
    class _StateVisual:
        fallback_text: str
        description: str
        env_key: str

    _STATE_VISUALS = {
        InputState.IDLE: _StateVisual("🎙️", "空闲", "IDLE"),
        InputState.RECORDING: _StateVisual("🔴", "录音中 (OpenAI)", "RECORDING"),
        InputState.RECORDING_TRANSLATE: _StateVisual("🔴", "录音中 (翻译)", "RECORDING"),
        InputState.RECORDING_KIMI: _StateVisual("🟠", "录音中 (本地 Whisper)", "RECORDING"),
        InputState.DOUBAO_STREAMING: _StateVisual("🟢", "流式识别中 (豆包)", "RECORDING"),
        InputState.PROCESSING: _StateVisual("🔵", "转录处理中", "PROCESSING"),
        InputState.PROCESSING_KIMI: _StateVisual("🔵", "转录处理中", "PROCESSING"),
        InputState.TRANSLATING: _StateVisual("🟡", "翻译中", "PROCESSING"),
        InputState.WARNING: _StateVisual("⚠️", "警告", "PROCESSING"),
        InputState.ERROR: _StateVisual("❗️", "错误", "PROCESSING"),
    }

    class StatusBarController:
        def __init__(self) -> None:
            self._status_item = None
            self._menu = None
            self._current_state: InputState = InputState.IDLE
            self._queue_length: int = 0
            self._custom_icons: Dict[str, NSImage] = {}
            self._load_custom_icons()

        def start(self) -> None:
            AppHelper.callAfter(self._setup)
            AppHelper.runConsoleEventLoop()

        def update_state(self, state: InputState, *, queue_length: int = 0) -> None:
            queue_length = max(0, queue_length)
            def _apply() -> None:
                self._current_state = state
                self._queue_length = queue_length
                self._refresh()
            AppHelper.callAfter(_apply)

        def _setup(self) -> None:
            app = NSApplication.sharedApplication()
            app.setActivationPolicy_(NSApplicationActivationPolicyProhibited)
            status_bar = NSStatusBar.systemStatusBar()
            self._status_item = status_bar.statusItemWithLength_(NSVariableStatusItemLength)
            button = self._status_item.button()
            if button is not None:
                button.setTitle_("🎙️")
                button.setToolTip_("Whisper-Input - 空闲")
            self._menu = NSMenu.alloc().init()
            quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Quit Whisper-Input", "terminate:", ""
            )
            self._menu.addItem_(quit_item)
            self._status_item.setMenu_(self._menu)
            self._refresh()

        def _refresh(self) -> None:
            if self._status_item is None:
                return
            button = self._status_item.button()
            if button is None:
                return
            title, image, tooltip = self._icon_and_tooltip()
            if image is not None:
                image.setSize_((18.0, 18.0))
                button.setImage_(image)
                button.setTitle_(title)
                button.setImageScaling_(NSImageScaleProportionallyDown)
                button.setImagePosition_(NSImageOnly)
            else:
                button.setImage_(None)
                button.setTitle_(title)
                button.setImagePosition_(0)
            button.setToolTip_(tooltip)

        def _icon_and_tooltip(self) -> Tuple[str, Optional[NSImage], str]:
            visual = _STATE_VISUALS.get(self._current_state, _STATE_VISUALS[InputState.IDLE])
            image = self._custom_icons.get(visual.env_key)
            title = ""
            if image is None:
                title = visual.fallback_text
                if self._queue_length:
                    title = f"{title}{self._queue_length}" if self._queue_length < 10 else f"{title}*"
            elif self._queue_length:
                title = f" {self._queue_length if self._queue_length < 10 else '*'}"
            tooltip = f"Whisper-Input - {visual.description}"
            if self._queue_length:
                tooltip += f" | 待处理任务 {self._queue_length}"
            return title, image, tooltip

        def _load_custom_icons(self) -> None:
            template_flag = os.getenv("STATUS_ICON_TEMPLATE", "false").lower() == "true"
            base_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "assets", "icons")
            )
            def _resolve_path(env_key: str) -> Optional[str]:
                env_path = os.getenv(f"STATUS_ICON_{env_key}")
                if env_path:
                    return env_path
                default_name = {"IDLE": "idle.png", "RECORDING": "recording.png", "PROCESSING": "transcripting.png"}.get(env_key)
                if not default_name:
                    return None
                return os.path.join(base_dir, default_name)
            def _try_load(env_key: str) -> None:
                path = _resolve_path(env_key)
                if not path or not os.path.exists(path):
                    return
                image = NSImage.alloc().initWithContentsOfFile_(path)
                if image is None:
                    return
                image.setTemplate_(template_flag)
                self._custom_icons[env_key] = image
            for visual in _STATE_VISUALS.values():
                _try_load(visual.env_key)

else:
    # ── Windows / Linux：控制台状态输出 ─────────────────────────────
    import threading

    _STATE_LABELS = {
        InputState.IDLE: "空闲 🎙️",
        InputState.RECORDING: "录音中 🔴",
        InputState.RECORDING_TRANSLATE: "录音中(翻译) 🔴",
        InputState.RECORDING_KIMI: "录音中(Whisper) 🟠",
        InputState.DOUBAO_STREAMING: "流式识别中(豆包) 🟢",
        InputState.PROCESSING: "转录处理中 🔵",
        InputState.PROCESSING_KIMI: "转录处理中 🔵",
        InputState.TRANSLATING: "翻译中 🟡",
        InputState.WARNING: "警告 ⚠️",
        InputState.ERROR: "错误 ❗",
    }

    class StatusBarController:
        def __init__(self) -> None:
            self._stop_event = threading.Event()

        def start(self) -> None:
            """Windows 下阻塞主线程直到程序退出。"""
            print("[Whisper-Input] 已启动，按 Ctrl+C 退出")
            try:
                while not self._stop_event.is_set():
                    self._stop_event.wait(timeout=0.5)
            except KeyboardInterrupt:
                print("\n[Whisper-Input] 退出")

        def update_state(self, state: InputState, *, queue_length: int = 0) -> None:
            label = _STATE_LABELS.get(state, str(state))
            queue_info = f" | 队列: {queue_length}" if queue_length else ""
            print(f"\r[状态] {label}{queue_info}          ", end="", flush=True)
