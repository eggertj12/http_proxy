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

# Import our classes
from SocketReader import SocketReader
from HttpHelper import HttpHelper
from Message import Message
from Exceptions import *


#-----------------------------------------------------------------------------------------------------------

def connect_to_server(message):
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn.connect((message.hostname, int(message.port)))
    return conn

def forward_message(message, reading, writing):
    # Let the world know who we are
    message.add_via('RatherPoorProxy')

    # Write the message to target socket
    writing.sendall(message.to_string())

    content = message.has_content()
    if content == 'content-length':
        HttpHelper.read_content_length(reading, writing, int(message.headers['content-length']))

    elif content == 'chunked':
        HttpHelper.read_chunked(reading, writing)

    print "Done with forward_message"


#-----------------------------------------------------------------------------------------------------------

def connection_handler(client_socket):
    client_reader = SocketReader(client_socket)
    persistent = True

    server_reader = None

    while persistent:
        try:
            # # select blocks on list of sockets until reading / writing is available
            # # or until timeout happens, set timeout of 30 seconds for dropped connections
            # socket_list = [client_reader.get_socket()]
            # readList, writeList, errorList = select.select(socket_list, [], socket_list, SocketReader.TIMEOUT)

            # if errorList:
            #     print "Socket error"
            #     break

            # if len(readList) == 0:
            #     print "Socket timeout"
            #     break

            req = Message()
            print "Entering parse_request"
            req.parse_request(client_reader)

            req.print_message(True)

            # Only a small subset of requests are supported
            if not req.verb in ('GET', 'POST', 'HEAD'):
                resp = HttpHelper.create_response('405', 'Method Not Allowed')
                client_reader.sendall(resp.to_string)
                # log(req, resp, addr)
                # jump to cleanup
                break            

            try:
                server_socket = connect_to_server(req)
            # Get this gaierror if it is impossible to open a connection
            # Blame it on the client and send a Bad request response
            except socket.gaierror, e:
                resp = HttpHelper.create_response('400', 'Bad request')
                client_reader.sendall(resp.to_string())
                # log(req, resp, addr)
                # Jump directly to cleanup
                break

            server_reader = SocketReader(server_socket)

            forward_message(req, client_reader, server_reader)
            
            resp = Message()
            resp.parse_response(server_reader)

            resp.print_message(True)

            forward_message(resp, server_reader, client_reader)

#            if not resp.is_persistent(req):
            # Clean up server connection
            # TODO: check for possible persistent connection
            server_reader.close()
            server_socket = None

            # Determine if we shall loop
            persistent = req.is_persistent()
        except TimeoutException:
            print "connection timed out. Closing"
            persistent = False
        except SocketClosedException, e:
            print 'Client closed socket'
            persistent = False
        except socket.error, e:
            # TODO: handle this more fine grained (or better yet analyse reasons)
            print 'Unknown socket error'
            persistent = False

    # End of while loop
    if server_reader != None:
        server_reader.close()

    client_reader.close()
    print "done with request\r\n"


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

    print "Heard new connection:", addr
    connection_handler(incoming_socket)
    
# clean up afterwards
listenSocket.shutdown(2)
listenSocket.close()