from __future__ import annotations
import logging
import uuid
import time
import json
import threading
import datetime
from sqlalchemy import (
    create_engine, Column, String, Float, BigInteger, Index, Integer, Engine, DateTime
)

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy import event, text

from ..log import Logger
from ..status import Status

Base = declarative_base()
_LOCK = threading.Lock()

 

class Execution(Base):
    __tablename__ = 'executions'
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
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
        Index('idx_start_time', 'start_time'),
        {'sqlite_autoincrement': True}
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
                now = datetime.datetime.fromtimestamp(time.time(),tz=datetime.timezone.utc)
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
                        "progress": 0.0
                    }
                )
                exec_id = result.scalar()
                conn.commit()
                ret = Execution(id=exec_id, uuid=uid, status=Status.SIM_PENDING, start_time=now, params=params)
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
                            "end_time": datetime.datetime.fromtimestamp(time.time(),tz=datetime.timezone.utc),
                            "status": status,
                            "result": result_value,
                            "id": execution_id
                        }
                    )
                    conn.commit()
        except Exception as ex:
            DB.log.error("Error updating execution status: %s", ex)
            if raise_exception:
                raise
    @staticmethod
    def set_progress(execution_id: int, progress: float, message:str=None, raise_exception=True):
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
                            "last_message_time": datetime.datetime.fromtimestamp(time.time(),tz=datetime.timezone.utc)
                        }
                    )
                    conn.commit()
        except Exception as ex:
            DB.log.error("Error updating execution status: %s", ex)
            if raise_exception:
                raise            

class Log(Base):
    __tablename__ = 'logs'
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    log_level = Column(Integer)
    log_levelname = Column(String(7))
    log = Column(String)
    created_at = Column(DateTime(True))
    created_by = Column(String)
    execution_id = Column(BigInteger().with_variant(Integer, "sqlite"))

    __table_args__ = (
        Index('idx_execution_id', 'execution_id'),
        {'sqlite_autoincrement': True}
    )

class DBHandler(logging.Handler):
    def __init__(self, engine: Engine):
        super().__init__()
        self.engine = engine

    def emit(self, record):
        try:
            with self.engine.connect() as conn:
                #datetime.datetime.now().astimezone()
                conn.execute(
                    text("""
                        INSERT INTO logs (log_level, log_levelname, log, created_at, created_by, execution_id)
                        VALUES (:log_level, :log_levelname, :log, :created_at, :created_by, :execution_id)
                    """),
                    {
                        "execution_id": getattr(record, 'execution_id', None),
                        "created_at": datetime.datetime.fromtimestamp(record.created, tz=datetime.timezone.utc),
                        "log_level": record.levelno,
                        "log_levelname": record.levelname,
                        "created_by": record.name,
                        "log": record.getMessage()
                    }
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
        connect_args = {'check_same_thread': False} if 'sqlite' in DATABASE_URL else {}
        DB._engine = create_engine(
            DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            connect_args=connect_args
        )
        # ➕ Abilita WAL per SQLite
        if DATABASE_URL.startswith("sqlite"):
            @event.listens_for(DB._engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.close()     

        DB._session_factory = scoped_session(sessionmaker(bind=DB._engine))
        try:
            Base.metadata.create_all(DB._engine)
            DB.log.info("Database initialized successfully.")
        except SQLAlchemyError as ex:
            DB.log.error("Error initializing database: %s", ex)
            raise

    @staticmethod
    def open_db(DATABASE_URL: str):
        connect_args = {'check_same_thread': False} if 'sqlite' in DATABASE_URL else {}
        DB._engine = create_engine(
            DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            connect_args=connect_args
        )
        # ➕ Abilita WAL per SQLite
        if DATABASE_URL.startswith("sqlite"):
            @event.listens_for(DB._engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.close()             
        DB._session_factory = scoped_session(sessionmaker(bind=DB._engine))
        DB.log = Logger.getLogger("DB_INIT")
        DB.log.info("Database opened successfully.")

    @staticmethod
    def get_engine() -> Engine:
        return DB._engine

