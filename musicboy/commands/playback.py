from pathlib import Path

import discord
from discord.ext import commands

from musicboy.context import Context
from musicboy.playlist import cache_next_songs, cache_song, get_song_path
from musicboy.threads import run_in_thread


def after_song_finished(ctx: Context, error=None):
    ctx.bot.playlist.next()
    play_song(ctx)
    run_in_thread(lambda: cache_next_songs(ctx.bot.playlist))


def get_song_source(song_id: str):
    return discord.FFmpegPCMAudio(str(get_song_path(song_id)))


def play_song(ctx: Context):
    song = ctx.bot.playlist.current
    path = get_song_path(song["id"])
    if path is None:
        raise ValueError(f"Could not find audio for song: {song['title']}")

    if ctx.voice_client.is_playing():
        ctx.voice_client.source = get_song_source(song["id"])
    else:
        ctx.voice_client.play(
            discord.FFmpegPCMAudio(str(path)),
            after=lambda error: after_song_finished(ctx, error),
            bitrate=256,
            signal_type="music",
        )


class Playback(commands.Cog):
    @commands.command(name="play", aliases=["p", "prepend"])
    async def play(self, ctx: Context, url_or_urls: str | None):
        """Play a song now if one is not already playing. Otherwise, song plays next"""
        if ctx.voice_client is not None:
            if ctx.voice_client.is_paused():
                ctx.guild.voice_client.resume()

        if url_or_urls is None:
            if len(ctx.bot.playlist.playlist) == 0:
                await ctx.message.add_reaction("❌")
                return

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

    @commands.command(name="add", aliases=["append"])
    async def add_to_queue(self, ctx: Context, url: str):
        """Adds a song to the end of the queue"""
        ctx.bot.playlist.append_song(url)

    @commands.command(name="stop", aliases=["leave", "end", "quit"])
    async def stop(self, ctx: Context):
        """Stops playback and leaves the voice channel"""
        if ctx.voice_client is not None:
            await ctx.voice_client.disconnect(force=True)

    @commands.command(name="next", aliases=["skip"])
    async def next_song(self, ctx: Context):
        """Skips to the next song in the queue"""
        ctx.bot.playlist.next()

        if ctx.voice_client.is_connected():
            play_song(ctx)

        run_in_thread(lambda: cache_next_songs(ctx.bot.playlist))
        await ctx.message.add_reaction("✅")

    @commands.command(name="previous", aliases=["prev", "back"])
    async def previous(self, ctx: Context):
        """Repeats the current song"""
        ctx.bot.playlist.prev()

        if ctx.voice_client.is_connected():
            play_song(ctx)

    @commands.command(name="pause")
    async def pause(self, ctx: Context):
        """Pauses playback"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()

    @commands.command(name="shuffle")
    async def shuffle(self, ctx: Context):
        """Shuffles the playlist"""
        ctx.bot.playlist.shuffle()
        await ctx.message.add_reaction("✅")

    @commands.command(name="playlist", aliases=["list", "queue", "q"])
    async def playlist(self, ctx: Context):
        """Displays the playlist"""
        playlist = ctx.bot.playlist
        if len(playlist.playlist) == 0:
            return await ctx.message.add_reaction("❌")

        next_up = playlist.playlist[playlist.idx + 1 :]
        if next_up:
            msg = "\n".join(f"{idx+2}. {ctx.bot.playlist.metadata.get(url, {}). get("title") or url}" for idx, url in enumerate(next_up))
        else:
            msg = "No more songs in the queue"
        msg = f"```1. {playlist.current['title']}{" (Now playing)" if ctx.voice_client and ctx.voice_client.is_playing() else ""}\n{msg}```"

        await ctx.send(msg)


async def setup(bot):
    await bot.add_cog(Playback(bot))
