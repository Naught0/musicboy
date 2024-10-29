from discord.ext import commands

from musicboy.playlist import Playlist


class MusicBot(commands.Bot):
    enabled_extensions = ["playback"]

    def __init__(self, *args, playlist: Playlist, **kwargs):
        super().__init__(*args, **kwargs)
        self.playlist = playlist

    async def setup_hook(self) -> None:
        for cmd in self.enabled_extensions:
            await self.load_extension(f"musicboy.commands.{cmd}")
