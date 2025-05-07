from monitor import monitor_process
def monitor():
    monitor_process(process_name="python",interval=5, output_file=None, directory="monitor")        
if __name__ == "__main__":
    import multiprocessing as mp
    #monitor = lambda: monitor_process(process_name="python",interval=1, output_file=None, directory="monitor")
    prc = mp.Process(target=monitor, daemon=True)
    prc.start()

import argparse
from libs.iniclass import IniClass
from libs.server import start_server
from libs.simulation import run_assignment
from libs.utils import parse_sqlalchemy_url, generate_sqlalchemy_url
from libs.database import DB
from libs.log.logger import Logger

def main():    
    try:
        parser = argparse.ArgumentParser(description="Run the simulation algorithm or start the server")
        parser.add_argument('-p', '--params', default='params.json', help='JSON file with parameters (default: params.json)')
        parser.add_argument('-c', '--config', default='settings.ini', help='Configuration file (default: settings.ini)')

        subparsers = parser.add_subparsers(dest='command', help='Sub-command help')

        # Subparser for the "run" command
        parser_run = subparsers.add_parser('run', help='Run the simulation')
        parser_run.add_argument('-p', '--params', default='params.json', help='JSON file with parameters (default: params.json)')
        parser_run.add_argument('-c', '--config', default='settings.ini', help='Configuration file (default: settings.ini)')

        # Subparser for the "server" command
        parser_server = subparsers.add_parser('server', help='Start the Flask server')
        parser_server.add_argument('-P', '--port', type=int, help='Flask server port')
        parser_server.add_argument('-H', '--host', help='Flask server host address')
        parser_server.add_argument('-D', '--debug', action='store_true', help='Enable Flask server debug mode')

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
            
        # Set default command to 'run' if no command is provided
        if args.command is None:
            args.command = 'run'

        if args.command == 'run':
            # Load the configuration
            config = IniClass(ini_file=args.config)
            Logger.initLogger(dir_log=config.LOG_DIR)
            DB.open_db(config.DATABASE_URL)
            Logger.initLogger(session=DB.get_session())
            
            run_assignment(params=args.params, ini=config)
            
        elif args.command == 'server':
            # Load the configuration
            config = IniClass(ini_file=args.config)
            Logger.initLogger(dir_log=config.LOG_DIR)
            DB.open_db(config.DATABASE_URL)
            Logger.initLogger(session=DB.get_session())

            host = args.host if args.host else config.FLASK_HOST
            port = args.port if args.port else config.FLASK_PORT
            debug = args.debug if args.debug else config.FLASK_DEBUG
            start_server(host=host, port=port, debug=debug, config=config)
        elif args.command == 'init_db':
            config = IniClass(ini_file=args.config)
            Logger.initLogger(dir_log=config.LOG_DIR)
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
            Logger.initLogger(session=DB.get_session())
        else:
            parser.print_help()
    except Exception as e:
        raise e
    finally:
        pass

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        raise e
    finally:
        try:
            prc.kill()
        except:
            pass