# indica se viene usato il DB per caricare o solvare i dati
# Usare False in caso di Debug
from libs.utils import ConfigReader, generate_sqlalchemy_url
import logging

class IniClass:

    def __init__(self, ini_file='settings.ini'):
        # Inizializza il lettore di configurazione
        config_reader = ConfigReader(
            ini_file=ini_file,
            db_url=None,
            use_db=False,
            db_query="SELECT value FROM settings WHERE name = :name"
        )

        self.USE_LOG = config_reader.getboolean("USE_LOG", 'LOGGING', True)
        self.DIR_LOG = config_reader.get("DIR_LOG", 'LOGGING', True)

        self.DB_SETTINGS_USE = config_reader.getboolean("DB_SETTINGS_USE","DATABASE_SETTINGS", False)
        if self.DB_SETTINGS_USE:
            self.DB_SETTINGS_TYPE = config_reader.get("DB_SETTINGS_TYPE", 'DATABASE_SETTINGS', 'sqlite')
            self.DB_SETTINGS_DRIVER = config_reader.get("DB_SETTINGS_DRIVER", 'DATABASE_SETTINGS', 'sqlite')
            self.DB_SETTINGS_USER = config_reader.get("DB_SETTINGS_USER", 'DATABASE_SETTINGS', '')
            self.DB_SETTINGS_PASS = config_reader.get("DB_SETTINGS_PASS", 'DATABASE_SETTINGS', '')
            self.DB_SETTINGS_HOST = config_reader.get("DB_SETTINGS_HOST", 'DATABASE_SETTINGS', '')
            self.DB_SETTINGS_PORT = config_reader.get("DB_SETTINGS_PORT", 'DATABASE_SETTINGS', '')
            self.DB_SETTINGS_NAME = config_reader.get("DB_SETTINGS_NAME", 'DATABASE_SETTINGS', 'settings.db')
            self.DB_SETTINGS_URI = config_reader.get("DB_SETTINGS_URI", 'DATABASE_SETTINGS', '')

            # Stringhe di connessione
            if self.DB_SETTINGS_URI == "":
                self.DB_SETTINGS_URI = generate_sqlalchemy_url(
                    db_type=self.DB_SETTINGS_TYPE,
                    db_driver=self.DB_SETTINGS_DRIVER,
                    db_user=self.DB_SETTINGS_USER,
                    db_password=self.DB_SETTINGS_PASS,
                    db_host = self.DB_SETTINGS_HOST,
                    db_port=self.DB_SETTINGS_PORT,
                    db_name=self.DB_SETTINGS_NAME
                )
                            
            config_reader = ConfigReader(
                ini_file='settings.ini',
                db_url=self.DB_SETTINGS_URI,
                use_db=self.DB_SETTINGS_USE,
                db_query="SELECT value FROM settings WHERE name = :name"
            )

        # GENERAL
        self.SRC_COEFS = config_reader.get("SRC_COEFS", 'GENERAL', r'coefficients.json')
        self.SRC_CONV_TBL = config_reader.get("SRC_CONV_TBL", 'GENERAL', None)
        self.NUMCPU = config_reader.getint("NUMCPU", 'GENERAL', 1)
        self.PARALLEL_ENGINE = config_reader.get("PARALLEL_ENGINE", 'GENERAL', "ray")
        self.DEBUG = config_reader.getboolean("DEBUG", 'GENERAL', False)


        # SIMULATOR
        self.SIMU_STEP = config_reader.getfloat("SIMU_STEP", 'SIMULATOR', 6)  # step di simulazione
        self.CAR_LENGTH = config_reader.getfloat("CAR_LENGTH", 'SIMULATOR', 5)  # lunghezza veicolo in metri
        self.MIN_SPEED = config_reader.getfloat("MIN_SPEED", 'SIMULATOR', 4)  # velocità minima per la coda
        self.AGG_INT = config_reader.getfloat("AGG_INT", 'SIMULATOR', 0.1)  # intervallo di aggregazione per i risultati
        self.LT1 = config_reader.getfloat("LT1", 'SIMULATOR', 0)  # perditempo 1 alla partenza del veicolo
        self.LT2 = config_reader.getfloat("LT2", 'SIMULATOR', 0)  # perditempo 2 alla partenza del veicolo

        # ASSIGNMENT
        self.CLASS_EQ_FACT = config_reader.getdict("CLASS_EQ_FACT", 'ASSIGNMENT', {'c': 1, 'h': 2})
        self.MSA_MAX_ITE = config_reader.getint("MSA_MAX_ITE", 'ASSIGNMENT', 1)
        self.MSA_RGAP = config_reader.getfloat("MSA_RGAP", 'ASSIGNMENT', 0.01)
        self.MSA_K = config_reader.getint("MSA_K", 'ASSIGNMENT', 3)
        self.MSA_MAX_TIMESLICE = config_reader.getint("MSA_MAX_TIMESLICE", 'ASSIGNMENT', int(3 * 60))
        self.DELTA_T = config_reader.getint("DELTA_T", 'ASSIGNMENT', 15)
        self.MSA_PRELOAD = config_reader.getint("MSA_PRELOAD", 'ASSIGNMENT', 60)
        self.MSA_POSTLOAD = config_reader.getint("MSA_POSTLOAD", 'ASSIGNMENT', 60)
        self.SAVE_GRAPH = config_reader.getboolean("SAVE_GRAPH", 'ASSIGNMENT', False)
        self.LOAD_GRAPH = config_reader.getboolean("LOAD_GRAPH", 'ASSIGNMENT', False)
        self.SAVE_PATHS = config_reader.getboolean("SAVE_PATHS", 'ASSIGNMENT', False)
        self.LOAD_PATHS = config_reader.getboolean("LOAD_PATHS", 'ASSIGNMENT', False)

        # OD ESTIMATION
        self.OD_ESTIMATION_PRELOAD = config_reader.getint("OD_ESTIMATION_PRELOAD", 'OD_ESTIMATION', 60)
        self.OD_ESTIMATION_MAX_ITE = config_reader.getint("OD_ESTIMATION_MAX_ITE", 'OD_ESTIMATION', 2)
        self.OD_ESTIMATION_RGAP = config_reader.getfloat("OD_ESTIMATION_RGAP", 'OD_ESTIMATION', 0.01)
        self.OD_ESTIMATION_MSA_MAX_ITE = config_reader.getint("OD_ESTIMATION_MSA_MAX_ITE", 'OD_ESTIMATION', 3)
        self.OD_ESTIMATION_MSA_K = config_reader.getint("OD_ESTIMATION_MSA_K", 'OD_ESTIMATION', 3)
        self.OD_ESTIMATION_MSA_RGAP = config_reader.getfloat("OD_ESTIMATION_MSA_RGAP", 'OD_ESTIMATION', 0.001)
        self.OD_ESTIMATION_MSA_TIMESLICE = config_reader.getint("OD_ESTIMATION_MSA_TIMESLICE", 'OD_ESTIMATION', 60)
        
        # OUPTUT
        self.OUTPUT_AGG_INT = config_reader.getfloat("OUTPUT_AGG_INT", 'OUTPUT', 15)

        # FLASK
        self.FLASK_HOST = config_reader.get("FLASK_HOST", 'FLASK', '0.0.0.0')
        self.FLASK_PORT = config_reader.getint("FLASK_PORT", 'FLASK', 5000)
        self.FLASK_DEBUG = config_reader.getboolean("FLASK_DEBUG", 'FLASK', True)

        # INTERNAL DATABASE
        self.DATABASE_URL = config_reader.get("DATABASE_URL", 'DATABASE', 'sqlite:///executions.db')

        for section, name, value in config_reader.items():
            if not hasattr(self, name.upper()):
                setattr(self, name.upper(), value)

        if self.USE_LOG:
            logging.info("File %s caricato", __file__)