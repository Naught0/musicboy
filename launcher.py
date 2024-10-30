import os
import sys

import discord
from dotenv import load_dotenv

from musicboy.bot import MusicBoy

load_dotenv()


def initialize_bot(bot_token: str):
    intents = discord.Intents.all()
    bot = MusicBoy(command_prefix="!!", intents=intents)
    bot.run(bot_token)


if __name__ == "__main__":
    initialize_bot(os.getenv("BOT_TOKEN") or sys.argv[1])
