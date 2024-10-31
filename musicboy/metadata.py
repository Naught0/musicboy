from musicboy.database import Database
from musicboy.playlist import Playlist
from musicboy.sources.youtube.youtube import fetch_metadata


async def find_missing_metadata(playlist: Playlist, db: Database):
    for url in set(playlist.playlist):
        try:
            db.get_metadata(url)
        except ValueError:
            print("Finding metadata for", url)
            meta = await fetch_metadata(url)
            db.write_metadata(meta)
