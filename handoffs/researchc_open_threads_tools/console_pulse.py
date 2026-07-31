"""Inject one inert F24 key event into another Windows console.

The Research C collectors use this only to keep Sable's five-minute idle
check-in from racing the one-slot director.  F24 is not bound by the UI:
``msvcrt`` reports it as an unknown extended key, which resets the input-idle
timer without changing the draft, music controls, or conversation.
"""

import ctypes
from ctypes import wintypes
import sys


KEY_EVENT = 0x0001
STD_INPUT_HANDLE = -10
VK_F24 = 0x87
MAPVK_VK_TO_VSC = 0
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class _Character(ctypes.Union):
    _fields_ = [
        ("UnicodeChar", wintypes.WCHAR),
        ("AsciiChar", wintypes.CHAR),
    ]


class _KeyEvent(ctypes.Structure):
    _fields_ = [
        ("bKeyDown", wintypes.BOOL),
        ("wRepeatCount", wintypes.WORD),
        ("wVirtualKeyCode", wintypes.WORD),
        ("wVirtualScanCode", wintypes.WORD),
        ("uChar", _Character),
        ("dwControlKeyState", wintypes.DWORD),
    ]


class _Event(ctypes.Union):
    _fields_ = [
        ("KeyEvent", _KeyEvent),
        ("padding", ctypes.c_byte * 16),
    ]


class _InputRecord(ctypes.Structure):
    _fields_ = [
        ("EventType", wintypes.WORD),
        ("Event", _Event),
    ]


def pulse(process_id):
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.FreeConsole.argtypes = ()
    kernel32.FreeConsole.restype = wintypes.BOOL
    kernel32.AttachConsole.argtypes = (wintypes.DWORD,)
    kernel32.AttachConsole.restype = wintypes.BOOL
    kernel32.GetStdHandle.argtypes = (wintypes.DWORD,)
    kernel32.GetStdHandle.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
    user32.MapVirtualKeyW.restype = wintypes.UINT
    kernel32.WriteConsoleInputW.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(_InputRecord),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.WriteConsoleInputW.restype = wintypes.BOOL
    kernel32.FreeConsole()
    if not kernel32.AttachConsole(wintypes.DWORD(process_id)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        handle = kernel32.CreateFileW(
            "CONIN$",
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0,
            None,
        )
        if handle in (0, INVALID_HANDLE_VALUE):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            scan = user32.MapVirtualKeyW(VK_F24, MAPVK_VK_TO_VSC)
            records = (_InputRecord * 2)()
            for index, key_down in enumerate((True, False)):
                records[index].EventType = KEY_EVENT
                records[index].Event.KeyEvent.bKeyDown = key_down
                records[index].Event.KeyEvent.wRepeatCount = 1
                records[index].Event.KeyEvent.wVirtualKeyCode = VK_F24
                records[index].Event.KeyEvent.wVirtualScanCode = scan
                records[index].Event.KeyEvent.uChar.UnicodeChar = "\0"
                records[index].Event.KeyEvent.dwControlKeyState = 0
            written = wintypes.DWORD()
            if not kernel32.WriteConsoleInputW(
                handle,
                records,
                len(records),
                ctypes.byref(written),
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            if written.value != len(records):
                raise RuntimeError(
                    f"wrote {written.value} console records, "
                    f"expected {len(records)}"
                )
        finally:
            kernel32.CloseHandle(handle)
    finally:
        kernel32.FreeConsole()


def main(argv=None):
    values = list(sys.argv[1:] if argv is None else argv)
    if len(values) != 1:
        raise SystemExit("usage: console_pulse.py PROCESS_ID")
    pulse(int(values[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
