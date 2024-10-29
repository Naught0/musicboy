import discord
from discord.ext import commands

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}!")


@bot.command()
async def join(ctx):
    channel = ctx.author.voice.channel
    await channel.connect()


@bot.command()
async def play(ctx, filename: str):
    if ctx.voice_client is None:
        await ctx.send("I'm not connected to a voice channel.")
        return

    ctx.voice_client.stop()  # Stop any currently playing audio
    ctx.voice_client.play(discord.FFmpegPCMAudio(filename))


@bot.command()
async def leave(ctx):
    if ctx.voice_client is not None:
        await ctx.voice_client.disconnect()


bot.run("YOUR_BOT_TOKEN")
