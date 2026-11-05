from alembic import context

from wowft.config import get_settings
from wowft.db import make_engine
from wowft.models import Base

target_metadata = Base.metadata


def run_migrations() -> None:
    url = context.config.attributes.get("url") or get_settings().database_url
    engine = make_engine(url)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite kann ALTER TABLE nur eingeschränkt
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations()
