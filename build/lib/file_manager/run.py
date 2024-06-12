#!/usr/bin/python3
"""
    Version:
--------

- file-manager v0.0.1
"""
import tornado.ioloop
from tornado.options import define, options
from file_manager.sources.app import make_application

define('rootpath', default= '~/repos/pi-gpx-camera/data', help = 'Root directory for server', type = str)
define('address', default = '127.0.0.1', help = 'Bound IP address', type = str)
define('port', default = '9000', help = 'Bound TCP port', type = int)

def main():
    options.parse_command_line()
    application = make_application(options.rootpath)
    application.listen(options.port, address = options.address)
    print(f"Starting file-manager on {options.address}:{options.port}")
    tornado.ioloop.IOLoop.instance().start()
if __name__ == '__main__':
    main()