from socket import *
import socket
import sys
import select
import threading
import datetime
import logging
import urllib
import email.utils as eut
import os

from SocketReader import SocketReader
from HttpHelper import HttpHelper


#---------------------------------------------------------------------------------------------


#-----------------------------------------------------------------------------------------------------------

def read_request(reading):
    req = HttpHelper.parse_request_line(reading)

    print req.verb, req.path, req.version

#-----------------------------------------------------------------------------------------------------------

def connecion_handler(client_socket):
    client_reader = SocketReader(client_socket)

    req = read_request(client_reader)


#-----------------------------------------------------------------------------------------------------------
# Program start
#-----------------------------------------------------------------------------------------------------------

#Send in two variables, portnr and log.txt
if (len(sys.argv) != 3):
    # print 'Need two arguments, port number and file for logging'
    sys.exit(1)

port = int(sys.argv[1])

# Set up a listening socket for accepting connection
listenSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
listenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
listenSocket.bind(('', port))

listenSocket.listen(5)

# Then it's easy peasy from here on, just sit back and wait
while True:
    incoming_socket, addr = listenSocket.accept()

    connecion_handler(incoming_socket)
    
# clean up afterwards
listenSocket.shutdown(2)
listenSocket.close()