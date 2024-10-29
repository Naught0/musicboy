from discord.ext import commands

from musicboy.playlist import Playlist


class MusicBot(commands.Bot):
    def __init__(self, *args, playlist: Playlist, **kwargs):
        super().__init__(*args, **kwargs)
        self.playlist = playlist

