import logging
import os
import time

_TMP_MAX_AGE_SECONDS = 30


def create_directories(base: str = ""):
    for sub in ("config", "queries", "logs"):
        path = os.path.join(base, sub) if base else sub
        os.makedirs(path, exist_ok=True)
    _cleanup_stale_tmp(base)


def _cleanup_stale_tmp(base: str):
    check_dirs = [base or "."] + [
        os.path.join(base, sub) if base else sub
        for sub in ("config", "queries", "logs")
    ]
    cutoff = time.time() - _TMP_MAX_AGE_SECONDS
    for d in check_dirs:
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            if not name.endswith(".tmp"):
                continue
            path = os.path.join(d, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
            except OSError as e:
                logging.warning("Не удалось удалить %s: %s", path, e)
