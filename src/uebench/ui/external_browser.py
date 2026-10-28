"""冻结 Windows 程序仅在外部打开请求期间恢复系统 DLL 搜索环境。

依据 PyInstaller 6.20 common-issues-and-pitfalls / Launching External Programs。
这不能保证浏览器呈现，也不改变默认应用或安全权限。
"""
from contextlib import contextmanager
import os
from pathlib import Path
import sys


@contextmanager
def external_browser_environment():
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        yield
        return
    import ctypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    get_directory = kernel.GetDllDirectoryW
    get_directory.argtypes = [ctypes.c_uint32, ctypes.c_wchar_p]
    get_directory.restype = ctypes.c_uint32
    set_directory = kernel.SetDllDirectoryW
    set_directory.argtypes = [ctypes.c_wchar_p]
    set_directory.restype = ctypes.c_int
    size = get_directory(0, None)
    buffer = ctypes.create_unicode_buffer(size + 1)
    get_directory(len(buffer), buffer)
    previous_directory = buffer.value
    previous_path = os.environ.get("PATH")
    bundle = Path(sys._MEIPASS).resolve()
    def outside_bundle(entry):
        try:
            return not Path(entry).resolve().is_relative_to(bundle)
        except (OSError, ValueError):
            return True
    if not set_directory(None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if previous_path is not None:
            os.environ["PATH"] = os.pathsep.join(p for p in previous_path.split(os.pathsep) if outside_bundle(p))
        yield
    finally:
        if previous_path is None:
            os.environ.pop("PATH", None)
        else:
            os.environ["PATH"] = previous_path
        if not set_directory(previous_directory or None):
            raise ctypes.WinError(ctypes.get_last_error())
