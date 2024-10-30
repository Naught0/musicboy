from time import time


def seconds_to_duration(seconds: int):
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"


class ProgressTracker:
    def __init__(self):
        self.start_time = int(time())

    @property
    def elapsed_seconds(self):
        return int(time()) - self.start_time

    @property
    def elapsed(self):
        return seconds_to_duration(self.elapsed_seconds)
