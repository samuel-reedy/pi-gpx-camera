#!/usr/bin/python3
"""
    Version:
--------

- file-manager v0.0.1
"""
import tornado.ioloop
from tornado.options import define, options
from file_manager.sources.app import make_application
import os
import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the command line options
# find the data directory under in the project directory
define('rootpath', default= os.path.join(os.path.dirname(__file__), '../..', 'data'), help = 'Root directory for server', type = str) 
# check to see if it exists
if not os.path.exists(options.rootpath):
    logger.info(f"Creating directory: {options.rootpath}")
    os.makedirs(options.rootpath)

# define('rootpath', default= '/home/pi/repos/pi-gpx-camera/data', help = 'Root directory for server', type = str)

define('address', default = '127.0.0.1', help = 'Bound IP address', type = str)
define('port', default = '8085', help = 'Bound TCP port', type = int)

def main():
    options.parse_command_line()
    application = make_application(options.rootpath)
    # application.listen(options.port, address = options.address)
    # print(f"Starting file-manager on {options.address}:{options.port}")
    application.listen(options.port)
    print(f"Starting file-manager on: {options.port}")
    tornado.ioloop.IOLoop.instance().start()
if __name__ == '__main__':
    main()