# ----------------------------------------------------------------------------------------------------
# http_proxy.py
# 
# Simple http proxy server
#
# Uses some helper classes
#    Message for representing the messages (request or response) and operations on those
#    SocketReader is a wrapper for sockets which provides buffered reading from socket of lines or bytes
#    Exceptions contains two custom exceptions we use
#    Cache is a static class for wrapping cache operations
#    HttpHelper is also a static class containing some operations for handling the communication
# 
#
# It handles parallel connections using threading, handling each persistent connection in a separate thread
# Pipelining is supported, although testing with Opera has been not really successful where the browser 
#    closes the socket resulting in a broken pipe error.
# Logging is done using the thread safe logging module and cache uses locking to protect file operations
# 
# 
# 
# ----------------------------------------------------------------------------------------------------

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
from Cache import Cache
from Message import Message
from Exceptions import *


#-----------------------------------------------------------------------------------------------------------
# Logging

# Write the request / response line to given log file
def log(request, response, addr):
    if not ('host' in request.headers):
        request.headers['host'] = ''

    log =  ': ' + str(addr[0]) + ':' + str(addr[1]) + ' ' 
    log = log + request.verb + ' ' + request.scheme + request.hostname + request.path + ' : '
    log = log + response.status + ' ' + response.text
    logging.warning(log)


#-----------------------------------------------------------------------------------------------------------
# Connection related

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
# Will load from cache if this is a cached response
def forward_message(message, reading, writing, cache_file = None):
    # Let the world know who we are
    message.add_via('RatherPoorProxy')

    if message.cache_file != None:
        Cache.send_cached_file(message, writing)

    else:
        # Write the message to target socket
        writing.sendall(message.to_string())

        content = message.has_content()
        if content == 'content-length':
            HttpHelper.read_content_length(reading, writing, int(message.headers['content-length']), cache_file)

        elif content == 'chunked':
            HttpHelper.read_chunked(reading, writing, cache_file)


#-----------------------------------------------------------------------------------------------------------
# The main handler loop

# Handle one persistent connection
def connection_handler(client_socket, addr):
    client_reader = SocketReader(client_socket)
    persistent = True

    # Keep requests and possibly out of order responses (f.ex. cached) in a dictionary
    req_id = resp_id = 0
    request_queue = {}
    response_queue = {}

    server_reader = None

    # Loop as long as the client wants and also until all queued requests have been answered
    while persistent or req_id > resp_id:
        try:
            # First check if we have a ready response to send to client
            if (resp_id in response_queue):
                req = request_queue[resp_id]
                resp = response_queue.pop(resp_id)
                forward_message(resp, server_reader, client_reader)
                log(req, resp, addr)
                resp_id = resp_id + 1

                # If no more queued messages just force close connection
                if req_id == resp_id:
                    persistent = False
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
                req = request_queue[resp_id]
                server_socket = connect_to_server(req)
                if server_socket == None:
                    # TODO: handle not opened connection (Should hardly happen here)
                    print "Could not open connection to server"
                    break
                server_reader = SocketReader(server_socket, req.hostname)
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

            # Client is ready to send data
            if client_reader != None and client_reader.get_socket() in readList:
                req = Message()
                try:
                    req.parse_request(client_reader)
                except SocketClosedException:
                    # Client has closed socket from it's end
                    # print "Client closed connection"
                    persistent = False
                    continue

                # Store request to have it available when it's response arrives
                request_queue[req_id] = req

                # req.print_message(True)

                # Only a small subset of requests are supported
                if not req.verb in ('GET', 'POST', 'HEAD'):
                    # Create a response and store in queue until this request will be answered
                    resp = HttpHelper.create_response('405', 'Method Not Allowed')
                    resp.headers['connection'] = 'close'
                    response_queue[req_id] = resp
                    req_id = req_id + 1
                    continue

                cache_file = Cache.is_in_cache(req.hostname, req.path)
                if cache_file != None:
                    resp = HttpHelper.create_response('200', 'OK')
                    resp.cache_file = cache_file
                    response_queue[req_id] = resp
                    req_id = req_id + 1
                    continue
                    

                if server_reader == None:
                    server_socket = connect_to_server(req)
                    if server_socket == None:
                        # Respond if the requested server can not be connected to
                        resp = HttpHelper.create_response('502', 'Bad gateway')
                        resp.headers['connection'] = 'close'
                        response_queue[req_id] = resp
                        req_id = req_id + 1
                        continue
                    server_reader = SocketReader(server_socket, req.hostname)

                # Might have to connect to a different server.
                elif server_reader.hostname != req.hostname:
                    server_socket = connect_to_server(req)
                    if server_socket == None:
                        resp = HttpHelper.create_response('502', 'Bad gateway: ' + req.hostname)
                        resp.headers['connection'] = 'close'
                        response_queue[req_id] = resp
                        req_id = req_id + 1
                        continue
                    server_reader = SocketReader(server_socket, req.hostname)

                # Finally ready to send the request
                forward_message(req, client_reader, server_reader)
                req_id = req_id + 1
            
            # Server is ready to send data
            elif server_reader != None and server_reader.get_socket() in readList:
                resp = Message()
                try:
                    resp.parse_response(server_reader)
                except SocketClosedException:
                    # Server has closed socket from it's end
                    # print "Server closed connection"
                    server_reader = None
                    continue

                # resp.print_message(True)
                resp.hostname = req.hostname

                response_queue[resp_id] = resp

                cache_file = None
                if req.is_cacheable() and resp.is_cacheable():
                    if 'content-type' in resp.headers:
                        ct = resp.headers['content-type']
                    else:
                        ct = ''
                    cache_file = Cache.filename(req.hostname, req.path, resp.cache_expiry_date(), ct)
                    Cache.cache_headers(resp, cache_file)


                forward_message(resp, server_reader, client_reader, cache_file)

                log(req, resp, addr)

                resp_id = resp_id + 1


                if not resp.is_persistent():
                    # Server wants to close connection. Clean up
                    server_reader.close()
                    server_socket = None

            # Determine if we shall loop
            persistent = req.is_persistent()

        except TimeoutException:
            # print "connection timed out. Closing"
            persistent = False
        except SocketClosedException, e:
            # print 'Client closed socket'
            persistent = False
        except socket.error, e:
            # TODO: handle this more fine grained (or better yet analyse reasons)
            persistent = False
            break

    # End of while loop, cleanup
    if server_reader != None:
        server_reader.close()
        server_reader = None

    client_reader.close()
    client_reader = None

    request_queue = None
    response_queue = None

#-----------------------------------------------------------------------------------------------------------
# Program start
#-----------------------------------------------------------------------------------------------------------

#Send in two variables, portnr and log.txt
if (len(sys.argv) != 3 and len(sys.argv) != 4):
    print 'Need two arguments, port number and file for logging'
    sys.exit(1)

port = int(sys.argv[1])

threaded = True
if len(sys.argv) == 4:
    print "Starting in unthreaded mode"
    threaded = False

# Set up logger configuration
logging.basicConfig(filename=sys.argv[2], format='%(asctime)s %(message)s', datefmt='%Y-%m-%dT%H:%M:%S+0000')

# Set up a listening socket for accepting connection
listenSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
listenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
listenSocket.bind(('', port))

listenSocket.listen(5)

# Then it's easy peasy from here on, just sit back and wait
while True:
    incoming_socket, addr = listenSocket.accept()

    if threaded:
        # dispatch to thread, set it as deamon as not to keep process alive
        thr = threading.Thread(target=connection_handler, args=(incoming_socket, addr))
        thr.daemon = True
        thr.start()
    else:
        connection_handler(incoming_socket, addr)
    
# clean up afterwards
listenSocket.shutdown(2)
listenSocket.close()