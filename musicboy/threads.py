import threading
from collections.abc import Callable


def run_in_thread(func: Callable):
    thread = threading.Thread(target=func)
    thread.start()
    return thread
