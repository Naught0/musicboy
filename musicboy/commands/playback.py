from discord.ext import commands

from musicboy.context import Context


class Playback(commands.Cog):
    @commands.command()
    async def play(self, ctx: Context, url: str):
        if ctx.voice_client is None:
            try:
                await ctx.author.voice.channel.connect()
            except Exception:
                return await ctx.message.add_reaction("❌")

        if ctx.guild.voice_client.is_playing():
            pass

        ctx.voice_client.stop()
        ctx.voice_client.play(discord.FFmpegPCMAudio())


    @commands.command()
    async def leave(self, ctx: Context):
        ctx.bot.playlist.next()
        if ctx.voice_client is not None:
            await ctx.voice_client.disconnect()
