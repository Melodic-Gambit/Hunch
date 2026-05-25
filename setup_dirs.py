import os


def create_directories(base: str = ""):
    for sub in ("config", "queries", "logs"):
        path = os.path.join(base, sub) if base else sub
        os.makedirs(path, exist_ok=True)
