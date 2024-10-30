from collections.abc import MutableMapping

from discord.ext import commands

from musicboy.playlist import Playlist, cache_next_songs
from musicboy.progress import ProgressTracker


class Context(commands.Context):
    bot: "MusicBoy"

    @property
    def progress(self) -> ProgressTracker | None:
        if not self.guild:
            return None

        return self.bot.progress.get(self.guild.id)

    @progress.setter
    def progress(self, progress: ProgressTracker):
        if not self.guild:
            return

        self.bot.progress[self.guild.id] = progress

    @property
    def playlist(self) -> Playlist | None:
        if not self.guild:
            return None

        pl = self.bot.playlists.get(self.guild.id)
        if pl is None:
            pl = Playlist(self.guild.id)
            self.bot.playlists[self.guild.id] = pl

        return pl


class MusicBoy(commands.Bot):
    enabled_extensions = ["playback"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.playlists: MutableMapping[int, Playlist] = {}
        self.progress: MutableMapping[int, ProgressTracker] = {}

    async def get_context(self, message, *, cls=Context):
        return await super().get_context(message, cls=cls)

    async def setup_hook(self) -> None:
        for cmd in self.enabled_extensions:
            await self.load_extension(f"musicboy.commands.{cmd}")

        for pl in self.playlists.values():
            cache_next_songs(pl)
