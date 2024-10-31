import asyncio
from pathlib import Path

import discord
from discord.ext import commands

from musicboy.bot import Context
from musicboy.database import Database
from musicboy.playlist import (
    PlaylistExhausted,
    cache_next_songs,
    cache_song_async,
    get_song_path,
)
from musicboy.progress import ProgressTracker, seconds_to_duration
from musicboy.sources.youtube.youtube import fetch_metadata_async


def after_song_finished(ctx: Context, error=None):
    if ctx.voice_client is None or not ctx.voice_client.is_connected():
        return

    playlist = ctx.playlist
    if playlist is None:
        return

    try:
        playlist.next()
    except PlaylistExhausted:
        return

    asyncio.create_task(play_song(ctx))

    asyncio.create_task(cache_next_songs(playlist, Database(ctx.db.path)))

    guild_ids = [v.guild.id for v in ctx.bot.voice_clients]

    for k in ctx.bot.progress:
        if k not in guild_ids:
            del ctx.bot.progress[k]


def get_song_source(song_id: str):
    return make_source(str(get_song_path(song_id)))


def make_source(path: str, volume: float = 0.05):
    return discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(path), volume=volume)


async def play_song(ctx: Context):
    if ctx.voice_client is None or not ctx.voice_client.is_connected():
        return

    playlist = ctx.playlist
    if playlist is None:
        return

    if ctx.guild is None:
        raise ValueError("Bot must be in a guild (not DM or group DM)")

    song = ctx.db.get_metadata(playlist.current)
    path = get_song_path(song["id"])
    if path is None:
        await cache_song_async(song, Path(playlist.data_dir) / song["id"])
        path = get_song_path(song["id"])

    if path is None:
        raise ValueError("Can't play song. Audio not downloaded")

    if ctx.voice_client.is_playing():
        ctx.voice_client.source = get_song_source(song["id"])
        ctx.voice_client.source.volume = ctx.playlist.volume
    else:
        ctx.voice_client.play(
            make_source(str(path), ctx.playlist.volume),
            after=lambda error: after_song_finished(ctx, error),
            bitrate=256,
            signal_type="music",
        )

    guild_id = ctx.guild.id
    progress = ProgressTracker()
    progress.start()
    ctx.bot.progress[guild_id] = progress
    ctx.update_last_active()


class Playback(commands.Cog):
    @commands.command(name="play", aliases=["p", "prepend"])
    async def play(self, ctx: Context, *, url_or_urls: str | None):
        """Play, resume, or queue a song next"""
        if ctx.voice_client is not None:
            if ctx.voice_client.is_paused():
                ctx.progress.start()
                return ctx.voice_client.resume()

        if ctx.playlist is None:
            return

        if url_or_urls is None:
            if len(ctx.playlist.playlist) == 0:
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
            url = url.split("&")[0]
            ctx.playlist.prepend_song(url)
            meta = await fetch_metadata_async(url_or_urls)
            await cache_song_async(
                meta,
                Path(ctx.playlist.data_dir) / meta["id"],
            )

        if ctx.voice_client.is_playing():
            return

        await play_song(ctx)

    @commands.command(name="add", aliases=["append"])
    async def add_to_queue(self, ctx: Context, *, urls: str):
        """Adds a song to the end of the queue"""
        if ctx.playlist is None:
            return

        for url in urls.split():
            url = url.split("&")[0]
            ctx.playlist.append_song(url)
            meta = await fetch_metadata_async(url)
            ctx.db.write_metadata(meta)

    @commands.command(name="stop", aliases=["leave", "end", "quit"])
    async def stop(self, ctx: Context):
        """Stops playback and leaves the voice channel"""
        if ctx.voice_client is not None:
            await ctx.voice_client.disconnect(force=True)

    @commands.command(name="next", aliases=["skip"])
    async def next_song(self, ctx: Context):
        """Skips to the next song in queue"""
        playlist = ctx.playlist
        if playlist is None:
            return

        try:
            playlist.next()
        except PlaylistExhausted:
            if ctx.voice_client:
                ctx.voice_client.stop()
                await ctx.voice_client.disconnect(force=True)

        if ctx.voice_client and ctx.voice_client.is_connected():
            await play_song(ctx)

        await cache_next_songs(playlist, ctx.db)

        await ctx.message.add_reaction("✅")

    @commands.command(name="prev", aliases=["previous", "back"])
    async def previous(self, ctx: Context):
        """Skips to the previous song in queue"""
        playlist = ctx.playlist
        if playlist is None:
            return

        playlist.prev()

        if ctx.voice_client and ctx.voice_client.is_connected():
            await play_song(ctx)

        await ctx.message.add_reaction("✅")

    @commands.command(name="pause")
    async def pause(self, ctx: Context):
        """Pauses playback"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.progress.stop()
            ctx.voice_client.pause()

    @commands.command(name="shuffle")
    async def shuffle(self, ctx: Context):
        """Shuffles the playlist"""
        if pl := ctx.playlist:
            pl.shuffle()

        await ctx.message.add_reaction("✅")

    @commands.command(name="queue", aliases=["q", "list", "playlist"])
    async def playlist(self, ctx: Context):
        """Displays the playlist"""
        playlist = ctx.playlist
        if playlist is None or len(playlist.playlist) == 0:
            return await ctx.message.add_reaction("❌")

        em = discord.Embed(color=discord.Color(0x000000))
        next_up = playlist.playlist[playlist.idx + 1 :]
        songs_remaining = len(next_up) + 1
        em.title = f"Playlist ({songs_remaining})"
        if next_up is not None:
            next_songs = []
            for idx, url in enumerate(next_up):
                song = ctx.db.get_metadata(url)
                duration = seconds_to_duration(song["duration"])
                next_songs.append(
                    f"**{idx+2}.** [{song['title']}]({song['url']}) ({duration})"
                )
            description = "\n".join(next_songs)
        else:
            description = "No more songs in the queue"

        meta = ctx.db.get_metadata(playlist.current)
        description = f"**1.** [{meta['title']}]({meta['url']}) ({seconds_to_duration(meta['duration'])}) {" (Now playing)" if ctx.voice_client and ctx.voice_client.is_playing() else ""}\n{description}"

        em.description = description

        await ctx.send(embed=em)

    @commands.command(name="np", aliases=["now", "playing"])
    async def now_playing(self, ctx: Context):
        """Displays the currently playing song"""
        if ctx.voice_client is None:
            return

        if (
            ctx.guild is None
            or (playlist := ctx.playlist) is None
            or ctx.progress is None
        ):
            return

        meta = ctx.db.get_metadata(playlist.current)
        em = discord.Embed(color=discord.Color(0x000000))
        em.title = f'{"⏸️" if ctx.voice_client.is_paused() else "▶️"} {meta["title"]}'
        em.url = meta["url"]
        progress = ctx.progress
        em.add_field(
            name="Progress",
            value=(
                f"{progress.elapsed} / {seconds_to_duration(meta['duration'])}"
                f" ({int(100 * progress.elapsed_seconds / meta['duration'])}%)"
            ),
        )

        up_next = "*Nothing*"
        if playlist.next_song:
            next_meta = ctx.db.get_metadata(playlist.next_song)
            up_next = (
                f"[{next_meta['title']}]({next_meta['url']})"
                f" ({seconds_to_duration(next_meta['duration'])})"
            )

        em.add_field(
            name="Up next",
            value=up_next,
            inline=False,
        )

        await ctx.send(embed=em)

    @commands.command(name="loop")
    async def loop(self, ctx: Context):
        """Toggle whether the playlist should loop after the final song"""
        if ctx.playlist is None:
            return

        ctx.playlist.loop = not ctx.playlist.loop
        await ctx.send(f"Looping {'on' if ctx.playlist.loop else 'off'}")

    @commands.command(name="clear")
    async def clear(self, ctx: Context):
        """Removes all but the first song from the playlist"""
        if ctx.playlist is None:
            return

        ctx.playlist.clear()
        await ctx.message.add_reaction("✅")

    @commands.command(name="rm", aliases=["remove", "del", "delete"])
    async def remove(self, ctx: Context, index_or_url: int | str):
        """Removes a song by position or url

        If you supply a URL, only the first instance of that song is removed"""
        if ctx.playlist is None:
            return

        if isinstance(index_or_url, int):
            ctx.playlist.remove_index(index_or_url)
        elif isinstance(index_or_url, str):
            ctx.playlist.remove_song(index_or_url)

        await ctx.message.add_reaction("✅")

    @commands.command(name="mv", aliases=["move"])
    async def move(self, ctx: Context, song_position: int, new_position: int):
        """Moves a song in the playlist"""
        if ctx.playlist is None:
            return

        if new_position < 2:
            new_position = 2
            await ctx.reply(
                "Position must be greater than 1. Playing song next (position 2)"
            )

        ctx.playlist.move_song(song_position, new_position)
        await ctx.message.add_reaction("✅")

    @commands.command(name="vol", aliases=["volume"])
    async def volume(self, ctx: Context, volume: int | None):
        """Changes the volume"""
        if ctx.playlist is None:
            return

        if volume is None:
            return await ctx.send(f"Volume: {ctx.playlist.volume * 100:.0f}")

        if volume < 0 or volume > 100:
            return await ctx.send("Volume must be between 0 and 100")

        vol = volume / 100

        ctx.playlist.volume = vol
        if ctx.voice_client and ctx.voice_client.source:
            ctx.voice_client.source.volume = vol

        await ctx.message.add_reaction("✅")


async def setup(bot):
    await bot.add_cog(Playback(bot))
