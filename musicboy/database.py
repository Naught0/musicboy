import sqlite3

from musicboy.playlist import PlaylistState
from musicboy.sources.youtube.youtube import SongMetadata


class NotFound(Exception):
    pass


class Database:
    def __init__(self, path: str = "musicboy/data/database.sqlite"):
        self.path = path
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row

    def initialize_db(self):
        cursor = self.connection.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS metadata (url TEXT PRIMARY KEY, id TEXT, title TEXT, duration INTEGER);"
            "CREATE TABLE IF NOT EXISTS state (guild_id INTEGER PRIMARY KEY, playlist TEXT, idx INTEGER, volume INTEGER);"
        )
        self.connection.commit()

    def get_state(self, guild_id: int) -> PlaylistState:
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM state WHERE guild_id = ?", (guild_id,))
        res = cursor.fetchone()
        if res is None:
            raise NotFound(f"Could not find state for {guild_id}")

        return PlaylistState(**res)

    def write_state(self, state: PlaylistState):
        cursor = self.connection.cursor()
        cursor.execute(
            "REPLACE INTO state(guild_id, playlist, idx, volume) VALUES (?, ?, ?, ?)",
            (
                state["guild_id"],
                state["playlist"],
                state["idx"],
                state["volume"],
            ),
        )
        self.connection.commit()

    def get_metadata(self, url: str) -> SongMetadata:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT id, url, title, duration FROM metadata WHERE url = ?", (url,)
        )
        res = cursor.fetchone()
        if res is None:
            raise NotFound(f"Could not find metadata for {url}")

        return SongMetadata(**res)

    def write_metadata(self, metadata: SongMetadata):
        cursor = self.connection.cursor()
        cursor.execute(
            "REPLACE INTO metadata(url, id, title, duration) VALUES (?, ?, ?, ?)",
            (
                metadata["url"],
                metadata["id"],
                metadata["title"],
                metadata["duration"],
            ),
        )
        self.connection.commit()
