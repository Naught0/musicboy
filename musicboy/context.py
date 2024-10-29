from discord.ext import commands

from musicboy.bot import MusicBot


class Context(commands.Context):
    bot: MusicBot
