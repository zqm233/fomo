from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

# Load app config and models so autogenerate can see all tables
from config import get_settings
from db.database import Base
import db.models  # noqa: F401 – registers all ORM models with Base.metadata

settings = get_settings()

# Alembic Config object (gives access to alembic.ini values)
config = context.config

# Do not pass database_url through config.set_main_option(...): Postgres URLs commonly
# use %-encoding (e.g. in passwords), which triggers ConfigParser "invalid interpolation".
# Offline/online migrations read settings.database_url directly.

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection, emits SQL to stdout)."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live DB connection).

    When called from init_db(), a connection is pre-injected via
    config.attributes["connection"] to avoid creating a second engine
    (which can deadlock on startup due to connection-pool contention).
    """
    pre_existing = config.attributes.get("connection", None)
    if pre_existing is not None:
        context.configure(connection=pre_existing, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return

    connectable = create_engine(settings.database_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
