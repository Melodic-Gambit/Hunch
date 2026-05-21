import os
import ctypes
import ctypes.wintypes
from typing import List


def clipboard_get_text() -> str:
    """
    Читает текст из буфера обмена Windows через Win32 API (CF_UNICODETEXT).
    Работает с текстом из любых приложений, в отличие от tkinter clipboard_get().
    Возвращает пустую строку если буфер недоступен или не содержит текст.
    """
    CF_UNICODETEXT = 13
    text = ""
    try:
        if not ctypes.windll.user32.OpenClipboard(0):
            return ""
        try:
            h = ctypes.windll.user32.GetClipboardData(CF_UNICODETEXT)
            if h:
                ptr = ctypes.windll.kernel32.GlobalLock(h)
                if ptr:
                    try:
                        text = ctypes.wstring_at(ptr)
                    finally:
                        ctypes.windll.kernel32.GlobalUnlock(h)
        finally:
            ctypes.windll.user32.CloseClipboard()
    except Exception:
        pass
    return text


def setup_paste_bindings(root_widget):
    """Рекурсивно привязывает Ctrl+V и Ctrl+C ко всем tk.Entry/tk.Text внутри root_widget."""
    import tkinter as tk

    def _make_paste(target):
        def _paste(event=None):
            text = clipboard_get_text()
            if not text:
                try:
                    text = target.winfo_toplevel().clipboard_get()
                except Exception:
                    pass
            if not text:
                return "break"
            try:
                target.delete("sel.first", "sel.last")
            except Exception:
                pass
            try:
                target.insert("insert", text)
            except Exception:
                pass
            return "break"
        return _paste

    def _make_copy(target):
        def _copy(event=None):
            try:
                target.event_generate("<<Copy>>")
            except Exception:
                pass
            return "break"
        return _copy

    def _walk(w):
        if isinstance(w, (tk.Entry, tk.Text)):
            paste_fn = _make_paste(w)
            copy_fn  = _make_copy(w)
            w.bind("<Control-v>", paste_fn)
            w.bind("<Control-V>", paste_fn)
            w.bind("<Control-c>", copy_fn)
            w.bind("<Control-C>", copy_fn)
            # Fallback для нелатинских раскладок (русская и др.):
            # при активной нелатинской раскладке keysym ≠ 'v'/'c', поэтому
            # <Control-v/c> не срабатывают. keycode 86 = VK_V, 67 = VK_C —
            # физические коды клавиш, не зависят от раскладки.
            def _layout_handler(event, _paste=paste_fn, _copy=copy_fn):
                if event.keycode == 86 and event.keysym.lower() not in ("v",):
                    return _paste(event)
                if event.keycode == 67 and event.keysym.lower() not in ("c",):
                    return _copy(event)
                return None
            w.bind("<Control-KeyPress>", _layout_handler)
        try:
            for child in w.winfo_children():
                _walk(child)
        except Exception:
            pass

    _walk(root_widget)


def load_sql_query(query_name: str, queries_dir: str = "queries") -> str:
    """Загружает SQL-запрос из файла"""
    query_path = os.path.join(queries_dir, f"{query_name}.sql")
    try:
        with open(query_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"Файл запроса {query_path} не найден")
    except IOError as e:
        raise IOError(f"Ошибка чтения файла {query_path}: {e}")

def save_sql_query(query_name: str, query: str, queries_dir: str = "queries"):
    """Сохраняет SQL-запрос в файл"""
    if not os.path.exists(queries_dir):
        os.makedirs(queries_dir)
    query_path = os.path.join(queries_dir, f"{query_name}.sql")
    with open(query_path, 'w', encoding='utf-8') as f:
        f.write(query)

def list_sql_queries(queries_dir: str = "queries") -> List[str]:
    """Возвращает список доступных SQL-запросов"""
    if not os.path.exists(queries_dir):
        return []
    queries = [f[:-4] for f in os.listdir(queries_dir) if f.endswith('.sql')]
    return sorted(queries)