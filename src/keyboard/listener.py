from pynput.keyboard import Controller, Key, Listener
import pyperclip
from ..utils.logger import logger
import time
import sys
from .inputState import InputState
import os


class KeyboardManager:
    def __init__(self, on_record_start, on_record_stop, on_translate_start, on_translate_stop, on_kimi_start, on_kimi_stop, on_reset_state, on_state_change=None, on_polish_start=None, on_polish_stop=None):
        self.keyboard = Controller()
        self.ctrl_pressed = False
        self.f_pressed = False
        self.i_pressed = False
        self.e_pressed = False
        self.space_pressed = False  # 润色模式（Ctrl+空格）
        self.temp_text_length = 0
        self.processing_text = None
        self.error_message = None
        self.warning_message = None
        self.is_recording = False
        self.last_key_time = 0
        self.KEY_DEBOUNCE_TIME = 0.3
        self._original_clipboard = None
        self._target_hwnd = None
        self._start_focus_tracker()

        # 回调函数
        self.on_record_start = on_record_start
        self.on_record_stop = on_record_stop
        self.on_translate_start = on_translate_start
        self.on_translate_stop = on_translate_stop
        self.on_kimi_start = on_kimi_start
        self.on_kimi_stop = on_kimi_stop
        self.on_reset_state = on_reset_state
        self.on_state_change = on_state_change
        self.on_polish_start = on_polish_start
        self.on_polish_stop = on_polish_stop

        
        # 状态管理
        self._state = InputState.IDLE
        self._state_messages = {
            InputState.IDLE: "",
            InputState.RECORDING: "0",
            InputState.RECORDING_TRANSLATE: "0",
            InputState.RECORDING_KIMI: "0",
            InputState.RECORDING_POLISH: "0",
            InputState.PROCESSING: "1",
            InputState.PROCESSING_KIMI: "1",
            InputState.PROCESSING_POLISH: "1",
            InputState.TRANSLATING: "1",
            InputState.ERROR: lambda msg: f"{msg}",
            InputState.WARNING: lambda msg: f"! {msg}"
        }

        self.state_symbol_enabled = True

        # 获取系统平台（支持 .env 配置或自动检测）
        sysetem_platform = os.getenv("SYSTEM_PLATFORM")
        if sysetem_platform == "win" or (sysetem_platform is None and sys.platform == "win32"):
            self.sysetem_platform = Key.ctrl
            logger.info("配置到Windows平台")
        else:
            self.sysetem_platform = Key.cmd
            logger.info("配置到Mac平台")
        

        # 获取转录和翻译按钮
        transcriptions_button = os.getenv("TRANSCRIPTIONS_BUTTON")
        try:
            # 字符键（如f）直接使用字符串，特殊键使用Key枚举
            if len(transcriptions_button) == 1 and transcriptions_button.isalpha():
                self.transcriptions_button = transcriptions_button
            else:
                self.transcriptions_button = Key[transcriptions_button]
            logger.info(f"配置到转录按钮：{transcriptions_button}")
        except KeyError:
            logger.error(f"无效的转录按钮配置：{transcriptions_button}")

        translations_button = os.getenv("TRANSLATIONS_BUTTON")
        try:
            # 字符键（如f）直接使用字符串，特殊键使用Key枚举
            if len(translations_button) == 1 and translations_button.isalpha():
                self.translations_button = translations_button
            else:
                self.translations_button = Key[translations_button]
            logger.info(f"配置到翻译按钮(与转录按钮组合)：{translations_button}")
        except KeyError:
            logger.error(f"无效的翻译按钮配置：{translations_button}")

        logger.info(f"按 {translations_button} + {transcriptions_button} 键：切换录音状态（OpenAI GPT-4o transcribe 模式）")
        logger.info(f"按 {translations_button} + I 键：切换录音状态（本地 Whisper 模式）")
        logger.info(f"两种模式都是按一下开始，再按一下结束")
    
    @property
    def state(self):
        """获取当前状态"""
        return self._state
    
    @state.setter
    def state(self, new_state):
        """设置新状态并更新UI"""
        if new_state != self._state:
            self._state = new_state
            
            # 获取状态消息
            message = self._state_messages[new_state]
            
            # 根据状态转换类型显示不同消息
            if new_state == InputState.RECORDING:
                # 录音状态
                self.temp_text_length = 0
                if self.state_symbol_enabled:
                    self.type_temp_text(message)
                self.on_record_start()
                
            elif new_state == InputState.RECORDING_TRANSLATE:
                # 翻译,录音状态
                self.temp_text_length = 0
                if self.state_symbol_enabled:
                    self.type_temp_text(message)
                self.on_translate_start()
                
            elif new_state == InputState.RECORDING_KIMI:
                # 本地 Whisper 录音状态
                self.temp_text_length = 0
                if self.state_symbol_enabled:
                    self.type_temp_text(message)
                self.on_kimi_start()

            elif new_state == InputState.PROCESSING:
                self._delete_previous_text()
                if self.state_symbol_enabled:
                    self.type_temp_text(message)
                self.processing_text = message
                self.on_record_stop()
                
            elif new_state == InputState.PROCESSING_KIMI:
                # 本地 Whisper 处理状态
                self._delete_previous_text()
                if self.state_symbol_enabled:
                    self.type_temp_text(message)
                self.processing_text = message
                self.on_kimi_stop()

            elif new_state == InputState.TRANSLATING:
                # 翻译状态
                self._delete_previous_text()                 
                if self.state_symbol_enabled:
                    self.type_temp_text(message)
                self.processing_text = message
                self.on_translate_stop()
            
            elif new_state == InputState.WARNING:
                # 警告状态
                message = message(self.warning_message)
                self._delete_previous_text()
                if self.state_symbol_enabled:
                    self.type_temp_text(message)
                self.warning_message = None
                self._schedule_message_clear()     
            
            elif new_state == InputState.ERROR:
                # 错误状态
                message = message(self.error_message)
                self._delete_previous_text()
                if self.state_symbol_enabled:
                    self.type_temp_text(message)
                self.error_message = None
                self._schedule_message_clear()  
        
            elif new_state == InputState.IDLE:
                # 空闲状态，清除所有临时文本
                self.processing_text = None
            
            else:
                # 其他状态
                if self.state_symbol_enabled:
                    self.type_temp_text(message)

            if self.on_state_change:
                try:
                    self.on_state_change(new_state)
                except Exception as exc:  # noqa: BLE001
                    logger.debug(f"状态回调异常: {exc}")

    def set_state_symbol_enabled(self, enabled: bool):
        """开启或关闭在输入框内展示状态符号"""
        self.state_symbol_enabled = enabled
    
    def _schedule_message_clear(self):
        """计划清除消息"""
        def clear_message():
            time.sleep(2)  # 警告消息显示2秒
            self.state = InputState.IDLE
        
        import threading
        threading.Thread(target=clear_message, daemon=True).start()
    
    def show_warning(self, warning_message):
        """显示警告消息"""
        self.warning_message = warning_message
        self.state = InputState.WARNING
    
    def show_error(self, error_message):
        """显示错误消息"""
        self.error_message = error_message
        self.state = InputState.ERROR
    
    def _save_clipboard(self):
        """保存当前剪贴板内容"""
        if self._original_clipboard is None:
            self._original_clipboard = pyperclip.paste()

    def _restore_clipboard(self):
        """恢复原始剪贴板内容"""
        if self._original_clipboard is not None:
            pyperclip.copy(self._original_clipboard)
            self._original_clipboard = None

    def type_text(self, text, error_message=None):
        """将文字输入到当前光标位置
        
        Args:
            text: 要输入的文本或包含文本和错误信息的元组
            error_message: 错误信息
        """
        # 如果text是元组，说明是从process_audio返回的结果
        if isinstance(text, tuple):
            text, error_message = text
            
        if error_message:
            self.show_error(error_message)
            return
            
        if not text:
            # 如果没有文本且不是错误，可能是录音时长不足
            if self.state in (InputState.PROCESSING, InputState.TRANSLATING):
                self.show_warning("录音时长过短，请至少录制1秒")
            return
            
        try:
            logger.info("正在输入转录文本...")
            self._delete_previous_text()

            # 还原焦点到录音前的目标窗口，确保粘贴到正确位置
            self._restore_target_window()

            # 最终转录文本通过剪贴板输入
            pyperclip.copy(text)

            # 模拟 Ctrl + V 粘贴文本
            with self.keyboard.pressed(self.sysetem_platform):
                self.keyboard.press('v')
                self.keyboard.release('v')
            
            # 等待一小段时间确保文本已输入
            time.sleep(0.5)
            
            logger.info("文本输入完成")

            # 清理处理状态（流式识别中不重置，保持录音状态）
            # 录音状态中输出文字（流式 definite 输出），不重置状态
            if not self.state.is_recording:
                self.state = InputState.IDLE
        except Exception as e:
            logger.error(f"文本输入失败: {e}")
            self.show_error(f"❌ 文本输入失败: {e}")
    
    def _delete_previous_text(self):
        """删除之前输入的临时文本"""
        if self.temp_text_length > 0:
            # 添加0.2秒延迟，让删除操作更自然
            import time
            time.sleep(0.2)
            
            for _ in range(self.temp_text_length):
                self.keyboard.press(Key.backspace)
                self.keyboard.release(Key.backspace)

        self.temp_text_length = 0
    
    def type_temp_text(self, text):
        """输入临时状态文本"""
        if not text or not self.state_symbol_enabled:
            return
            
        # 判断是否为状态符号（现在使用数字）
        is_status_symbol = text in ['0', '1']
        
        if is_status_symbol:
            # 状态符号直接输入，不使用剪贴板
            try:
                self.keyboard.type(text)
            except Exception as e:
                # 如果直接输入失败，记录错误但不中断程序
                logger.warning(f"直接输入状态符号失败: {e}, 文本: {text}")
        else:
            # 其他文本（如错误消息、警告等）通过剪贴板输入
            pyperclip.copy(text)
            with self.keyboard.pressed(self.sysetem_platform):
                self.keyboard.press('v')
                self.keyboard.release('v')
        
        # 更新临时文本长度
        self.temp_text_length = len(text)
    
    def _start_focus_tracker(self) -> None:
        """后台线程持续跟踪前台窗口，自动更新粘贴目标（排除本进程窗口）。"""
        if sys.platform != 'win32':
            return
        import ctypes
        import os as _os

        our_pid = _os.getpid()

        def _track():
            prev_hwnd = None
            while True:
                try:
                    hwnd = ctypes.windll.user32.GetForegroundWindow()
                    if hwnd and hwnd != prev_hwnd:
                        pid = ctypes.c_ulong(0)
                        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        if pid.value != our_pid:
                            self._target_hwnd = hwnd
                        prev_hwnd = hwnd
                except Exception:
                    pass
                time.sleep(0.3)

        import threading as _th
        t = _th.Thread(target=_track, daemon=True, name="focus-tracker")
        t.start()

    def _save_target_window(self) -> None:
        """保存当前前台窗口句柄（焦点跟踪线程已实时维护，此处作备用）。"""
        if sys.platform == 'win32' and not getattr(self, '_target_hwnd', None):
            try:
                import ctypes
                self._target_hwnd = ctypes.windll.user32.GetForegroundWindow()
            except Exception:
                self._target_hwnd = None

    def _restore_target_window(self) -> None:
        """还原焦点到录音前的目标窗口。"""
        if sys.platform != 'win32' or not getattr(self, '_target_hwnd', None):
            return
        try:
            import ctypes
            hwnd = self._target_hwnd
            # AttachThreadInput 技巧：绕过 Windows 前台窗口限制
            fg_thread = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, None)
            cur_thread = ctypes.windll.kernel32.GetCurrentThreadId()
            ctypes.windll.user32.AttachThreadInput(cur_thread, fg_thread, True)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.BringWindowToTop(hwnd)
            ctypes.windll.user32.AttachThreadInput(cur_thread, fg_thread, False)
            time.sleep(0.15)
        except Exception as e:
            logger.warning(f"还原目标窗口失败: {e}")

    def toggle_recording(self):
        """切换录音状态"""
        current_time = time.time()

        # 防抖处理
        if current_time - self.last_key_time < self.KEY_DEBOUNCE_TIME:
            return

        self.last_key_time = current_time

        if not self.is_recording:
            # 开始录音前记住目标窗口
            self._save_target_window()
            if self.state.can_start_recording:
                self.is_recording = True
                self.state = InputState.RECORDING
                logger.info("🎤 开始录音（OpenAI GPT-4o transcribe 模式）")
        else:
            # 停止录音
            self.is_recording = False
            self.state = InputState.PROCESSING
            logger.info("⏹️ 停止录音（OpenAI GPT-4o transcribe 模式）")
    
    def toggle_kimi_recording(self):
        """切换本地 Whisper 录音状态"""
        current_time = time.time()

        # 防抖处理
        if current_time - self.last_key_time < self.KEY_DEBOUNCE_TIME:
            return

        self.last_key_time = current_time
        
        if not self.is_recording:
            # 开始录音
            if self.state.can_start_recording:
                self.is_recording = True
                self.state = InputState.RECORDING_KIMI
                logger.info("🎤 开始录音（本地 Whisper 模式）")
        else:
            # 停止录音
            self.is_recording = False
            self.state = InputState.PROCESSING_KIMI
            logger.info("⏹️ 停止录音（本地 Whisper 模式）")

    def toggle_polish_recording(self):
        """切换润色录音状态（Ctrl+E）：说完后交 LLM 润色再输出"""
        current_time = time.time()

        if current_time - self.last_key_time < self.KEY_DEBOUNCE_TIME:
            return
        self.last_key_time = current_time

        if not self.is_recording:
            if self.state.can_start_recording:
                self._save_target_window()
                self.is_recording = True
                self.state = InputState.RECORDING_POLISH
                if self.on_polish_start:
                    self.on_polish_start()
                logger.info("✏️ 开始润色录音（说完按 Ctrl+E 结束）")
        else:
            self.is_recording = False
            self.state = InputState.PROCESSING_POLISH
            if self.on_polish_stop:
                self.on_polish_stop()
            logger.info("⏹️ 停止润色录音，等待 LLM 润色...")

    # Ctrl/Shift/Alt 的左右变体映射
    _KEY_VARIANTS = {
        Key.ctrl: (Key.ctrl, Key.ctrl_l, Key.ctrl_r),
        Key.ctrl_l: (Key.ctrl, Key.ctrl_l, Key.ctrl_r),
        Key.ctrl_r: (Key.ctrl, Key.ctrl_l, Key.ctrl_r),
        Key.shift: (Key.shift, Key.shift_l, Key.shift_r),
        Key.shift_l: (Key.shift, Key.shift_l, Key.shift_r),
        Key.shift_r: (Key.shift, Key.shift_l, Key.shift_r),
        Key.alt: (Key.alt, Key.alt_l, Key.alt_r),
        Key.alt_l: (Key.alt, Key.alt_l, Key.alt_r),
        Key.alt_r: (Key.alt, Key.alt_l, Key.alt_r),
    }

    def _match_special_key(self, key, target) -> bool:
        """匹配特殊键，兼容左右变体（Key.ctrl_l 匹配 Key.ctrl 等）"""
        if key == target:
            return True
        variants = self._KEY_VARIANTS.get(target)
        if variants and key in variants:
            return True
        return False

    def _match_char_key(self, key, char: str) -> bool:
        """匹配字符键，兼容 Ctrl 组合键时 key.char 变为控制字符的情况"""
        if hasattr(key, 'char') and key.char == char:
            return True
        if hasattr(key, 'vk') and key.vk == ord(char.upper()):
            return True
        return False

    def on_press(self, key):
        """按键按下时的回调"""
        try:
            # 检查转录按钮（字符键或特殊键）
            is_transcription_key = False
            if isinstance(self.transcriptions_button, str):
                is_transcription_key = self._match_char_key(key, self.transcriptions_button)
            else:
                # 特殊键
                is_transcription_key = self._match_special_key(key, self.transcriptions_button)

            # 检查翻译按钮（字符键或特殊键）
            is_translation_key = False
            if isinstance(self.translations_button, str):
                is_translation_key = self._match_char_key(key, self.translations_button)
            else:
                # 特殊键
                is_translation_key = self._match_special_key(key, self.translations_button)

            # 检查空格键（润色模式 Ctrl+空格）
            if key == Key.space:
                self.space_pressed = True
                if self.ctrl_pressed and self.space_pressed:
                    self.toggle_polish_recording()
            # 检查I键（本地 Whisper 模式）
            elif self._match_char_key(key, 'i'):
                self.i_pressed = True
                if self.ctrl_pressed and self.i_pressed:
                    self.toggle_kimi_recording()
            elif is_transcription_key:
                self.f_pressed = True
                if self.ctrl_pressed and self.f_pressed:
                    self.toggle_recording()
            elif is_translation_key:  # Ctrl键
                self.ctrl_pressed = True
                if self.ctrl_pressed and self.f_pressed:
                    self.toggle_recording()
                elif self.ctrl_pressed and self.i_pressed:
                    self.toggle_kimi_recording()
                elif self.ctrl_pressed and self.space_pressed:
                    self.toggle_polish_recording()
        except AttributeError:
            pass

    def on_release(self, key):
        """按键释放时的回调"""
        try:
            # 检查转录按钮（字符键或特殊键）
            is_transcription_key = False
            if isinstance(self.transcriptions_button, str):
                is_transcription_key = self._match_char_key(key, self.transcriptions_button)
            else:
                is_transcription_key = self._match_special_key(key, self.transcriptions_button)

            # 检查翻译按钮（字符键或特殊键）
            is_translation_key = False
            if isinstance(self.translations_button, str):
                is_translation_key = self._match_char_key(key, self.translations_button)
            else:
                is_translation_key = self._match_special_key(key, self.translations_button)

            if key == Key.space:
                self.space_pressed = False
            elif self._match_char_key(key, 'i'):
                self.i_pressed = False
            elif is_transcription_key:
                self.f_pressed = False
            elif is_translation_key:
                self.ctrl_pressed = False

        except AttributeError:
            pass
    
    def start_listening(self):
        """开始监听键盘事件"""
        with Listener(on_press=self.on_press, on_release=self.on_release) as listener:
            listener.join()

    def reset_state(self):
        """重置所有状态和临时文本"""
        # 清除临时文本
        self._delete_previous_text()
        
        # 恢复剪贴板
        self._restore_clipboard()
        
        # 重置状态标志
        self.ctrl_pressed = False
        self.f_pressed = False
        self.i_pressed = False
        self.is_recording = False
        self.last_key_time = time.time()
        self.processing_text = None
        self.error_message = None
        self.warning_message = None
        
        # 设置为空闲状态
        self.state = InputState.IDLE

def check_accessibility_permissions():
    """检查是否有辅助功能权限并提供指导"""
    logger.warning("\n=== macOS 辅助功能权限检查 ===")
    logger.warning("此应用需要辅助功能权限才能监听键盘事件。")
    logger.warning("\n请按照以下步骤授予权限：")
    logger.warning("1. 打开 系统偏好设置")
    logger.warning("2. 点击 隐私与安全性")
    logger.warning("3. 点击左侧的 辅助功能")
    logger.warning("4. 点击右下角的锁图标并输入密码")
    logger.warning("5. 在右侧列表中找到 Terminal（或者您使用的终端应用）并勾选")
    logger.warning("\n授权后，请重新运行此程序。")
    logger.warning("===============================\n") 
