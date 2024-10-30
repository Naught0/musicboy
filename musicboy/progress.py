from time import time


def seconds_to_duration(seconds: int):
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"


class ProgressTracker:
    _duration = 0
    paused = False

    def start(self):
        self.paused = False
        self.start_time = int(time())

    def stop(self):
        self.stop_time = int(time())
        self._duration += self.stop_time - self.start_time
        self.paused = True

    @property
    def elapsed_seconds(self):
        if self.paused:
            return self._duration

        return int(time()) - self.start_time + self._duration

    @property
    def elapsed(self):
        if self.paused:
            return seconds_to_duration(self._duration)

        return seconds_to_duration(self.elapsed_seconds)
