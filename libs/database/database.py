from __future__ import annotations
import logging
import uuid
import time
import json
from sqlalchemy import create_engine, Column, String, Float, BigInteger, Index, ForeignKey, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from ..log import Logger
from ..status import Status

Base = declarative_base()
class Execution(Base):
    __tablename__ = 'executions'
    id = Column(BigInteger().with_variant(Integer,"sqlite"), primary_key=True, autoincrement=True)
    uuid = Column(String, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)    
    status = Column(String)
    start_time = Column(Float)
    end_time = Column(Float, nullable=True)
    params = Column(String)
    result = Column(String, nullable=True)
    progress = Column(Float, default=0.0)  # New column for progress

    __table_args__ = (
        Index('idx_start_time', 'start_time'),
        {'sqlite_autoincrement': True} 
    )

    def update_progress(self, progress: float):
        """Update the progress of the execution."""
        self.progress = progress

    def get_duration(self) -> float:
        """Get the duration of the execution."""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    @staticmethod
    def create_execution(params: dict=None, raise_exception = True) -> Execution:
        with DB.get_session() as session:
            try:
                new_execution = Execution(status=Status.SIM_PENDING, start_time=time.time(), params=json.dumps(params))
                session.add(new_execution)
                session.commit()
                session.refresh(new_execution)  # Refresh the object from the database
                return new_execution
            except SQLAlchemyError as ex:
                session.rollback()
                DB.log.error("Error creating execution: %s", ex)
                if raise_exception:
                    raise      

    def set_execution_success(execution, raise_exception = True) -> Execution:
        with DB.get_session() as session:
            try:
                if not isinstance(execution, Execution):
                    execution = session.query(Execution).filter_by(id=execution).first()
                    if not execution:
                        DB.log.error(f"Execution ID={execution} not found"), 404
                        raise SQLAlchemyError(f"Execution ID={execution} not found")
                execution.end_time = time.time()
                execution.status = Status.SIM_COMPLETED
                execution.result = "success"
                session.commit()
            except SQLAlchemyError as ex:
                session.rollback()
                DB.log.error("Error setting execution success: %s", ex)
                if raise_exception:
                    raise        

    def set_execution_failed(execution, ex=None, raise_exception = True) -> Execution:
        with DB.get_session() as session:
            try:
                if not isinstance(execution, Execution):
                    execution = session.query(Execution).filter_by(id=execution).first()
                    if not execution:
                        DB.log.error(f"Execution ID={execution} not found"), 404
                        raise SQLAlchemyError(f"Execution ID={execution} not found")
                execution.end_time = time.time()
                execution.status = Status.SIM_FAILED
                execution.result = str(ex)
                session.commit()
            except SQLAlchemyError as ex:
                session.rollback()
                DB.log.error("Error setting execution failed: %s", ex)
                if raise_exception:
                    raise        

class Log(Base):
    __tablename__ = 'logs'
    id = Column(BigInteger().with_variant(Integer,"sqlite"), primary_key=True, autoincrement=True)
    execution_id = Column(BigInteger)
    timestamp = Column(Float)
    level = Column(String)
    message = Column(String)
    __table_args__ = (
        Index('idx_execution_id', 'execution_id'),
         {'sqlite_autoincrement': True} 
    )

class DBHandler(logging.Handler):
    def __init__(self, session: Session):
        super().__init__()
        self.session = session

    def emit(self, record):
        log_entry = Log(
            execution_id = record.execution_id if hasattr(record, 'execution_id') else None,    
            timestamp=record.created,
            level=record.levelname,
            message=record.getMessage()
        )
        self.session.add(log_entry)
        self.session.commit()

class DB:
    
    _session: Session = None
    log = logging.getLogger("DB")

    @staticmethod
    def init_db(DATABASE_URL):
        """Initialize the database."""

        # Configure the database
        engine = create_engine(DATABASE_URL, echo=False)

        DB._session = sessionmaker(bind=engine)

        # Create the tables
        try:
            
            Base.metadata.create_all(engine)
            DB.log.info("Database initialized successfully.")
        except SQLAlchemyError as ex:
            DB.log.error("Error initializing database: %s", ex)
            raise

    @staticmethod
    def open_db(DATABASE_URL):
        """Initialize the database."""

        # Configure the database
        engine = create_engine(DATABASE_URL, echo=True)

        DB._session = sessionmaker(bind=engine)
        Logger.initLogger(session=DB.get_session())
        DB.log = Logger.getLogger("DB_INIT")
        
        DB.log.info("Database opened successfully.")

    @staticmethod
    def get_session() -> Session:
        """Return a session to the database."""
        return DB._session()


