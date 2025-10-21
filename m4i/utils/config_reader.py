# libs/config/config_reader.py

import os
import ast
import configparser
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import warnings
from typing import Union

class ConfigReader:
    def __init__(self, settings:Union[str,dict,tuple,list]='settings.ini', db_url=None, use_db=False, db_query=None, table_name="settings"):
        self.config = configparser.ConfigParser()
        self.config_from_settings(settings)            
        self.use_db = use_db
        self.db_url = db_url
        self.table_name = table_name
        self.db_query = db_query or f"SELECT value FROM {self.table_name} WHERE name = :name"
        self.db_session = None

        if self.use_db and self.db_url:
            self._init_db()

    def config_from_settings(self, settings: Union[str,dict,tuple,list]):
        if isinstance(settings, str):
            if os.path.exists(settings):
                self.config.read(settings)
            else:
                warnings.warn(f"Configuration file '{settings}' not found.")
        elif isinstance(settings, dict):
            self.config.read_dict(settings)
        elif isinstance(settings, (list, tuple)):
            for item in settings:
                self.config_from_settings(item)
        else:
            raise ValueError("Invalid settings format. Must be a file path, dict, list or tuple.")
        
    def items(self):
        for sec in self.config.sections():
            for name, value in self.config.items(sec):
                yield sec, name, value

    def _init_db(self):
        try:
            engine = create_engine(self.db_url)
            Session = sessionmaker(bind=engine)
            self.db_session = Session()
        except SQLAlchemyError as ex:
            print(f"Error initializing database connection: {ex}")
    
    @staticmethod
    def check_db_connection(db_url):
        try:
            engine = create_engine(db_url)
            connection = engine.connect()
            connection.close()
            return True
        except SQLAlchemyError:
            return False
    
    @staticmethod
    def check_db_exists(db_url, table_name="settings"):
        try:
            engine = create_engine(db_url)
            inspector = inspect(engine)
            return inspector.has_table(table_name)
        except SQLAlchemyError:
            return False

    def _get_from_db(self, section, name):
        if not self.db_session:
            return None
        try:
            result = self.db_session.execute(self.db_query, {'name': name, "section": section}).fetchone()
            return result[0] if result else None
        except SQLAlchemyError as ex:
            print(f"Error fetching {name} from database: {ex}")
            return None

    def _get_from_ini(self, section, name):
        return self.config.get(section, name, fallback=None)

    def _get_from_env(self, name):
        return os.getenv("M4I_" + name)

    def get(self, name, section='DEFAULT', default=None):
        value_ini = self._get_from_ini(section, name)
        value_db=None
        value_env=None
        if self.use_db:
            value_db = self._get_from_db(section, name)
        value_env = self._get_from_env(name)
        
        value = (value_env or value_db) or value_ini
        return value.strip() if value is not None else default

    def getint(self, name, section='DEFAULT', default=None):
        value = self.get(name, section, default)
        return int(value) if value is not None else default

    def getboolean(self, name, section='DEFAULT', default=None):
        value = self.get(name, section, default)
        if isinstance(value, bool):
            return value
        return value.lower() in ('true', '1', 'yes') if value is not None else default
        

    def getfloat(self, name, section='DEFAULT', default=None):
        value = self.get(name, section, default)
        return float(value) if value is not None else default

    def getlist(self, name, section='DEFAULT', default=None):
        value = self.get(name, section, default)
        return ast.literal_eval(value) if value is not None else default

    def getset(self, name, section='DEFAULT', default=None):
        value = self.get(name, section, default)
        return set(ast.literal_eval(value)) if value is not None else default

    def gettuple(self, name, section='DEFAULT', default=None):
        value = self.get(name, section, default)
        return tuple(ast.literal_eval(value)) if value is not None else default

    def getdict(self, name, section='DEFAULT', default=None):
        value = self.get(name, section, default)
        return dict(ast.literal_eval(value)) if value is not None else default