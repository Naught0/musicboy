import os
import sys

import discord

from musicboy.bot import MusicBot
from musicboy.playlist import Playlist


def initialize_bot(bot_token: str):
    with open("musicboy/data/playlist.txt") as f:
        playlist = f.read().splitlines()

    intents = discord.Intents.default()
    playlist = Playlist()
    bot = MusicBot(command_prefix="!!", intents=intents, playlist=playlist)

    bot.run(bot_token)


if __name__ == "__main__":
    initialize_bot(os.getenv("BOT_TOKEN", sys.argv[1]))
