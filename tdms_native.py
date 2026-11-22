"""
TDMS native Windows helpers (no add-on needed):
    enable_drop(window, callback)   files dragged from Explorer onto the TDMS window
    drag_files(window, paths)       drag real files out of TDMS to Explorer / desktop / mail / chat
Everything is wrapped so a problem here never stops TDMS; the functions simply return False.
"""
import os
from pathlib import Path

WM_DROPFILES = 0x0233
WM_COPYGLOBALDATA = 0x0049
GWL_WNDPROC = -4
_keep = {}


def available():
    return os.name == "nt"


def _top_hwnd(widget):
    import ctypes
    widget.update_idletasks()
    child = widget.winfo_id()
    return ctypes.windll.user32.GetParent(child) or child


def enable_drop(widget, callback):
    """callback(files: list[str], screen_x: int, screen_y: int) is called on the Tk thread."""
    if not available():
        return False
    try:
        import ctypes
        from ctypes import wintypes
        user32, shell32 = ctypes.windll.user32, ctypes.windll.shell32
        hwnd = _top_hwnd(widget)
        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        user32.CallWindowProcW.restype = LRESULT
        user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        setlong = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
        setlong.restype = ctypes.c_void_p
        setlong.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
        shell32.DragQueryFileW.argtypes = [ctypes.c_void_p, wintypes.UINT, ctypes.c_wchar_p, wintypes.UINT]
        shell32.DragQueryFileW.restype = wintypes.UINT
        shell32.DragQueryPoint.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.POINT)]
        shell32.DragFinish.argtypes = [ctypes.c_void_p]
        user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        old = [None]

        def proc(h, msg, wp, lp):
            if msg != WM_DROPFILES:                       # every other message: straight through, no extra work
                return user32.CallWindowProcW(old[0], h, msg, wp, lp)
            try:
                if msg == WM_DROPFILES:
                    n = shell32.DragQueryFileW(wp, 0xFFFFFFFF, None, 0)
                    files = []
                    for i in range(n):
                        length = shell32.DragQueryFileW(wp, i, None, 0)
                        buf = ctypes.create_unicode_buffer(length + 1)
                        shell32.DragQueryFileW(wp, i, buf, length + 1)
                        files.append(buf.value)
                    pt = wintypes.POINT()
                    shell32.DragQueryPoint(wp, ctypes.byref(pt))
                    user32.ClientToScreen(h, ctypes.byref(pt))
                    shell32.DragFinish(wp)
                    widget.after(20, lambda f=files, x=pt.x, y=pt.y: callback(f, x, y))
                    return 0
            except Exception:
                pass
            return user32.CallWindowProcW(old[0], h, msg, wp, lp)
        cb = WNDPROC(proc)
        _keep["proc"] = cb
        old[0] = setlong(hwnd, GWL_WNDPROC, ctypes.cast(cb, ctypes.c_void_p))
        try:                                       # also allow drops when TDMS runs "as administrator"
            user32.ChangeWindowMessageFilterEx(hwnd, WM_DROPFILES, 1, None)
            user32.ChangeWindowMessageFilterEx(hwnd, WM_COPYGLOBALDATA, 1, None)
        except Exception:
            pass
        shell32.DragAcceptFiles(hwnd, True)
        return True
    except Exception:
        return False


def drag_files(widget, paths):
    """Start a real drag of files (copy).  Returns True when the drag ran."""
    if not available() or not paths:
        return False
    try:
        import ctypes
        from ctypes import wintypes
        ole32, shell32 = ctypes.windll.ole32, ctypes.windll.shell32

        class GUID(ctypes.Structure):
            _fields_ = [("a", ctypes.c_ulong), ("b", ctypes.c_ushort), ("c", ctypes.c_ushort), ("d", ctypes.c_ubyte * 8)]
        shell32.SHParseDisplayName.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), wintypes.ULONG, ctypes.POINTER(wintypes.ULONG)]
        shell32.SHParseDisplayName.restype = ctypes.c_long
        shell32.SHCreateDataObject.argtypes = [ctypes.c_void_p, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
        shell32.SHCreateDataObject.restype = ctypes.c_long
        shell32.SHDoDragDrop.argtypes = [wintypes.HWND, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        shell32.SHDoDragDrop.restype = ctypes.c_long
        shell32.ILFree.argtypes = [ctypes.c_void_p]
        ole32.CLSIDFromString.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(GUID)]
        ole32.OleInitialize(None)
        pidls = []
        for p in paths:
            pidl = ctypes.c_void_p()
            if shell32.SHParseDisplayName(str(Path(p)), None, ctypes.byref(pidl), 0, None) == 0 and pidl.value:
                pidls.append(pidl.value)
        if not pidls:
            return False
        try:
            arr = (ctypes.c_void_p * len(pidls))(*pidls)
            iid = GUID()
            ole32.CLSIDFromString("{0000010e-0000-0000-C000-000000000046}", ctypes.byref(iid))      # IID_IDataObject
            pdo = ctypes.c_void_p()
            if shell32.SHCreateDataObject(None, len(pidls), arr, None, ctypes.byref(iid), ctypes.byref(pdo)) != 0 or not pdo.value:
                return False
            effect = wintypes.DWORD(0)
            shell32.SHDoDragDrop(_top_hwnd(widget), pdo, None, 1, ctypes.byref(effect))              # 1 = DROPEFFECT_COPY
            try:                                                                                      # IUnknown::Release
                obj = ctypes.cast(pdo.value, ctypes.POINTER(ctypes.c_void_p))
                vtbl = ctypes.cast(obj[0], ctypes.POINTER(ctypes.c_void_p))
                ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])(pdo.value)
            except Exception:
                pass
            return True
        finally:
            for p in pidls:
                try:
                    shell32.ILFree(p)
                except Exception:
                    pass
    except Exception:
        return False


def set_titlebar(window, caption, text=None, dark=False):
    """Colour the window title bar like the app header (Windows 11; harmless elsewhere)."""
    if not available():
        return False
    try:
        import ctypes
        dwm = ctypes.windll.dwmapi
        dwm.DwmSetWindowAttribute.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
        hwnd = _top_hwnd(window)

        def bgr(h):
            h = h.lstrip("#")
            return (int(h[4:6], 16) << 16) | (int(h[2:4], 16) << 8) | int(h[0:2], 16)
        for attr, val in ((20, 1 if dark else 0), (35, bgr(caption)), (36, bgr(text) if text else None)):
            if val is not None:
                v = ctypes.c_int(val)
                dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))
        return True
    except Exception:
        return False
