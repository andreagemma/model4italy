from __future__ import annotations

import logging
import uuid
import time
import json
import threading
import datetime
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Float,
    BigInteger,
    Index,
    Integer,
    Engine,
    DateTime,
)

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, scoped_session, registry
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy import event, text

import warnings
from ..log import Logger
from ..server.status import Status
import warnings

try:
    mapper_registry = registry()
    Base = mapper_registry.generate_base()
    _LOCK = threading.Lock()
except:
    warnings.warn("SQLAlchemy is required for database operations. Please install it using 'pip install SQLAlchemy'.")


class Token(Base):
    __tablename__ = "tokens"
    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    token = Column(String, unique=True, nullable=False)
    user = Column(String, nullable=True)
    created_at = Column(DateTime(True), default=lambda: datetime.datetime.now(datetime.timezone.utc))
    expires_at = Column(DateTime(True), nullable=True)

    __table_args__ = (Index("idx_token", "token"), {"sqlite_autoincrement": True})

    def __init__(
        self,
        id: int = None,
        token: str = None,
        user: str = None,
        created_at: datetime.datetime = None,
        expires_at: datetime.datetime = None,
    ):
        self.id = id
        self.token = token
        self.user = user
        self.created_at = created_at if created_at else datetime.datetime.now(datetime.timezone.utc)
        self.expires_at = expires_at

    def is_valid(self) -> bool:
        """Check if the token is valid based on its expiration date."""
        if self.expires_at:
            return datetime.datetime.now(datetime.timezone.utc) < self.expires_at
        return True

    @staticmethod
    def create_token(user: str, expires_at: datetime.datetime = None) -> Token:
        """Create a new token if it does not already exist for the user."""
        try:
            with DB.get_engine().connect() as conn:
                # Check if a token already exists for the user
                result = conn.execute(Token.__table__.select().where(Token.user == user))
                row = result.fetchone()
                if row:
                    existing_token = Token(id=row["id"], token=row["token"], expires_at=row["expires_at"])
                    if existing_token.is_valid():
                        return existing_token

                # Create a new token if none exists or the existing one is invalid
                new_token = Token(token=str(uuid.uuid4()), user=user, expires_at=expires_at)
                result = conn.execute(
                    Token.__table__.insert().values(
                        token=new_token.token,
                        user=new_token.user,
                        expires_at=new_token.expires_at,
                    )
                )
                new_token.id = result.inserted_primary_key[0]
                return new_token
        except SQLAlchemyError as ex:
            DB.log.error("Error creating or retrieving token: %s", ex)
            raise

    @staticmethod
    def get_token(user: str) -> Token:
        """Retrieve a token for the user if it exists and is valid."""
        try:
            with DB.get_engine().connect() as conn:
                result = conn.execute(Token.__table__.select().where(Token.user == user))
                row = result.fetchone()
                if row:
                    token = Token(
                        id=row["id"],
                        token=row["token"],
                        user=row["user"],
                        expires_at=row["expires_at"],
                    )
                    if token.is_valid():
                        return token
            return None
        except SQLAlchemyError as ex:
            DB.log.error("Error retrieving token: %s", ex)
            raise

    def refresh(self):
        """Refresh the token's expiration date."""
        if self.expires_at and self.expires_at > datetime.datetime.now(datetime.timezone.utc):
            self.expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)
            try:
                with DB.get_engine().connect() as conn:
                    conn.execute(Token.__table__.update().where(Token.id == self.id).values(expires_at=self.expires_at))
            except SQLAlchemyError as ex:
                DB.log.error("Error refreshing token: %s", ex)
                raise


class Execution(Base):
    __tablename__ = "executions"
    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    uuid = Column(String, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    status = Column(String)
    start_time = Column(DateTime(True))
    end_time = Column(DateTime(True), nullable=True)
    params = Column(String)
    result = Column(String, nullable=True)
    progress = Column(Float, default=0.0)
    last_message = Column(String, nullable=True)
    last_message_time = Column(DateTime(True), nullable=True)

    __table_args__ = (
        Index("idx_start_time", "start_time"),
        {"sqlite_autoincrement": True},
    )

    def update_progress(self, progress: float):
        self.progress = progress

    def get_duration(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.datetime.now() - self.start_time).total_seconds()

    @staticmethod
    def create_execution(params: dict = None, raise_exception=True) -> dict:
        try:
            with DB.get_engine().connect() as conn:
                now = datetime.datetime.fromtimestamp(time.time(), tz=datetime.timezone.utc)
                uid = str(uuid.uuid4())
                result = conn.execute(
                    text("""
                        INSERT INTO executions (uuid, status, start_time, params, progress)
                        VALUES (:uuid, :status, :start_time, :params, :progress)
                        RETURNING id
                    """),
                    {
                        "uuid": uid,
                        "status": Status.SIM_PENDING,
                        "start_time": now,
                        "params": json.dumps(params),
                        "progress": 0.0,
                    },
                )
                exec_id = result.scalar()
                conn.commit()
                ret = Execution(
                    id=exec_id,
                    uuid=uid,
                    status=Status.SIM_PENDING,
                    start_time=now,
                    params=params,
                )
                return ret
        except Exception as ex:
            DB.log.error("Error creating execution: %s", ex)
            if raise_exception:
                raise

    @staticmethod
    def set_execution_success(execution_id: int, raise_exception=True):
        Execution._set_status(execution_id, Status.SIM_COMPLETED, "success", raise_exception)

    @staticmethod
    def set_execution_failed(execution_id: int, ex=None, raise_exception=True):
        Execution._set_status(execution_id, Status.SIM_FAILED, str(ex), raise_exception)

    @staticmethod
    def _set_status(execution_id: int, status: str, result_value: str, raise_exception=True):
        try:
            with _LOCK:
                with DB.get_engine().connect() as conn:
                    conn.execute(
                        text("""
                            UPDATE executions
                            SET end_time = :end_time,
                                status = :status,
                                result = :result
                            WHERE id = :id
                        """),
                        {
                            "end_time": datetime.datetime.fromtimestamp(time.time(), tz=datetime.timezone.utc),
                            "status": status,
                            "result": result_value,
                            "id": execution_id,
                        },
                    )
                    conn.commit()
        except Exception as ex:
            DB.log.error("Error updating execution status: %s", ex)
            if raise_exception:
                raise

    @staticmethod
    def set_progress(execution_id: int, progress: float, message: str = None, raise_exception=True):
        try:
            with _LOCK:
                with DB.get_engine().connect() as conn:
                    conn.execute(
                        text("""
                            UPDATE executions
                            SET progress = :progress,
                             last_message = :last_message,
                             last_message_time = :last_message_time
                            WHERE id = :id
                        """),
                        {
                            "progress": progress,
                            "id": execution_id,
                            "last_message": message,
                            "last_message_time": datetime.datetime.fromtimestamp(time.time(), tz=datetime.timezone.utc),
                        },
                    )
                    conn.commit()
        except Exception as ex:
            DB.log.error("Error updating execution status: %s", ex)
            if raise_exception:
                raise


class Log(Base):
    __tablename__ = "logs"
    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    log_level = Column(Integer)
    log_levelname = Column(String(7))
    log = Column(String)
    created_at = Column(DateTime(True))
    created_by = Column(String)
    execution_id = Column(BigInteger().with_variant(Integer, "sqlite"))

    __table_args__ = (
        Index("idx_execution_id", "execution_id"),
        {"sqlite_autoincrement": True},
    )


class DBHandler(logging.Handler):
    def __init__(self, engine: Engine):
        super().__init__()
        self.engine = engine

    def emit(self, record):
        try:
            with self.engine.connect() as conn:
                # datetime.datetime.now().astimezone()
                conn.execute(
                    text("""
                        INSERT INTO logs (log_level, log_levelname, log, created_at, created_by, execution_id)
                        VALUES (:log_level, :log_levelname, :log, :created_at, :created_by, :execution_id)
                    """),
                    {
                        "execution_id": getattr(record, "execution_id", None),
                        "created_at": datetime.datetime.fromtimestamp(record.created, tz=datetime.timezone.utc),
                        "log_level": record.levelno,
                        "log_levelname": record.levelname,
                        "created_by": record.name,
                        "log": record.getMessage(),
                    },
                )
                conn.commit()
        except Exception as e:
            logging.getLogger("DBHandler").error("Failed to log to DB: %s", e)


class DB:
    _engine: Engine = None
    _session_factory = None
    log = logging.getLogger("DB")

    @staticmethod
    def init_db(DATABASE_URL: str):
        connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
        DB._engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True, connect_args=connect_args)
        if DATABASE_URL.startswith("sqlite"):

            @event.listens_for(DB._engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=DELETE;")
                cursor.close()

        DB._session_factory = scoped_session(sessionmaker(bind=DB._engine, autoflush=True))
        try:
            Base.metadata.create_all(DB._engine)
            DB.log.info("Database initialized successfully.")
        except SQLAlchemyError as ex:
            DB.log.error("Error initializing database: %s", ex)
            raise

    @staticmethod
    def open_db(DATABASE_URL: str):
        connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
        DB._engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True, connect_args=connect_args)
        # Abilita WAL per SQLite
        if DATABASE_URL.startswith("sqlite"):

            @event.listens_for(DB._engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=DELETE;")
                cursor.close()

        DB._session_factory = scoped_session(sessionmaker(bind=DB._engine))
        DB.log = Logger.getLogger("DB")
        DB.log.info("Database opened successfully.")

    @staticmethod
    def get_engine() -> Engine:
        return DB._engine
