# libs/config/config_reader.py

import os
import ast
import configparser
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

class ConfigReader:
    def __init__(self, ini_file='settings.ini', db_url=None, use_db=False, db_query=None):
        self.config = configparser.ConfigParser()
        self.config.read(ini_file)
        self.use_db = use_db
        self.db_url = db_url
        self.db_query = db_query or "SELECT value FROM settings WHERE name = :name"
        self.db_session = None

        if self.use_db and self.db_url:
            self._init_db()

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
        return os.getenv(name)

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