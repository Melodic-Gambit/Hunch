import os


def create_directories():
    for directory in ("config", "queries", "logs"):
        os.makedirs(directory, exist_ok=True)
