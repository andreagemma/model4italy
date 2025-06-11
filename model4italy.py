import logging
from monitor import monitor_process

prc = None
def monitor():
    monitor_process(process_name="python",interval=5, output_file=None, directory="monitor")        


if __name__ == "__main__":
    def main():    
        import argparse
        from libs.iniclass import IniClass
        from libs.server.server import start_server
        from libs.dispatcher import Dispatcher
        from libs.utils import parse_sqlalchemy_url, generate_sqlalchemy_url
        from libs.database import DB
        from libs.log import Logger

        import os
            
        try:
            parser = argparse.ArgumentParser(description="Run an elaboration or start the server")
            parser.add_argument('-p', '--params', default='params.json', help='JSON file with parameters (default: params.json)')
            parser.add_argument('-d', '--params_data', help='JSON file with data parameters (default: params_data.json)')
            parser.add_argument('-c', '--config', default='settings.ini', help='Configuration file (default: settings.ini)')
            parser.add_argument('-o', '--op', help='Operation. Override JSON setting (default: None)')
            parser.add_argument('-m', '--monitor', help='Monitor process', action='store_true', default=False,)

            subparsers = parser.add_subparsers(dest='command', help='Sub-command help')

            # Subparser for the "run" command
            parser_run = subparsers.add_parser('run', help='Run an elaboration')
            parser_run.add_argument('-p', '--params', default='params.json', help='JSON file with parameters (default: params.json)')
            parser_run.add_argument('-d', '--params-data', help='JSON file with data parameters (default: params_data.json)')
            parser_run.add_argument('-c', '--config', default='settings.ini', help='Configuration file (default: settings.ini)')        
            parser_run.add_argument('-o', '--op', help='Operation. Override JSON setting (default: None)')

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
            if args.monitor:
                global prc
                import multiprocessing as mp
                prc = mp.Process(target=monitor, daemon=True)
                prc.start()
            else:
                prc = None
                
            # Set default command to 'run' if no command is provided
            if args.command is None:
                args.command = 'run'

            if args.command == 'init_db':
                config = IniClass(ini_file=args.config)
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
                if args.type:
                    url_dict["db_type"] = args.type
                if args.driver:
                    url_dict["db_driver"] = args.driver
                if args.user:
                    url_dict["db_user"] = args.user
                if args.password:
                    url_dict["db_password"] = args.password
                if args.host:
                    url_dict["db_host"] = args.host
                if args.port:
                    url_dict["db_port"] = args.port
                if args.name:
                    url_dict["db_name"] = args.name                    
                url = generate_sqlalchemy_url(**url_dict)                
                DB.init_db(url)          
            else:
                config = IniClass(ini_file=args.config)
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
                DB.open_db(config.DATABASE_URL)  
                Logger.setEngine(DB.get_engine())
                    
                if args.command == 'run':
                    params = args.params
                    if args.params_data:
                        params = [args.params_data, args.params]                
                    else:
                        if os.path.exists("params_data.json"):
                            params = ["params_data.json", args.params]
                    Dispatcher(params=params, ini=config, op=args.op).run()       
                    
                elif args.command == 'server':
                    host = args.host if args.host else config.WEB_SERVER_HOST
                    port = args.port if args.port else config.WEB_SERVER_PORT
                    debug = args.debug if args.debug else config.WEB_SERVER_DEBUG
                    start_server(host=host, port=port, debug=debug, config=config)
                else:
                    parser.print_help()
        except Exception as e:
            print(f"Error: {e}")
            os._exit(1)
            
        finally:
            pass


    try:
        main()
    except Exception as e:
        raise e
    finally:
        try:
            if prc:
                prc.kill()
        except:
            pass
