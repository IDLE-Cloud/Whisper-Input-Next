"""
浮动控制栏：常驻屏幕，提供快速模式和润色模式的鼠标点击入口。
使用 WS_EX_NOACTIVATE 确保点击按钮时不抢走目标窗口的焦点。
"""

from __future__ import annotations

import sys
import threading
import queue
from typing import Callable, Optional
from ..utils.logger import logger


class ControlBar:
    """
    常驻浮动工具栏，包含：
      - 快速录音按钮（等效 Ctrl+Q）
      - 润色录音按钮（等效 Ctrl+空格）
      - 当前状态显示
    点击时不激活本窗口，焦点保留在目标应用。
    """

    # 颜色主题
    _BG          = "#2b2b2b"
    _BTN_IDLE    = "#3c3f41"
    _BTN_HOVER   = "#4c5052"
    _BTN_QUICK   = "#c0392b"   # 快速录音中：红
    _BTN_POLISH  = "#8e44ad"   # 润色录音中：紫
    _BTN_WAITING = "#e67e22"   # 等待处理中：橙
    _TEXT        = "#ffffff"
    _STATUS_TEXT = "#aaaaaa"

    def __init__(
        self,
        on_quick_toggle: Callable,
        on_polish_toggle: Callable,
    ):
        self._on_quick  = on_quick_toggle
        self._on_polish = on_polish_toggle
        self._q: queue.Queue = queue.Queue()

        self._root        = None
        self._quick_btn   = None
        self._polish_btn  = None
        self._status_lbl  = None
        self._drag_x      = 0
        self._drag_y      = 0

        t = threading.Thread(target=self._run_loop, daemon=True, name="control-bar")
        t.start()

    # ── 公开接口（线程安全） ─────────────────────────────────────────────

    def update_state(self, state_name: str) -> None:
        """根据 InputState 名称更新按钮外观。"""
        self._q.put(("state", state_name))

    def show(self) -> None:
        self._q.put(("show", None))

    def hide(self) -> None:
        self._q.put(("hide", None))

    # ── tkinter 主循环（独立线程） ────────────────────────────────────────

    def _run_loop(self) -> None:
        import tkinter as tk

        self._root = tk.Tk()
        self._root.overrideredirect(True)
        self._root.wm_attributes("-topmost", True)
        self._root.wm_attributes("-alpha", 0.92)
        self._root.configure(bg=self._BG)
        self._root.resizable(False, False)

        self._build_ui(tk)
        self._apply_no_activate()

        # 初始定位到屏幕右下角
        self._root.update_idletasks()
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        w  = self._root.winfo_reqwidth()
        h  = self._root.winfo_reqheight()
        self._root.geometry(f"+{sw - w - 20}+{sh - h - 60}")

        self._root.after(50, self._poll)
        self._root.mainloop()

    def _build_ui(self, tk) -> None:
        frame = tk.Frame(self._root, bg=self._BG, padx=6, pady=5)
        frame.pack()

        # 拖动区域（标题栏替代）
        drag = tk.Label(frame, text="⠿ 语音", bg=self._BG,
                        fg=self._STATUS_TEXT, font=("Microsoft YaHei", 9),
                        cursor="fleur")
        drag.pack(side="left", padx=(0, 6))
        drag.bind("<ButtonPress-1>",   self._on_drag_start)
        drag.bind("<B1-Motion>",       self._on_drag_move)

        # 快速模式按钮
        self._quick_btn = tk.Button(
            frame, text="🎤 快速", bg=self._BTN_IDLE, fg=self._TEXT,
            font=("Microsoft YaHei", 10, "bold"),
            relief="flat", bd=0, padx=10, pady=4,
            cursor="hand2", activebackground=self._BTN_HOVER,
            activeforeground=self._TEXT,
            command=self._click_quick,
        )
        self._quick_btn.pack(side="left", padx=2)

        # 润色模式按钮
        self._polish_btn = tk.Button(
            frame, text="✏️ 润色", bg=self._BTN_IDLE, fg=self._TEXT,
            font=("Microsoft YaHei", 10, "bold"),
            relief="flat", bd=0, padx=10, pady=4,
            cursor="hand2", activebackground=self._BTN_HOVER,
            activeforeground=self._TEXT,
            command=self._click_polish,
        )
        self._polish_btn.pack(side="left", padx=2)

        self._status_lbl = tk.Label(frame, text="", bg=self._BG, fg=self._STATUS_TEXT)

    def _apply_no_activate(self) -> None:
        """Windows 专属：点击工具栏时不激活本窗口，保留目标窗口焦点。"""
        if sys.platform != "win32":
            return
        try:
            import ctypes
            GWL_EXSTYLE      = -20
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_TOPMOST    = 0x00000008
            hwnd = self._root.winfo_id()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE,
                style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST
            )
        except Exception as e:
            logger.warning(f"设置 WS_EX_NOACTIVATE 失败: {e}")

    # ── 拖动 ─────────────────────────────────────────────────────────────

    def _on_drag_start(self, event) -> None:
        self._drag_x = event.x_root - self._root.winfo_x()
        self._drag_y = event.y_root - self._root.winfo_y()

    def _on_drag_move(self, event) -> None:
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self._root.geometry(f"+{x}+{y}")

    # ── 按钮点击 ─────────────────────────────────────────────────────────

    def _click_quick(self) -> None:
        threading.Thread(target=self._on_quick, daemon=True).start()

    def _click_polish(self) -> None:
        threading.Thread(target=self._on_polish, daemon=True).start()

    # ── 状态轮询 ─────────────────────────────────────────────────────────

    def _poll(self) -> None:
        try:
            while True:
                cmd, val = self._q.get_nowait()
                if cmd == "state":
                    self._refresh_state(val)
                elif cmd == "show":
                    self._root.deiconify()
                elif cmd == "hide":
                    self._root.withdraw()
        except queue.Empty:
            pass
        if self._root:
            self._root.after(80, self._poll)

    def _refresh_state(self, state_name: str) -> None:
        if self._quick_btn is None:
            return
        s = state_name.upper()

        if "DOUBAO_STREAMING" in s or ("RECORDING" in s and "POLISH" not in s and "KIMI" not in s):
            self._quick_btn.config(bg=self._BTN_QUICK, text="⏹ 停止", state="normal")
            self._polish_btn.config(bg=self._BTN_IDLE, text="✏️ 润色", state="disabled")
            self._status_lbl.config(text="")

        elif "RECORDING_POLISH" in s:
            self._quick_btn.config(bg=self._BTN_IDLE, text="🎤 快速", state="disabled")
            self._polish_btn.config(bg=self._BTN_POLISH, text="⏹ 停止", state="normal")
            self._status_lbl.config(text="")

        elif "PROCESSING_POLISH" in s:
            self._quick_btn.config(bg=self._BTN_IDLE, text="🎤 快速", state="disabled")
            self._polish_btn.config(bg=self._BTN_WAITING, text="⏳ 润色中", state="disabled")
            self._status_lbl.config(text="")

        else:  # IDLE / PROCESSING / ERROR / WARNING 全部显示为可开始状态
            self._quick_btn.config(bg=self._BTN_IDLE, text="🎤 快速", state="normal")
            self._polish_btn.config(bg=self._BTN_IDLE, text="✏️ 润色", state="normal")
            self._status_lbl.config(text="")
