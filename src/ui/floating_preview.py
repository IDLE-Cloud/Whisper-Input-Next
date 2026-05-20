"""浮动预览窗口：macOS 用 AppKit NSPanel，Windows/Linux 用控制台输出。"""

from __future__ import annotations

import sys

if sys.platform == "darwin":
    # ── macOS：原始 AppKit 实现 ──────────────────────────────────────
    import traceback
    from typing import Optional, Tuple

    from AppKit import (
        NSFloatingWindowLevel,
        NSFont,
        NSMakeRect,
        NSMakeSize,
        NSPanel,
        NSTextField,
        NSWindowStyleMaskBorderless,
        NSWindowStyleMaskNonactivatingPanel,
        NSWorkspace,
    )
    from ApplicationServices import (
        AXUIElementCopyAttributeValue,
        AXUIElementCreateApplication,
        kAXFocusedUIElementAttribute,
        kAXPositionAttribute,
        kAXSizeAttribute,
        AXValueGetValue,
        kAXValueTypeCGPoint,
        kAXValueTypeCGSize,
    )
    from Cocoa import NSColor, NSScreen
    from PyObjCTools import AppHelper

    def _get_caret_position() -> Tuple[float, float, float, float]:
        workspace = NSWorkspace.sharedWorkspace()
        front_app = workspace.frontmostApplication()
        if front_app is None:
            raise RuntimeError("无法获取当前激活的应用")
        pid = front_app.processIdentifier()
        app_element = AXUIElementCreateApplication(pid)
        if app_element is None:
            raise RuntimeError("无法创建 AXUIElement")
        err, focused_element = AXUIElementCopyAttributeValue(app_element, kAXFocusedUIElementAttribute, None)
        if err != 0 or focused_element is None:
            raise RuntimeError(f"无法获取焦点元素, error={err}")
        err, position_value = AXUIElementCopyAttributeValue(focused_element, kAXPositionAttribute, None)
        if err != 0 or position_value is None:
            raise RuntimeError("无法获取位置属性")
        err, size_value = AXUIElementCopyAttributeValue(focused_element, kAXSizeAttribute, None)
        if err != 0 or size_value is None:
            raise RuntimeError("无法获取尺寸属性")
        success, point = AXValueGetValue(position_value, kAXValueTypeCGPoint, None)
        if not success:
            raise RuntimeError("无法解析位置值")
        success, size = AXValueGetValue(size_value, kAXValueTypeCGSize, None)
        if not success:
            raise RuntimeError("无法解析尺寸值")
        screen = NSScreen.mainScreen()
        screen_height = screen.frame().size.height
        y_from_bottom = screen_height - point.y - size.height
        return (point.x, y_from_bottom, size.width, size.height)

    class FloatingPreviewWindow:
        def __init__(self, max_width: int = 600, font_size: float = 16.0) -> None:
            self._panel: Optional[NSPanel] = None
            self._text_field: Optional[NSTextField] = None
            self._max_width = max_width
            self._font_size = font_size
            self._is_visible = False
            self._padding_h = 12
            self._padding_v = 8

        def show(self) -> None:
            def _show() -> None:
                if self._panel is None:
                    self._create_panel()
                if self._text_field is not None:
                    self._text_field.setStringValue_("正在聆听...")
                self._position_near_caret()
                self._panel.orderFront_(None)
                self._is_visible = True
            AppHelper.callAfter(_show)

        def hide(self) -> None:
            def _hide() -> None:
                if self._panel is not None:
                    self._panel.orderOut_(None)
                self._is_visible = False
            AppHelper.callAfter(_hide)

        def update_text(self, text: str) -> None:
            def _update() -> None:
                if self._text_field is None:
                    return
                display_text = text if len(text) <= 100 else "..." + text[-97:]
                self._text_field.setStringValue_(display_text if display_text else "正在聆听...")
                self._adjust_size()
            AppHelper.callAfter(_update)

        def _position_near_caret(self) -> None:
            if self._panel is None:
                return
            screen = NSScreen.mainScreen()
            screen_frame = screen.frame()
            panel_frame = self._panel.frame()
            panel_height = panel_frame.size.height
            panel_width = panel_frame.size.width
            try:
                caret_x, caret_y, caret_width, caret_height = _get_caret_position()
                new_x = caret_x
                new_y = caret_y - panel_height - 5
                if new_y < 50:
                    new_y = caret_y + caret_height + 5
                if new_x + panel_width > screen_frame.size.width:
                    new_x = screen_frame.size.width - panel_width - 10
                if new_x < 10:
                    new_x = 10
            except Exception:
                new_x = (screen_frame.size.width - panel_width) / 2
                new_y = screen_frame.size.height - 150
            self._panel.setFrame_display_(NSMakeRect(new_x, new_y, panel_width, panel_height), True)

        def _create_panel(self) -> None:
            screen = NSScreen.mainScreen()
            screen_frame = screen.frame()
            width, height = 300, 50
            x = (screen_frame.size.width - width) / 2
            y = screen_frame.size.height - 150
            style_mask = NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel
            self._panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                NSMakeRect(x, y, width, height), style_mask, 2, False,
            )
            self._panel.setLevel_(NSFloatingWindowLevel)
            self._panel.setOpaque_(False)
            self._panel.setBackgroundColor_(NSColor.colorWithCalibratedRed_green_blue_alpha_(0.1, 0.1, 0.1, 0.85))
            self._panel.setHasShadow_(True)
            self._panel.setMovableByWindowBackground_(True)
            content_view = self._panel.contentView()
            content_view.setWantsLayer_(True)
            layer = content_view.layer()
            layer.setCornerRadius_(10.0)
            layer.setMasksToBounds_(True)
            self._text_field = NSTextField.alloc().initWithFrame_(
                NSMakeRect(self._padding_h, self._padding_v, width - self._padding_h * 2, height - self._padding_v * 2)
            )
            self._text_field.setStringValue_("正在聆听...")
            self._text_field.setBezeled_(False)
            self._text_field.setDrawsBackground_(False)
            self._text_field.setEditable_(False)
            self._text_field.setSelectable_(False)
            self._text_field.setTextColor_(NSColor.whiteColor())
            self._text_field.setFont_(NSFont.systemFontOfSize_(self._font_size))
            self._text_field.setAlignment_(1)
            self._text_field.cell().setWraps_(True)
            self._text_field.cell().setLineBreakMode_(0)
            content_view.addSubview_(self._text_field)

        def _adjust_size(self) -> None:
            if self._panel is None or self._text_field is None:
                return
            text = self._text_field.stringValue()
            if not text:
                return
            cell = self._text_field.cell()
            max_text_width = self._max_width - self._padding_h * 2
            cell_size_at_max = cell.cellSizeForBounds_(NSMakeRect(0, 0, max_text_width, 10000))
            single_line_height = self._font_size + 6
            needs_wrap = cell_size_at_max.height > single_line_height * 1.5
            if needs_wrap:
                new_width = self._max_width
                text_height = cell_size_at_max.height
            else:
                cell_size_single = cell.cellSizeForBounds_(NSMakeRect(0, 0, 10000, single_line_height))
                content_width = cell_size_single.width + self._padding_h * 2 + 10
                new_width = max(min(content_width, self._max_width), 200)
                text_height = single_line_height
            new_height = max(text_height + self._padding_v * 2, 36)
            frame = self._panel.frame()
            new_y = frame.origin.y + frame.size.height - new_height
            self._panel.setFrame_display_(NSMakeRect(frame.origin.x, new_y, new_width, new_height), True)
            self._text_field.setFrame_(
                NSMakeRect(self._padding_h, self._padding_v, new_width - self._padding_h * 2, new_height - self._padding_v * 2)
            )

else:
    # ── Windows / Linux：控制台输出预览 ──────────────────────────────

    import tkinter as tk
    import queue as _queue
    import threading as _threading

    class FloatingPreviewWindow:
        """Windows 下用 tkinter 显示不抢焦点的浮动预览窗口。"""

        def __init__(self, max_width: int = 600, font_size: float = 16.0) -> None:
            self._q: _queue.Queue = _queue.Queue()
            self._root = None
            self._label = None
            # tkinter 主循环运行在独立线程，不占用主线程，也不抢焦点
            t = _threading.Thread(target=self._run_loop, daemon=True)
            t.start()

        def _run_loop(self) -> None:
            self._root = tk.Tk()
            self._root.overrideredirect(True)          # 无标题栏
            self._root.wm_attributes('-topmost', True) # 始终置顶
            self._root.wm_attributes('-alpha', 0.88)   # 半透明
            self._root.configure(bg='#1c1c1c')
            self._root.withdraw()                      # 默认隐藏

            # Windows 专属：WS_EX_NOACTIVATE 彻底禁止窗口抢焦点
            try:
                import ctypes
                GWL_EXSTYLE = -20
                WS_EX_NOACTIVATE = 0x08000000
                WS_EX_TOOLWINDOW = 0x00000080
                hwnd = self._root.winfo_id()
                style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                ctypes.windll.user32.SetWindowLongW(
                    hwnd, GWL_EXSTYLE,
                    style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
                )
            except Exception:
                pass

            self._label = tk.Label(
                self._root,
                text="正在聆听...",
                fg='white',
                bg='#1c1c1c',
                font=('Microsoft YaHei', 13),
                wraplength=560,
                justify='left',
                padx=12,
                pady=8,
            )
            self._label.pack()

            # 定位到屏幕顶部居中
            self._root.update_idletasks()
            w = self._root.winfo_reqwidth()
            self._root.geometry(f'+{(self._root.winfo_screenwidth()-w)//2}+60')

            self._root.after(50, self._poll)
            self._root.mainloop()

        def _poll(self) -> None:
            """每 50ms 处理一次队列里的指令，不阻塞 tkinter 事件循环。"""
            try:
                while True:
                    cmd, val = self._q.get_nowait()
                    if cmd == 'show':
                        self._label.config(text='正在聆听...')
                        self._root.deiconify()
                        # 明确不抢焦点
                        self._root.update_idletasks()
                    elif cmd == 'hide':
                        self._root.withdraw()
                    elif cmd == 'update' and self._label:
                        display = val if len(val) <= 80 else '...' + val[-77:]
                        self._label.config(text=display)
                        # 重新居中（文字变长时）
                        self._root.update_idletasks()
                        w = self._root.winfo_reqwidth()
                        self._root.geometry(
                            f'+{(self._root.winfo_screenwidth()-w)//2}+60'
                        )
            except _queue.Empty:
                pass
            if self._root:
                self._root.after(50, self._poll)

        def show(self) -> None:
            self._q.put(('show', None))

        def hide(self) -> None:
            self._q.put(('hide', None))

        def update_text(self, text: str) -> None:
            self._q.put(('update', text))
