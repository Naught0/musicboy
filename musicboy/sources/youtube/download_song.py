import os
import sys

from youtube import download_audio


def deprioritize_process():
    nice = os.nice(0)
    nice = os.nice(19 - nice)
    print("Set proc to new nice value:", nice)


def download_song(url: str, path: str):
    deprioritize_process()
    download_audio(url, path)


if __name__ == "__main__":
    download_audio(sys.argv[1], sys.argv[2])
