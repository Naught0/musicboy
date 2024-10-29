from pathlib import Path
from typing import cast

import discord
from discord.ext import commands

from musicboy.context import Context
from musicboy.playlist import Playlist
from musicboy.sources.youtube.youtube import SongMetadata, download_audio


def get_song_path(song: SongMetadata, base_dir: str = "musicboy/data") -> Path | None:
    try:
        path = next(Path(base_dir).glob(f"{song['id']}.*"))
    except StopIteration:
        return None

    return path


def cache_song(song: SongMetadata, path: Path):
    return download_audio(song["url"], str(path))


def cache_next_songs(playlist: Playlist):
    for url in playlist.playlist[:3]:
        if not get_song_path(meta := playlist.metadata[url]):
            cache_song(meta, Path(playlist.data_dir) / meta["id"])


def play_song(client: discord.VoiceClient, song: SongMetadata):
    path = get_song_path(song)
    if path is None:
        raise ValueError(f"Could not find audio for song: {song['title']}")

    client.play(discord.FFmpegPCMAudio(str(path)))


def after_song_finished(ctx: Context, error=None):
    cache_next_songs(ctx.bot.playlist)
    ctx.bot.playlist.next()
    play_song(cast(discord.VoiceClient, ctx.voice_client), ctx.bot.playlist.current)


class Playback(commands.Cog):
    @commands.command(name="play", aliases=["p", "prepend"])
    async def play(self, ctx: Context, url_or_urls: str):
        """Play a song now if one is not already playing. Otherwise, song plays next"""
        if ctx.voice_client is None:
            try:
                await ctx.author.voice.channel.connect()
            except Exception:
                return await ctx.message.add_reaction("❌")

        for url in url_or_urls.split():
            ctx.bot.playlist.prepend_song(url)

        if ctx.voice_client.is_playing():
            return

        cache_song(
            ctx.bot.playlist.current,
            Path(ctx.bot.playlist.data_dir) / ctx.bot.playlist.current["id"],
        )
        play_song(ctx.voice_client, ctx.bot.playlist.current)

    @commands.command(name="add", aliases=["append", "queue"])
    async def add_to_queue(self, ctx: Context, url: str):
        """Adds a song to the end of the queue"""
        ctx.bot.playlist.append_song(url)

    @commands.command(name="stop", aliases=["leave", "end", "quit"])
    async def stop(self, ctx: Context):
        """Stops playback and leaves the voice channel"""
        if ctx.voice_client is not None:
            await ctx.voice_client.disconnect(force=True)


async def setup(bot):
    await bot.add_cog(Playback(bot))
