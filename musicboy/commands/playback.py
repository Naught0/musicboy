import asyncio
from pathlib import Path

import discord
from asyncer import asyncify
from discord.ext import commands

from musicboy.context import Context
from musicboy.playlist import (
    PlaylistExhausted,
    cache_next_songs,
    cache_song,
    get_song_path,
)
from musicboy.progress import ProgressTracker, seconds_to_duration
from musicboy.threads import run_in_thread


def after_song_finished(ctx: Context, error=None):
    if ctx.voice_client is None or not ctx.voice_client.is_connected():
        return

    try:
        ctx.bot.playlist.next()
    except PlaylistExhausted:
        return

    asyncio.run(play_song(ctx))
    run_in_thread(lambda: cache_next_songs(ctx.bot.playlist))
    chan_ids = [c.channel.id for c in ctx.bot.voice_clients]

    for k in ctx.bot.progress:
        if k not in chan_ids:
            del ctx.bot.progress[k]


def get_song_source(song_id: str):
    return discord.FFmpegPCMAudio(str(get_song_path(song_id)))


async def play_song(ctx: Context):
    if ctx.voice_client is None or not ctx.voice_client.is_connected():
        return

    song = ctx.bot.playlist.current
    path = get_song_path(song["id"])
    if path is None:
        await asyncify(cache_song)(song, Path(ctx.bot.playlist.data_dir) / song["id"])
        path = get_song_path(song["id"])

    if path is None:
        raise ValueError("Can't play song. Audio not downloaded")

    if ctx.voice_client.is_playing():
        ctx.voice_client.source = get_song_source(song["id"])
    else:
        ctx.voice_client.play(
            discord.FFmpegPCMAudio(str(path)),
            after=lambda error: after_song_finished(ctx, error),
            bitrate=256,
            signal_type="music",
        )

    channel_id = ctx.voice_client.channel.id
    ctx.bot.progress[channel_id] = ProgressTracker.start()


class Playback(commands.Cog):
    @commands.command(name="play", aliases=["p", "prepend"])
    async def play(self, ctx: Context, url_or_urls: str | None):
        """Play, resume, or queue a song next"""
        if ctx.voice_client is not None:
            if ctx.voice_client.is_paused():
                return ctx.voice_client.resume()

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
            return await play_song(ctx)

        for url in url_or_urls.split():
            ctx.bot.playlist.prepend_song(url)

        if ctx.voice_client.is_playing():
            return

        cache_song(
            ctx.bot.playlist.current,
            Path(ctx.bot.playlist.data_dir) / ctx.bot.playlist.current["id"],
        )
        await play_song(ctx)

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
        """Skips to the next song in queue"""
        try:
            ctx.bot.playlist.next()
        except PlaylistExhausted:
            if ctx.voice_client:
                ctx.voice_client.stop()
                await ctx.voice_client.disconnect(force=True)

        if ctx.voice_client and ctx.voice_client.is_connected():
            await play_song(ctx)

        run_in_thread(lambda: cache_next_songs(ctx.bot.playlist))
        await ctx.message.add_reaction("✅")

    @commands.command(name="prev", aliases=["previous", "back"])
    async def previous(self, ctx: Context):
        """Skips to the previous song in queue"""
        ctx.bot.playlist.prev()

        if ctx.voice_client and ctx.voice_client.is_connected():
            await play_song(ctx)

        await ctx.message.add_reaction("✅")

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

    @commands.command(name="queue", aliases=["q", "list", "playlist"])
    async def playlist(self, ctx: Context):
        """Displays the playlist"""
        playlist = ctx.bot.playlist
        if len(playlist.playlist) == 0:
            return await ctx.message.add_reaction("❌")

        em = discord.Embed(color=discord.Color(0x000000))
        next_up = playlist.playlist[playlist.idx + 1 :]
        songs_remaining = len(next_up) + 1
        em.title = f"Playlist ({songs_remaining})"
        if next_up is not None:
            next_songs = []
            for idx, url in enumerate(next_up):
                song = playlist.metadata[url]
                duration = seconds_to_duration(song["duration"])
                next_songs.append(
                    f"**{idx+2}.** [{song['title']}]({song['url']}) ({duration})"
                )
            description = "\n".join(next_songs)
        else:
            description = "No more songs in the queue"
        description = f"**1.** [{playlist.current['title']}]({playlist.current['url']}) ({seconds_to_duration(playlist.current['duration'])}) {" (Now playing)" if ctx.voice_client and ctx.voice_client.is_playing() else ""}\n{description}"

        em.description = description

        await ctx.send(embed=em)

    @commands.command(name="np", aliases=["now", "playing"])
    async def now_playing(self, ctx: Context):
        """Displays the currently playing song"""
        if ctx.voice_client is None or not ctx.voice_client.is_playing():
            return

        current = ctx.bot.playlist.current
        em = discord.Embed(color=discord.Color(0x000000))
        em.title = current["title"]
        em.url = current["url"]
        progress = ctx.bot.progress[ctx.voice_client.channel.id]
        em.add_field(
            name="Progress",
            value=f"`{progress.elapsed} / {seconds_to_duration(current['duration'])} ({int(100 * progress.elapsed_seconds / current['duration'])}%)`",
        )

        if ctx.bot.playlist.next_song:
            em.add_field(
                name="Next up",
                value=f"[{ctx.bot.playlist.next_song['title']}]({ctx.bot.playlist.next_song['url']}) ({seconds_to_duration(ctx.bot.playlist.next_song['duration'])})",
                inline=False,
            )

        await ctx.send(embed=em)

    @commands.command(name="loop")
    async def loop(self, ctx: Context):
        """Toggle whether the playlist should loop after the final song"""
        ctx.bot.playlist.loop = not ctx.bot.playlist.loop
        await ctx.send(f"Looping {'on' if ctx.bot.playlist.loop else 'off'}")

    @commands.command(name="clear")
    async def clear(self, ctx: Context):
        """Removes all but the first song from the playlist"""
        ctx.bot.playlist.clear()
        await ctx.message.add_reaction("✅")

    @commands.command(name="rm", aliases=["remove", "del", "delete"])
    async def remove(self, ctx: Context, index_or_url: int | str):
        """Removes a song by position or url

        If you supply a URL, only the first instance of that song is removed"""
        if isinstance(index_or_url, int):
            ctx.bot.playlist.remove_index(index_or_url)
        elif isinstance(index_or_url, str):
            ctx.bot.playlist.remove_song(index_or_url)

        await ctx.message.add_reaction("✅")

    @commands.command(name="mv", aliases=["move"])
    async def move(self, ctx: Context, song_position: int, new_position: int):
        """Moves a song in the playlist"""
        if new_position < 2:
            new_position = 2
            await ctx.reply(
                "Position must be greater than 1. Playing song next (position 2)"
            )

        ctx.bot.playlist.move_song(song_position, new_position)
        await ctx.message.add_reaction("✅")


async def setup(bot):
    await bot.add_cog(Playback(bot))
