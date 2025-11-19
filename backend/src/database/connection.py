"""
Database connection management.

This module handles:
- PostgreSQL connection pool initialization using SQLAlchemy and asyncpg
- Connection lifecycle management (creation, health checks, cleanup)
- Transaction management and session handling
- Connection retry logic with exponential backoff
- Database migration support using Alembic
- Connection pooling configuration for optimal performance

The connection manager ensures reliable database access across all application
components with proper error handling and resource cleanup.
"""

import os
import time
import asyncpg
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event, pool
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


class DatabaseConnection:
    """
    Database connection manager with pooling and retry logic.

    Handles PostgreSQL connections using SQLAlchemy with:
    - Connection pooling (QueuePool)
    - Automatic retry on connection failure
    - Connection health checks
    - Graceful shutdown
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,
        echo: bool = False,
    ):
        """
        Initialize database connection manager.

        Args:
            database_url: PostgreSQL connection URL (or from env var DATABASE_URL)
            pool_size: Number of connections to maintain in the pool
            max_overflow: Maximum number of connections that can be created beyond pool_size
            pool_timeout: Seconds to wait before giving up on getting a connection
            pool_recycle: Seconds after which a connection is recycled
            echo: Whether to log all SQL statements (for debugging)
        """
        self.database_url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/moderator_db"
        )
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle
        self.echo = echo

        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None

    def _create_engine(self) -> Engine:
        """
        Create SQLAlchemy engine with connection pooling.

        Returns:
            SQLAlchemy Engine instance
        """
        engine = create_engine(
            self.database_url,
            poolclass=pool.QueuePool,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_timeout=self.pool_timeout,
            pool_recycle=self.pool_recycle,
            pool_pre_ping=True,  # Enable connection health checks
            echo=self.echo,
        )

        # Add event listeners for connection lifecycle
        @event.listens_for(engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            """Handle new connections."""
            # Set connection parameters
            cursor = dbapi_conn.cursor()
            cursor.execute("SET timezone='UTC'")
            cursor.close()

        @event.listens_for(engine, "checkout")
        def receive_checkout(dbapi_conn, connection_record, connection_proxy):
            """Handle connection checkout from pool."""
            pass  # Add custom checkout logic if needed

        return engine

    def connect(self, max_retries: int = 3, retry_delay: float = 1.0) -> bool:
        """
        Establish database connection with retry logic.

        Args:
            max_retries: Maximum number of connection attempts
            retry_delay: Initial delay between retries (doubles with each attempt)

        Returns:
            True if connection successful, False otherwise
        """
        for attempt in range(max_retries):
            try:
                self._engine = self._create_engine()

                # Test connection
                with self._engine.connect() as conn:
                    conn.execute("SELECT 1")

                # Create session factory
                self._session_factory = sessionmaker(
                    bind=self._engine,
                    autocommit=False,
                    autoflush=False,
                    expire_on_commit=False,
                )

                return True

            except OperationalError as e:
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)
                    time.sleep(delay)
                else:
                    raise ConnectionError(
                        f"Failed to connect to database after {max_retries} attempts: {e}"
                    )

        return False

    def disconnect(self):
        """
        Close all database connections and cleanup resources.
        """
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None

    def create_all_tables(self):
        """
        Create all database tables defined in models.

        Note: For production, use Alembic migrations instead.
        """
        if not self._engine:
            raise RuntimeError("Database not connected. Call connect() first.")

        Base.metadata.create_all(bind=self._engine)

    def drop_all_tables(self):
        """
        Drop all database tables.

        WARNING: This will delete all data! Use with caution.
        """
        if not self._engine:
            raise RuntimeError("Database not connected. Call connect() first.")

        Base.metadata.drop_all(bind=self._engine)

    def get_session(self) -> Session:
        """
        Get a new database session.

        Returns:
            SQLAlchemy Session instance

        Raises:
            RuntimeError: If database is not connected
        """
        if not self._session_factory:
            raise RuntimeError("Database not connected. Call connect() first.")

        return self._session_factory()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """
        Provide a transactional scope for database operations.

        Usage:
            with db.session_scope() as session:
                user = session.query(User).first()
                session.commit()

        Yields:
            SQLAlchemy Session instance

        The session is automatically committed if no exception occurs,
        and rolled back if an exception is raised.
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def health_check(self) -> bool:
        """
        Check database connection health.

        Returns:
            True if database is accessible, False otherwise
        """
        try:
            if not self._engine:
                return False

            with self._engine.connect() as conn:
                conn.execute("SELECT 1")

            return True
        except Exception:
            return False

    @property
    def engine(self) -> Engine:
        """
        Get SQLAlchemy engine instance.

        Returns:
            SQLAlchemy Engine

        Raises:
            RuntimeError: If database is not connected
        """
        if not self._engine:
            raise RuntimeError("Database not connected. Call connect() first.")

        return self._engine


# Global database connection instance
_db_connection: Optional[DatabaseConnection] = None


def init_db(
    database_url: Optional[str] = None,
    pool_size: int = 5,
    max_overflow: int = 10,
    echo: bool = False,
) -> DatabaseConnection:
    """
    Initialize global database connection.

    Args:
        database_url: PostgreSQL connection URL
        pool_size: Number of connections in pool
        max_overflow: Maximum overflow connections
        echo: Whether to echo SQL statements

    Returns:
        DatabaseConnection instance
    """
    global _db_connection

    _db_connection = DatabaseConnection(
        database_url=database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        echo=echo,
    )
    _db_connection.connect()

    return _db_connection


def get_db() -> DatabaseConnection:
    """
    Get global database connection instance.

    Returns:
        DatabaseConnection instance

    Raises:
        RuntimeError: If database has not been initialized
    """
    if not _db_connection:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    return _db_connection


def get_session() -> Session:
    """
    Get a new database session from the global connection.

    Returns:
        SQLAlchemy Session instance

    Raises:
        RuntimeError: If database has not been initialized
    """
    return get_db().get_session()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Provide a transactional scope using the global database connection.

    Usage:
        from database.connection import session_scope

        with session_scope() as session:
            user = session.query(User).filter_by(id=1).first()
            user.username = "new_name"
            # Automatically committed on exit

    Yields:
        SQLAlchemy Session instance
    """
    db = get_db()
    with db.session_scope() as session:
        yield session


def close_db():
    """
    Close global database connection and cleanup resources.
    """
    global _db_connection

    if _db_connection:
        _db_connection.disconnect()
        _db_connection = None


# ============================================================================
# Asyncpg connection pool for async operations
# ============================================================================

_asyncpg_pool: Optional[asyncpg.Pool] = None


async def init_asyncpg_pool(
    database_url: Optional[str] = None,
    min_size: int = 5,
    max_size: int = 15,
    command_timeout: int = 60
) -> asyncpg.Pool:
    """
    Initialize global asyncpg connection pool.

    Args:
        database_url: PostgreSQL connection URL
        min_size: Minimum number of connections in pool
        max_size: Maximum number of connections in pool
        command_timeout: Command timeout in seconds

    Returns:
        asyncpg.Pool instance
    """
    global _asyncpg_pool

    if not database_url:
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/moderator_db"
        )

    _asyncpg_pool = await asyncpg.create_pool(
        database_url,
        min_size=min_size,
        max_size=max_size,
        command_timeout=command_timeout
    )

    return _asyncpg_pool


def get_asyncpg_pool() -> asyncpg.Pool:
    """
    Get global asyncpg connection pool.

    Returns:
        asyncpg.Pool instance

    Raises:
        RuntimeError: If pool has not been initialized
    """
    if not _asyncpg_pool:
        raise RuntimeError("Asyncpg pool not initialized. Call init_asyncpg_pool() first.")

    return _asyncpg_pool


async def close_asyncpg_pool():
    """
    Close global asyncpg connection pool and cleanup resources.
    """
    global _asyncpg_pool

    if _asyncpg_pool:
        await _asyncpg_pool.close()
        _asyncpg_pool = None


async def check_database_health() -> bool:
    """
    Check if database connection is healthy.

    Returns:
        True if database is accessible, False otherwise
    """
    try:
        pool = get_asyncpg_pool()
        if not pool:
            return False

        async with pool.acquire() as conn:
            await conn.fetchval('SELECT 1')
        return True
    except Exception as e:
        from utils.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"Database health check failed: {e}")
        return False
