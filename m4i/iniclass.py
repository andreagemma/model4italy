# indica se viene usato il DB per caricare o solvare i dati
# Usare False in caso di Debug
from .utils import ConfigReader, generate_sqlalchemy_url
import logging, os

class IniClass:
    def get_dict(self):
        from copy import deepcopy
        tmp = deepcopy(self.__dict__)
        tmp.pop('config_reader', None)  # Rimuove il lettore di configurazione
        return tmp
    
    def __init__(self, ini_file='settings.ini', db_url=None, use_db=False, reload=True):
        # Inizializza il lettore di configurazione
        self.config_reader = ConfigReader(
            ini_file=ini_file,
            db_url=db_url,
            use_db=use_db,
            db_query="SELECT value FROM settings WHERE name = :name"
        )
        self.DB_SETTINGS_USE = self.config_reader.getboolean("DB_SETTINGS_USE","DATABASE_SETTINGS", False)
        self.DB_SETTINGS_TYPE = self.config_reader.get("DB_SETTINGS_TYPE", 'DATABASE_SETTINGS', 'sqlite')
        self.DB_SETTINGS_DRIVER = self.config_reader.get("DB_SETTINGS_DRIVER", 'DATABASE_SETTINGS', 'sqlite')
        self.DB_SETTINGS_USER = self.config_reader.get("DB_SETTINGS_USER", 'DATABASE_SETTINGS', '')
        self.DB_SETTINGS_PASS = self.config_reader.get("DB_SETTINGS_PASS", 'DATABASE_SETTINGS', '')
        self.DB_SETTINGS_HOST = self.config_reader.get("DB_SETTINGS_HOST", 'DATABASE_SETTINGS', '')
        self.DB_SETTINGS_PORT = self.config_reader.get("DB_SETTINGS_PORT", 'DATABASE_SETTINGS', '')
        self.DB_SETTINGS_NAME = self.config_reader.get("DB_SETTINGS_NAME", 'DATABASE_SETTINGS', 'settings.db')
        self.DB_SETTINGS_URL = self.config_reader.get("DB_SETTINGS_URL", 'DATABASE_SETTINGS', '')
        if self.DB_SETTINGS_USE:
            # Stringhe di connessione
            if self.DB_SETTINGS_URL == "":
                self.DB_SETTINGS_URL = generate_sqlalchemy_url(
                    db_type=self.DB_SETTINGS_TYPE,
                    db_driver=self.DB_SETTINGS_DRIVER,
                    db_user=self.DB_SETTINGS_USER,
                    db_password=self.DB_SETTINGS_PASS,
                    db_host = self.DB_SETTINGS_HOST,
                    db_port=self.DB_SETTINGS_PORT,
                    db_name=self.DB_SETTINGS_NAME
                )                   
            self.config_reader = ConfigReader(
                ini_file='settings.ini',
                db_url=self.DB_SETTINGS_URL,
                use_db=self.DB_SETTINGS_USE,
                db_query="SELECT value FROM settings WHERE name = :name"
            )
        

        self.load_parameters()
        if self.LOG_USE:
            logging.info("File %s caricato", os.path.abspath(ini_file))

    def load_parameters(self):

        self.LOG_NAME = self.config_reader.get("LOG_NAME", 'LOGGING', "M4I")
        self.LOG_USE = self.config_reader.getboolean("LOG_USE", 'LOGGING', True)
        self.LOG_DIR = self.config_reader.get("LOG_DIR", 'LOGGING', "log")
        self.LOG_ON_DATABASE = self.config_reader.getboolean("LOG_ON_DATABASE", 'LOGGING', False)
        self.LOG_ON_CONSOLE = self.config_reader.getboolean("LOG_ON_CONSOLE", 'LOGGING', True)
        self.LOG_ON_FILE = self.config_reader.getboolean("LOG_ON_FILE", 'LOGGING', False)
        self.LOG_LEVEL = self.config_reader.get("LOG_LEVEL", 'LOGGING', "DEBUG")
        self.LOG_EXECUTION_FORMAT = self.config_reader.get("LOG_EXECUTION_FORMAT", 'LOGGING', "%(execution_id)s - %(asctime)s | %(last_elapsed).2f/%(elapsed).2fs | %(levelname)s | %(name)s | %(message)s")
        self.LOG_FORMAT = self.config_reader.get("LOG_FORMAT", 'LOGGING', "%(asctime)s | %(levelname)s | %(name)s | %(message)s")

        # GENERAL
        self.SRC_COEFS = self.config_reader.get("SRC_COEFS", 'GENERAL', None)
        if not self.SRC_COEFS:
            self.SRC_COEFS = os.path.join(os.path.dirname(__file__),"coefficients.json")
        self.SRC_CONV_TBL = self.config_reader.get("SRC_CONV_TBL", 'GENERAL', None)
        self.DEBUG = self.config_reader.getboolean("DEBUG", 'GENERAL', False)
        self.CRS = self.config_reader.get("CRS", 'GENERAL', "EPSG:4326")  # Coordinate Reference System
        self.CRS_CALC = self.config_reader.get("CRS_CALC", 'GENERAL', "EPSG:6875")  # Coordinate Reference System for calculation
        self.TZ_LOCAL = self.config_reader.get("TZ_LOCAL", 'GENERAL', "Europe/Rome")  # Timezone locale


        # SIMULATOR
        self.SIMU_STEP = self.config_reader.getfloat("SIMU_STEP", 'SIMULATOR', 6)  # step di simulazione
        self.CAR_LENGTH = self.config_reader.getfloat("CAR_LENGTH", 'SIMULATOR', 5)  # lunghezza veicolo in metri
        self.MIN_SPEED = self.config_reader.getfloat("MIN_SPEED", 'SIMULATOR', 4)  # velocità minima per la coda
        self.AGG_INT = self.config_reader.getfloat("AGG_INT", 'SIMULATOR', 0.1)  # intervallo di aggregazione per i risultati
        self.LT1 = self.config_reader.getfloat("LT1", 'SIMULATOR', 0)  # perditempo 1 alla partenza del veicolo
        self.LT2 = self.config_reader.getfloat("LT2", 'SIMULATOR', 0)  # perditempo 2 alla partenza del veicolo

        # ASSIGNMENT
        self.CLASS_EQ_FACT = self.config_reader.getdict("CLASS_EQ_FACT", 'ASSIGNMENT', {'c': 1, 'h': 2})
        self.MSA_MAX_ITE = self.config_reader.getint("MSA_MAX_ITE", 'ASSIGNMENT', 6)
        self.MSA_RGAP = self.config_reader.getfloat("MSA_RGAP", 'ASSIGNMENT', 0.01)
        self.MSA_K = self.config_reader.getint("MSA_K", 'ASSIGNMENT', 3)
        self.MSA_MAX_TIMESLICE = self.config_reader.getint("MSA_MAX_TIMESLICE", 'ASSIGNMENT', int(3 * 60))
        self.MSA_SPP_NUMCPUS = self.config_reader.getint("MSA_SPP_NUMCPUS", 'ASSIGNMENT', 0)
        self.MSA_K_BALANCING = self.config_reader.getint("MSA_K_BALANCING", 'ASSIGNMENT', -1)
        self.DELTA_T = self.config_reader.getint("DELTA_T", 'ASSIGNMENT', 15)
        self.MSA_PRELOAD = self.config_reader.getint("MSA_PRELOAD", 'ASSIGNMENT', 60)
        self.MSA_POSTLOAD = self.config_reader.getint("MSA_POSTLOAD", 'ASSIGNMENT', 60)
        self.SAVE_GRAPH = self.config_reader.getboolean("SAVE_GRAPH", 'ASSIGNMENT', False)
        self.LOAD_GRAPH = self.config_reader.getboolean("LOAD_GRAPH", 'ASSIGNMENT', False)
        self.SAVE_PATHS = self.config_reader.getboolean("SAVE_PATHS", 'ASSIGNMENT', False)
        self.LOAD_PATHS = self.config_reader.getboolean("LOAD_PATHS", 'ASSIGNMENT', False)

        # OD ESTIMATION
        self.OD_ESTIMATION_PRELOAD = self.config_reader.getint("OD_ESTIMATION_PRELOAD", 'OD_ESTIMATION', 60)
        self.OD_ESTIMATION_MAX_ITE = self.config_reader.getint("OD_ESTIMATION_MAX_ITE", 'OD_ESTIMATION', 2)
        self.OD_ESTIMATION_RGAP = self.config_reader.getfloat("OD_ESTIMATION_RGAP", 'OD_ESTIMATION', 0.01)
        self.OD_ESTIMATION_MSA_MAX_ITE = self.config_reader.getint("OD_ESTIMATION_MSA_MAX_ITE", 'OD_ESTIMATION', 6)
        self.OD_ESTIMATION_MSA_K = self.config_reader.getint("OD_ESTIMATION_MSA_K", 'OD_ESTIMATION', 3)
        self.OD_ESTIMATION_MSA_RGAP = self.config_reader.getfloat("OD_ESTIMATION_MSA_RGAP", 'OD_ESTIMATION', 0.01)
        self.OD_ESTIMATION_MSA_TIMESLICE = self.config_reader.getint("OD_ESTIMATION_MSA_TIMESLICE", 'OD_ESTIMATION', 60)
        
        self.OD_ESTIMATION_GAMMA1 = self.config_reader.getfloat("OD_ESTIMATION_GAMMA1", 'OD_ESTIMATION', 0)
        self.OD_ESTIMATION_GAMMA2 = self.config_reader.getfloat("OD_ESTIMATION_GAMMA2", 'OD_ESTIMATION', 1)
        self.OD_ESTIMATION_GAMMA3 = self.config_reader.getfloat("OD_ESTIMATION_GAMMA3", 'OD_ESTIMATION', 1)
        self.OD_ESTIMATION_ITESA = self.config_reader.getint("OD_ESTIMATION_ITESA", 'OD_ESTIMATION', 100)
        self.OD_ESTIMATION_LAMBDA_LB = self.config_reader.getfloat("OD_ESTIMATION_LAMBDA_LB", 'OD_ESTIMATION', 0)  # Estremo inferiore della ricerca monodimensionale
        self.OD_ESTIMATION_LAMBDA_UB = self.config_reader.getfloat("OD_ESTIMATION_LAMBDA_UB", 'OD_ESTIMATION', 0.05)  # Estremo superiore
        self.OD_ESTIMATION_EPS = self.config_reader.getfloat("OD_ESTIMATION_EPS", 'OD_ESTIMATION', 0.000001)  # Soglia di arresto dell'ottimizzazione monodimensionale
        self.OD_ESTIMATION_EPS2 = self.config_reader.getfloat("OD_ESTIMATION_EPS2", 'OD_ESTIMATION', 10)  # Soglia di arresto dell'ottimizzazione monodimensionale
        self.OD_ESTIMATION_SA = self.config_reader.getfloat("OD_ESTIMATION_SA", 'OD_ESTIMATION', 0.362)  # segmento minore della sezione aurea
        
        # FCD_SERVER
        self.FCD_SERVER_FCD_HORIZON = self.config_reader.getint("FCD_SERVER_FCD_HORIZON", 'FCD_SERVER', 60) # orario di previsione in minuti
        self.FCD_SERVER_FCD_TIMESLICE = self.config_reader.getint("FCD_SERVER_FCD_TIMESLICE", 'FCD_SERVER', 15) # numero massimo di iterazioni per la previsione
        self.FCD_SERVER_FCD_TIMESLICE_OFFLINE = self.config_reader.getint("FCD_SERVER_FCD_TIMESLICE_OFFLINE", 'FCD_SERVER', 120) # numero di iterazioni per la previsione offline
        self.FCD_SERVER_FCD_CRS_DATA = self.config_reader.get("FCD_SERVER_FCD_CRS_DATA", 'FCD_SERVER', "EPSG:4326") # CRS dei dati FCD
        self.FCD_SERVER_FCD_CRS_CALC = self.config_reader.get("FCD_SERVER_FCD_CRS_CALC", 'FCD_SERVER', "EPSG:6875") # CRS dei dati FCD
        self.FCD_SERVER_SHARE_DATA = self.config_reader.getboolean("FCD_SERVER_SHARE_DATA", 'FCD_SERVER', True) # esporta i dati FCD su IPC
        self.FCD_SERVER_WRITE_OUTPUT = self.config_reader.getboolean("FCD_SERVER_WRITE_OUTPUT", 'FCD_SERVER', False) # esporta i dati FCD su DB
        self.FCD_SERVER_MAP_MATCHING = self.config_reader.getboolean("FCD_SERVER_MAP_MATCHING", 'FCD_SERVER', True) # abilita il map matching
        self.FCD_SERVER_ROUTING = self.config_reader.getboolean("FCD_SERVER_ROUTING", 'FCD_SERVER', True) # abilita il routing
        self.FCD_SERVER_TRIPS = self.config_reader.getboolean("FCD_SERVER_TRIPS", 'FCD_SERVER', True) # abilita la generazione dei viaggi
        self.FCD_SERVER_TZ_DATA = self.config_reader.get("FCD_SERVER_TZ_DATA", 'FCD_SERVER', "UTC") # Timezone dei dati FCD

        self.FCD_MAP_MATCHING_CPUS = self.config_reader.getint("FCD_MAP_MATCHING_CPUS", 'FCD_MAP_MATCHING', 1) # numero di processi per il map matching
        self.FCD_MAP_MATCHING_MAX_DISTANCE = self.config_reader.getfloat("FCD_MAP_MATCHING_MAX_DISTANCE", 'FCD_MAP_MATCHING', 50) # distanza massima per il map matching in metri
        self.FCD_MAP_MATCHING_MAX_ANGLE = self.config_reader.getfloat("FCD_MAP_MATCHING_MAX_ANGLE", 'FCD_MAP_MATCHING', 45) # angolo massimo per il map matching in gradi

        self.FCD_ROUTING_CPUS = self.config_reader.getint("FCD_ROUTING_CPUS", 'FCD_ROUTING', 1)
        self.FCD_ROUTING_START_FROM_ZONE = self.config_reader.getboolean("FCD_ROUTING_START_FROM_ZONE", 'FCD_ROUTING', False) # se True il path inizia dalla zona di partenza
        self.FCD_ROUTING_END_TO_ZONE = self.config_reader.getboolean("FCD_ROUTING_END_TO_ZONE", 'FCD_ROUTING', False) # se True il path termina nella zona di arrivo
        self.FCD_ROUTING_AGGRATION_INTERVAL = self.config_reader.getint("FCD_ROUTING_AGGRATION_INTERVAL", 'FCD_ROUTING', 15) # intervallo di aggregazione in secondi
         
        self.FCD_TRIPS_CPUS = self.config_reader.getint("FCD_TRIPS_CPUS", 'FCD_TRIPS', 1)  # numero di processi per la generazione dei viaggi
        self.FCD_TRIPS_SIGNAL_BREAK_MAX_DT = self.config_reader.getint("FCD_TRIPS_SIGNAL_BREAK_MAX_DT", 'FCD_TRIPS', 900)  # max time for signal break in seconds
        self.FCD_TRIPS_SIGNAL_BREAK_DT = self.config_reader.getint("FCD_TRIPS_SIGNAL_BREAK_DT", 'FCD_TRIPS', 300)  # time for signal break in seconds
        self.FCD_TRIPS_SIGNAL_BREAK_V = self.config_reader.getfloat("FCD_TRIPS_SIGNAL_BREAK_V", 'FCD_TRIPS', 0.5555555555555556)  # speed for signal break in m/s
        self.FCD_TRIPS_STOP_O_DS = self.config_reader.getfloat("FCD_TRIPS_STOP_O_DS", 'FCD_TRIPS', 50)  # distance for stop at origin in meters
        self.FCD_TRIPS_STOP_D_DS = self.config_reader.getfloat("FCD_TRIPS_STOP_D_DS", 'FCD_TRIPS', 50)  # distance for stop at destination in meters
        self.FCD_TRIPS_SIGNAL_CONT_DT = self.config_reader.getint("FCD_TRIPS_SIGNAL_CONT_DT", 'FCD_TRIPS', 600)  # time for signal continuation in seconds
        self.FCD_TRIPS_SIGNAL_CONT_V = self.config_reader.getfloat("FCD_TRIPS_SIGNAL_CONT_V", 'FCD_TRIPS', 0.1388888888888889)  # speed for signal continuation in m/s
        self.FCD_TRIPS_MAX_V3 = self.config_reader.getfloat("FCD_TRIPS_MAX_V3", 'FCD_TRIPS', 69.44444444444444)  # max speed for V3 in m/s
        self.FCD_TRIPS_MAX_DISTANCE_OVERRIDE_POSITION_FIRST_POINT = self.config_reader.getfloat("FCD_TRIPS_MAX_DISTANCE_OVERRIDE_POSITION_FIRST_POINT", 'FCD_TRIPS', 200)  # max distance override in meters
        self.FCD_TRIPS_MIN_LENGTH = self.config_reader.getfloat("FCD_TRIPS_MIN_LENGTH", 'FCD_TRIPS', 100)  # min length of trip in meters
        self.FCD_TRIPS_MIN_TIME = self.config_reader.getint("FCD_TRIPS_MIN_TIME", 'FCD_TRIPS', 1)  # min time of trip in seconds
        self.FCD_TRIPS_REMOVE_STOPS = self.config_reader.getboolean("FCD_TRIPS_REMOVE_STOPS", 'FCD_TRIPS', False)  # remove stops in trips
        self.FCD_TRIPS_MAX_DISTANCE_BETWEEN_DATA = self.config_reader.getfloat("FCD_TRIPS_MAX_DISTANCE_BETWEEN_DATA", 'FCD_TRIPS', 20000)  # max distance between data in meters
        self.FCD_TRIPS_MAX_DELTA_PROGR = self.config_reader.getfloat("FCD_TRIPS_MAX_DELTA_PROGR", 'FCD_TRIPS', 20000)  # max delta progression in meters
        
        # OUPTUT
        self.OUTPUT_AGG_INT = self.config_reader.getfloat("OUTPUT_AGG_INT", 'OUTPUT', 15)
        self.OUTPUT_STATE_COMPRESSION = self.config_reader.getboolean("OUTPUT_STATE_COMPRESSION", 'OUTPUT', None)
        self.OUTPUT_STATE_LEVEL_COMPRESSION = self.config_reader.getint("OUTPUT_STATE_LEVEL_COMPRESSION", 'OUTPUT', 5)  # livello di compressione per lo stato (1-9)

        # WEB_SERVER
        self.WEB_SERVER_HOST = self.config_reader.get("WEB_SERVER_HOST", 'WEB_SERVER', '0.0.0.0')
        self.WEB_SERVER_PORT = self.config_reader.getint("WEB_SERVER_PORT", 'WEB_SERVER', 5000)
        self.WEB_SERVER_DEBUG = self.config_reader.getboolean("WEB_SERVER_DEBUG", 'WEB_SERVER', True)

        # INTERNAL DATABASE
        self.DATABASE_URL = self.config_reader.get("DATABASE_URL", 'DATABASE', 'sqlite:///executions.db')

        # IPC
        self.IPC_USE = self.config_reader.getboolean("IPC_USE", 'IPC', True) # True or False
        self.IPC_BUCKET = self.config_reader.get("IPC_BUCKET", 'IPC', "m4i")
        self.IPC_BACKEND = self.config_reader.get("IPC_BACKEND", 'IPC', "local") # local or redis
        self.IPC_HOST = self.config_reader.get("IPC_HOST", 'IPC', "localhost") # localhost or redis server address
        self.IPC_PORT = self.config_reader.getint("IPC_PORT", 'IPC', 6379) # redis server port or free port for local
        self.IPC_DB = self.config_reader.getint("IPC_DB", 'IPC', 0) # redis db number or not used for local
        self.IPC_COMPRESSION = self.config_reader.get("IPC_COMPRESSION", 'IPC', "lz4") # compression method for data tranfer # "blosclz", "lz4", "lz4hc", "snappy", "zlib", "zstd", "gzip", "bz2", "zip", "lzma" or None (lz4 default)
        self.IPC_COMPRESSION_LEVEL = self.config_reader.getint("IPC_COMPRESSION_LEVEL", 'IPC', 5) # compression level for data tranfer (1-9) (default 5)
        
        # PARALLEL
        self.PARALLEL_USE = self.config_reader.getboolean("PARALLEL_USE", 'PARALLEL', False)
        self.PARALLEL_NUMCPUS = self.config_reader.getint("PARALLEL_NUMCPUS", 'PARALLEL', 1)
        self.PARALLEL_ENGINE = self.config_reader.get("PARALLEL_ENGINE", 'PARALLEL', "ray")
        self.PARALLEL_CLUSTER_ADDRESS = self.config_reader.get("PARALLEL_CLUSTER_ADDRESS", 'PARALLEL', None)

        for section, name, value in self.config_reader.items():
            if not hasattr(self, name.upper()):
                logging.warning(f"Setting {section}:{name.upper()} not found in IniClass, setting it to {value}")
                setattr(self, name.upper(), value)

        

        