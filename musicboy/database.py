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
        stmts = [
            "CREATE TABLE IF NOT EXISTS metadata (id INTEGER PRIMARY KEY, url TEXT UNIQUE NOT NULL, video_id TEXT NOT NULL, title TEXT NOT NULL, duration INTEGER NOT NULL);",
            "CREATE TABLE IF NOT EXISTS state (guild_id INTEGER PRIMARY KEY, idx INTEGER, volume INTEGER);",
            "CREATE TABLE IF NOT EXISTS playlist (id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL, url TEXT NOT NULL, idx INTEGER);",
        ]

        for stmt in stmts:
            cursor.execute(stmt)

        self.connection.commit()

    def get_all_state(self):
        cursor = self.connection.cursor()
        cursor.execute("SELECT guild_id, idx, volume FROM state;")
        states = cursor.fetchall()
        cursor.execute("SELECT guild_id, url, idx FROM playlist ORDER BY idx ASC;")
        songs = cursor.fetchall()
        return (
            PlaylistState(
                **state,
                playlist=[
                    song["url"]
                    for song in songs
                    if song["guild_id"] == state["guild_id"]
                ],
            )
            for state in states
        )

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
            "REPLACE INTO state(guild_id, idx, volume) VALUES (?, ?, ?)",
            (state["guild_id"], state["idx"], state["volume"]),
        )
        self.connection.commit()

    def write_playlist(self, guild_id: int, playlist: list[str]):
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM playlist WHERE guild_id = ?;", (guild_id,))
        self.connection.commit()
        cursor.executemany(
            "INSERT INTO playlist(guild_id, url, idx) VALUES (?, ?, ?);",
            [(guild_id, url, idx) for idx, url in enumerate(playlist)],
        )
        self.connection.commit()

    def get_playlist(self, guild_id: int) -> list[str]:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT url FROM playlist WHERE guild_id = ? ORDER BY idx ASC", (guild_id,)
        )
        return [row[0] for row in cursor.fetchall()]

    def get_metadata(self, url: str) -> SongMetadata:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT video_id, url, title, duration FROM metadata WHERE url = ?", (url,)
        )
        res = cursor.fetchone()
        if res is None:
            raise NotFound(f"Could not find metadata for {url}")

        return SongMetadata(**res)

    def write_metadata(self, metadata: SongMetadata):
        cursor = self.connection.cursor()
        cursor.execute(
            "REPLACE INTO metadata(url, video_id, title, duration) VALUES (?, ?, ?, ?)",
            (
                metadata["url"],
                metadata["video_id"],
                metadata["title"],
                metadata["duration"],
            ),
        )
        self.connection.commit()
