import os

from alembic import context
from sqlalchemy.engine import make_url

from app.db.models import Base
from app.db.session import create_db_engine

database_url = os.getenv("DATABASE_URL")
if not database_url or make_url(database_url).get_backend_name() != "postgresql":
    raise RuntimeError("Alembic requires a PostgreSQL DATABASE_URL")

if context.is_offline_mode():
    context.configure(
        dialect_name="postgresql",
        target_metadata=Base.metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_db_engine(database_url)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=Base.metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
