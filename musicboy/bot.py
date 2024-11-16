import json
from collections.abc import MutableMapping, Sequence
from pathlib import Path
from time import time
from typing import cast

import discord
from discord.ext import commands, tasks
from discord.voice_client import VoiceClient

from musicboy.database import Database
from musicboy.metadata import find_missing_metadata
from musicboy.playlist import Playlist, PlaylistState, cache_next_songs
from musicboy.progress import ProgressTracker


class Context(commands.Context):
    bot: "MusicBoy"

    def update_last_active(self):
        if not self.guild:
            return

        self.bot.voice_activity[self.guild.id] = int(time())

    @property
    def db(self) -> Database:
        return self.bot.db

    @property
    def voice_client(self) -> VoiceClient | None:
        g = self.guild
        return cast(VoiceClient, g.voice_client) if g else None

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
            pl = Playlist(self.guild.id, self.db)
            self.bot.playlists[self.guild.id] = pl

        return pl


def get_music_channel(guild: discord.Guild) -> discord.TextChannel | None:
    music_channel = [
        c for c in guild.channels if c.name.lower() in ("music", "musicboy")
    ]
    if music_channel and isinstance(music_channel[0], discord.TextChannel):
        return music_channel[0]


class MusicBoy(commands.Bot):
    enabled_extensions = ["playback"]

    def __init__(
        self,
        *args,
        db: Database | None = None,
        max_idle_seconds: int = 60 * 15,
        data_dir="musicboy/data",
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.db = db or Database()
        self.playlists: MutableMapping[int, Playlist] = {}
        self.progress: MutableMapping[int, ProgressTracker] = {}
        self.voice_activity: MutableMapping[int, int] = {}
        self.max_idle_seconds = max_idle_seconds
        self.data_dir = Path(data_dir)

    @tasks.loop(seconds=60)
    async def prune_voice_clients(self):
        inactive_guilds = [c.guild for c in self.voice_clients if not c.is_playing()]
        for guild in inactive_guilds:
            if guild.voice_client is None:
                continue

            now = int(time())
            idle_time = now - self.voice_activity.get(guild.id, now)
            if idle_time >= self.max_idle_seconds:
                await guild.voice_client.disconnect(force=True)

                chan = get_music_channel(guild)
                if chan is not None:
                    await chan.send(
                        f"Inactive for {idle_time // 60} minutes. Leaving voice 👋",
                        delete_after=60,
                    )

                playlist = self.playlists.get(guild.id)
                if playlist is not None:
                    playlist.clear()

                self.progress.pop(guild.id)
                self.voice_activity.pop(guild.id)

    @property
    def voice_clients(self):  # type: ignore
        return cast(Sequence[VoiceClient], self._connection.voice_clients)

    async def get_context(self, message, *, cls=Context):  # type: ignore
        return await super().get_context(message, cls=cls)

    async def init_state_from_db(self):
        playlists = self.db.get_all_state()
        for state in playlists:
            self.playlists[state["guild_id"]] = Playlist.from_state(state, self.db)

    async def setup_hook(self) -> None:
        self.db.initialize_db()

        for cmd in self.enabled_extensions:
            await self.load_extension(f"musicboy.commands.{cmd}")

        await self.init_state_from_db()

        for pl in self.playlists.values():
            await find_missing_metadata(pl, self.db)
            await cache_next_songs(pl, self.db)

        self.prune_voice_clients.start()
