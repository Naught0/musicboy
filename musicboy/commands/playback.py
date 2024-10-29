from pathlib import Path
from typing import cast

import discord
from discord.ext import commands

from musicboy.context import Context
from musicboy.playlist import cache_next_songs, cache_song, get_song_path


def after_song_finished(ctx: Context, error=None):
    if len(ctx.bot.playlist.playlist) < 1:
        return

    cache_next_songs(ctx.bot.playlist)
    ctx.bot.playlist.next()
    play_song(ctx)


def play_song(ctx: Context):
    song = ctx.bot.playlist.current
    path = get_song_path(song)
    if path is None:
        raise ValueError(f"Could not find audio for song: {song['title']}")

    ctx.voice_client.play(
        discord.FFmpegPCMAudio(str(path)),
        after=lambda error: after_song_finished(ctx, error),
    )


class Playback(commands.Cog):
    @commands.command(name="play", aliases=["p", "prepend"])
    async def play(self, ctx: Context, url_or_urls: str | None):
        """Play a song now if one is not already playing. Otherwise, song plays next"""
        if url_or_urls is None:
            if len(ctx.bot.playlist.playlist) == 0:
                return await ctx.message.add_reaction("❌")

        if ctx.voice_client is None:
            try:
                await ctx.author.voice.channel.connect()
            except Exception:
                return await ctx.message.add_reaction("❌")

        if url_or_urls is None:
            return play_song(ctx)

        for url in url_or_urls.split():
            ctx.bot.playlist.prepend_song(url)

        if ctx.voice_client.is_playing():
            return

        cache_song(
            ctx.bot.playlist.current,
            Path(ctx.bot.playlist.data_dir) / ctx.bot.playlist.current["id"],
        )
        play_song(ctx)

    @commands.command(name="add", aliases=["append", "queue"])
    async def add_to_queue(self, ctx: Context, url: str):
        """Adds a song to the end of the queue"""
        ctx.bot.playlist.append_song(url)

    @commands.command(name="stop", aliases=["leave", "end", "quit"])
    async def stop(self, ctx: Context):
        """Stops playback and leaves the voice channel"""
        if ctx.voice_client is not None:
            await ctx.voice_client.disconnect(force=True)
            await ctx.message.add_reaction("✅")

    @commands.command(name="next", aliases=["skip"])
    async def next_song(self, ctx: Context):
        """Skips to the next song in the queue"""
        cast(discord.VoiceClient, ctx.voice_client).stop()

        ctx.bot.playlist.next()
        play_song(ctx)
        cache_next_songs(ctx.bot.playlist)
        await ctx.message.add_reaction("✅")

    @commands.command(name="previous", aliases=["prev", "back"])
    async def previous(self, ctx: Context):
        """Repeats the current song"""
        cast(discord.VoiceClient, ctx.voice_client).stop()

        ctx.bot.playlist.prev()
        play_song(ctx)
        await ctx.message.add_reaction("✅")

    @commands.command(name="shuffle")
    async def shuffle(self, ctx: Context):
        """Shuffles the playlist"""
        ctx.bot.playlist.shuffle()
        await ctx.message.add_reaction("✅")


async def setup(bot):
    await bot.add_cog(Playback(bot))
