from discord.ext import commands

from musicboy.bot import MusicBoy


class Context(commands.Context):
    bot: MusicBoy
