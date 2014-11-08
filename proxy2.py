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

# Write the request / response line to given log file
def log(request, response, addr):
    if not ('host' in request.headers):
        request.headers['host'] = ''

    log =  ': ' + str(addr[0]) + ':' + str(addr[1]) + ' ' 
    log = log + request.verb + ' ' + request.scheme + request.hostname + request.path + ' : '
    log = log + response.status + ' ' + response.text
    logging.warning(log)


# Setup a connection to the upstream server
def connect_to_server(message):
    try:
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn.connect((message.hostname, int(message.port)))
    # Get this gaierror if it is impossible to open a connection
    except socket.gaierror, e:
        return None

    return conn

# Handle sending the message (request or response) and accompanying data if available
def forward_message(message, reading, writing):
    # Let the world know who we are
#    message.add_via('RatherPoorProxy')

    # Write the message to target socket
    writing.sendall(message.to_string())

    content = message.has_content()
    if content == 'content-length':
        HttpHelper.read_content_length(reading, writing, int(message.headers['content-length']))

    elif content == 'chunked':
        HttpHelper.read_chunked(reading, writing)


#-----------------------------------------------------------------------------------------------------------

# Handle one persistent connection
def connection_handler(client_socket, addr):
    client_reader = SocketReader(client_socket)
    persistent = True

    req_id = resp_id = 0
    request_queue = {}
    response_queue = {}

    server_reader = None

    while persistent or req_id > resp_id:
        try:

            # First check if we have a ready response to send to client
            if (resp_id in response_queue):
                req = request_queue.pop(resp_id)
                resp = response_queue.pop(resp_id)
                forward_message(resp, server_reader, client_reader)
                log(req, resp, addr)
                resp_id = resp_id + 1
                continue

            # Find out which sockets to try and listen to
            socket_list = []
            if persistent:
                # Client has indicated it wants to keep connection open
                socket_list.append(client_socket)

            if server_reader != None:
                socket_list.append(server_reader.get_socket())
            elif req_id > resp_id:
                # Still have responses pending, open a connection to the server
                server_socket = connect_to_server(request_queue[resp_id])
                if server_socket == None:
                    # TODO: handle not opened connection (Should hardly happen here)
                    print "Could not open connection to server"
                    break
                server_reader = SocketReader(server_socket)
                socket_list.append(server_reader.get_socket())

            # select blocks on list of sockets until reading / writing is available
            # or until timeout happens, set timeout of 30 seconds for dropped connections
            readList, writeList, errorList = select.select(socket_list, [], socket_list, SocketReader.TIMEOUT)

            if errorList:
                print "Socket error"
                break

            if len(readList) == 0:
                print "Socket timeout"
                break

            if client_reader != None and client_reader.get_socket() in readList:
                req = Message()
                try:
                    req.parse_request(client_reader)
                except SocketClosedException:
                    # Client has closed socket from it's end
                    persistent = False
                    continue

                request_queue[req_id] = req

                print req.verb, req.hostname, req.port, req.path, req.version
                req.print_message(True)

                # Only a small subset of requests are supported
                if not req.verb in ('GET', 'POST', 'HEAD'):
                    resp = HttpHelper.create_response('405', 'Method Not Allowed')
                    response_queue[req_id] = resp
                    req_id = req_id + 1
                    continue

                if server_reader == None:
                    server_socket = connect_to_server(req)
                    if server_socket == None:
                        resp = HttpHelper.create_response('400', 'Bad request')
                        response_queue[req_id] = resp
                        req_id = req_id + 1
                        continue
                    server_reader = SocketReader(server_socket)

                forward_message(req, client_reader, server_reader)
                req_id = req_id + 1
            
            elif server_reader != None and server_reader.get_socket() in readList:
                resp = Message()
                try:
                    resp.parse_response(server_reader)
                except SocketClosedException:
                    # Client has closed socket from it's end
                    server_reader = None
                    continue

                resp.print_message(True)
#                print resp.status, resp.text, resp.version
                response_queue[resp_id] = resp

                forward_message(resp, server_reader, client_reader)

                req = request_queue.pop(resp_id)

                log(req, resp, addr)

                resp_id = resp_id + 1


                if not resp.is_persistent():
                    # Clean up server connection
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

    # End of while loop, cleanup
    if server_reader != None:
        server_reader.close()
        server_reader = None

    client_reader.close()
    client_reader = None

    request_queue = None
    response_queue = None
    print "done with connection\r\n"


#-----------------------------------------------------------------------------------------------------------
# Program start
#-----------------------------------------------------------------------------------------------------------

#Send in two variables, portnr and log.txt
if (len(sys.argv) != 3):
    # print 'Need two arguments, port number and file for logging'
    sys.exit(1)

port = int(sys.argv[1])

logging.basicConfig(filename=sys.argv[2], format='%(asctime)s %(message)s', datefmt='%Y-%m-%dT%H:%M:%S+0000')

# Set up a listening socket for accepting connection
listenSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
listenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
listenSocket.bind(('', port))

listenSocket.listen(5)

# Then it's easy peasy from here on, just sit back and wait
while True:
    incoming_socket, addr = listenSocket.accept()

    print "Heard new connection:", addr
    connection_handler(incoming_socket, addr)
    
# clean up afterwards
listenSocket.shutdown(2)
listenSocket.close()