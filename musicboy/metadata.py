import logging

from musicboy.database import Database, NotFound
from musicboy.playlist import Playlist
from musicboy.sources.youtube.youtube import fetch_metadata

logger = logging.getLogger(__name__)


async def find_missing_metadata(playlist: Playlist, db: Database):
    for url in set(playlist.playlist):
        try:
            db.get_metadata(url)
        except NotFound:
            logger.info(f"Finding metadata for {url}")
            meta = await fetch_metadata(url)
            db.write_metadata({**meta, "url": url})
