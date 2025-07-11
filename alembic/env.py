from logging.config import fileConfig
import os
import sys
from sqlalchemy import engine_from_config, pool

from alembic import context

# Add the parent directory to sys.path to allow imports from the app package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import your models here
from app.db.base import Base
from app.db.types import GUID  # Import GUID type from types module

# Import ALL your models explicitly
from app.models.user import User  # noqa: F401
from app.models.group import Group  # noqa: F401
from app.models.channel import Channel  # noqa: F401
from app.models.invitation import Invitation  # noqa: F401
from app.models.message import Message  # noqa: F401
from app.models.phone_verification import PhoneVerification  # noqa: F401

# This tells the linter these imports are intentional
__all__ = [
    "User", "Group", "Channel", "Invitation", "Message", "PhoneVerification"
]

from app.config import settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override the SQLAlchemy URL with the one from settings
# Remove async driver for alembic (it doesn't support async)
database_url = settings.DATABASE_URL
if "+asyncpg" in database_url:
    database_url = database_url.replace("+asyncpg", "")
elif "+aiosqlite" in database_url:
    database_url = database_url.replace("+aiosqlite", "")

config.set_main_option("sqlalchemy.url", database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()