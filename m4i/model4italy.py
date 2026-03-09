import logging

from .base_m4i_model import BaseM4IModel
from .utils.util import get_parametric_name, nested_dict_from_key_value_list
from typing import Optional
import sys
import json
def main(**kwargs)->Optional[BaseM4IModel]:    
    import argparse
    import os
        
    prc = None
    try:
        # Controlla se esistono argomaenti passati alla line di comando
        if len(sys.argv) > 1 and not kwargs:
            parser = argparse.ArgumentParser(description="Run an elaboration or start the server")
            parser.add_argument('-p', '--params', default='params.json', help='JSON file with parameters (default: params.json)')
            parser.add_argument('-d', '--params_data', help='JSON file with data parameters (default: params_data.json)')
            parser.add_argument('-c', '--config', default='settings.ini', help='Configuration file (default: settings.ini)')
            parser.add_argument('-m', '--monitor', help='Folder of results of monitor process. If not specified, the process is not monitored')
            parser.add_argument('-O', '--option', action='append', help='Option parameter. Override JSON setting.')
            parser.add_argument('-e', '--env', action='append', help='Override Enviroment Variables.')
            subparsers = parser.add_subparsers(dest='command', help='Sub-command help')

            # Subparser for the "run" command
            parser_run = subparsers.add_parser('run', help='Run an elaboration')
            parser_run.add_argument('-p', '--params', default='params.json', help='JSON file with parameters (default: params.json)')
            parser_run.add_argument('-d', '--params-data', help='JSON file with data parameters (default: params_data.json)')
            parser_run.add_argument('-c', '--config', default='settings.ini', help='Configuration file (default: settings.ini)')        
            parser_run.add_argument('-o', '--op', help='Operation. Override JSON setting (default: None)')
            parser_run.add_argument('-O', '--option', action='append', help='Option parameter. Override JSON setting.')
            parser_run.add_argument('-e', '--env', action='append', help='Override Enviroment Variables.')

            # Subparser for the "server" command
            parser_server = subparsers.add_parser('server', help='Start the web server')
            parser_server.add_argument('-P', '--port', type=int, help='web server port')
            parser_server.add_argument('-H', '--host', help='Web server host address')
            parser_server.add_argument('-D', '--debug', action='store_true', help='Enable web server debug mode')

            parser_init_db = subparsers.add_parser('init_db', help='Initialize the database')
            parser_init_db.add_argument('-u', '--url', help='Database URL')
            parser_init_db.add_argument('-H', '--host', help='Database host address')
            parser_init_db.add_argument('-P', '--port', help='Database port')
            parser_init_db.add_argument('-U', '--user', help='Database user')
            parser_init_db.add_argument('-W', '--password', help='Database password')
            parser_init_db.add_argument('-N', '--name', help='Database name')
            parser_init_db.add_argument('-T', '--type', help='Database type')
            parser_init_db.add_argument('-D', '--driver', help='Database driver')

            
            args = parser.parse_args()
        else: 
            args = argparse.Namespace()
            args.command = 'run'
            args.op = None            
            args.params = 'params.json'
            args.params_data = None
            args.config = 'settings.ini'
            args.monitor = None
            args.host = None
            args.port = None
            args.debug = None
            args.user = None
            args.password = None
            args.name = None
            args.type = None
            args.driver = None
            args.host = None
            args.port = None
            args.option = None
            args.env = None

        for k,v in kwargs.items():
            if hasattr(args, k):
                setattr(args, k, v)
        if args.monitor is not None:
            prc = launch_monitor(directory=args.monitor)
        else:
            prc = None
            
        # Set default command to 'run' if no command is provided
        if args.command is None:
            args.command = 'run'
        if args.env:
            for env in args.env:
                key, value = env.split('=', 1)
                os.environ[key] = value                        
        options = {}
        if args.option:
            for option in args.option:
                try:
                    key, value = option.split('=', 1)
                except:
                    raise Exception(f"Invalid option format: {option}. Use key:subkey:subsubkey=value format.")
                options[key] = value
            options = nested_dict_from_key_value_list(options)
        for k,v in os.environ.items():
            if k.startswith("M4I_"):                
                option_key = k[len("M4I_"):]
                
                try:
                    key, value = option_key.split('=', 1)
                except:
                    key = option_key
                    value = v
                settings = options.setdefault("settings", {})
                settings[key] = value
        if hasattr(args,"op") and args.op:
            options["op"] = args.op
        if args.command == 'init_db':
            init_db(
                ini_file=args.config,
                db_type=args.type,
                db_driver=args.driver,
                db_user=args.user,
                db_password=args.password,
                db_host=args.host,
                db_port=args.port,
                db_name=args.name
            )
        else:
            if args.command == 'run':
                return run(ini_file=args.config,
                params=args.params,
                params_data=args.params_data if args.params_data is not None else "params_data.json",
                options=options)
                
            elif args.command == 'server':
                run_server(ini_file=args.config,
                host=args.host,
                port=args.port,
                debug=args.debug)
            else:
                parser.print_help()
    except Exception as e:
        if __name__ == "__main__":
            print(f"Error: {e}")
            os._exit(1)
        else:
            raise e
        
    finally:
        try:
            if prc:
                prc.kill()
        except:
            pass

def launch_monitor(directory="monitor"):
    import multiprocessing as mp
    from .monitor import monitor_process
    prc = None
    def monitor():
        monitor_process(process_name="python",interval=5, output_file=None, directory=directory)          

    prc = mp.Process(target=monitor, daemon=True)
    prc.start()
    return prc

def init_db(ini_file="settings.ini", db_type=None, db_driver=None, db_user=None, db_password=None, db_host=None, db_port=None, db_name=None):
    """
    Initialize the database connection.
    This function is called when the script is executed directly.
    """
    from .iniclass import IniClass
    from .database import DB
    from .log import Logger
    from .utils import parse_sqlalchemy_url, generate_sqlalchemy_url

    config = IniClass(ini_file=ini_file)
    Logger.initLogger(
        level=logging.getLevelName(config.LOG_LEVEL),
        console=config.LOG_ON_CONSOLE,
        file=config.LOG_ON_FILE,
        db=config.LOG_ON_DATABASE,
        engine=None,                    
        log_name=config.LOG_NAME, 
        dir_log=config.LOG_DIR,
        format=config.LOG_FORMAT,
        execution_format=config.LOG_EXECUTION_FORMAT
        )
    url_dict = {}
    if config.DATABASE_URL:
        url = config.DATABASE_URL
        url_dict = parse_sqlalchemy_url(url)
    if db_type is not None or db_driver is not None or db_user is not None or db_password is not None or db_host is not None or db_port is not None or db_name is not None:
        url_dict = {}
    if db_type:
        url_dict["db_type"] = db_type
    if db_driver:
        url_dict["db_driver"] = db_driver
    if db_user:
        url_dict["db_user"] = db_user
    if db_password:
        url_dict["db_password"] = db_password
    if db_host:
        url_dict["db_host"] = db_host
    if db_port:
        url_dict["db_port"] = db_port
    if db_name:
        url_dict["db_name"] = db_name                    
        url = generate_sqlalchemy_url(**url_dict)                
    DB.init_db(url) 

def open_db(ini_file="settings.ini", options: dict | None = None):
    from .iniclass import IniClass
    from .database import DB
    from .log import Logger
    config = IniClass(ini_file=ini_file, options=options)
    Logger.initLogger(
        level=logging.getLevelName(config.LOG_LEVEL),
        console=config.LOG_ON_CONSOLE,
        file=config.LOG_ON_FILE,
        db=config.LOG_ON_DATABASE,
        engine=None,                    
        log_name=config.LOG_NAME, 
        dir_log=config.LOG_DIR,
        format=config.LOG_FORMAT,
        execution_format=config.LOG_EXECUTION_FORMAT
        )
    try:
        if config.DATABASE_URL:
            DB.open_db(config.DATABASE_URL)  
        else:
            raise ValueError("DATABASE_URL is not set in the configuration file.")
    except Exception as e:
        raise Exception(f"Error initializing database: {e}")            
    Logger.setEngine(DB.get_engine())   
    return config

def run(ini_file="settings.ini", params="params.json", params_data=None, options: dict=None):
    import os
    from .dispatcher import Dispatcher
    if not isinstance(params, (list,tuple)):
        params = [params]
    if not isinstance(params_data, (list,tuple)):
        params_data = [params_data]

    params = [ p for p in params + params_data if p is not None]

    config = open_db(ini_file=ini_file, options=options)
    return Dispatcher(params=params, options=options, ini=config).run()       

def run_server(ini_file="settings.ini", host=None, port=None, debug=None):
    """
    Start the web server.
    This function is called when the script is executed directly.
    """
    from .server.server import start_server
    
    config = open_db(ini_file=ini_file)
    host = host if host is None else config.WEB_SERVER_HOST
    port = port if port is None  else config.WEB_SERVER_PORT
    debug = debug if debug is None  else config.WEB_SERVER_DEBUG
    start_server(host=host, port=port, debug=debug, config=config)    
    
if __name__ == "__main__":
    main()
        
