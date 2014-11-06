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
    req = HttpHelper.parse_headers(reading, req)
    HttpHelper.get_dest_port(req)
    return req

def connect_to_server(req):
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn.connect((req.headers["host"], int(req.port)))
    return conn

def read_response(reading):
    resp = HttpHelper.parse_response_line(reading)
    resp = HttpHelper.parse_headers(reading, resp)
    return resp


#-----------------------------------------------------------------------------------------------------------

def connection_handler(client_socket):
#    client_socket.settimeout(30)
    client_reader = SocketReader(client_socket)
    print "handling new request"

    while True:

        # select blocks on list of sockets until reading / writing is available
        # or until timeout happens, set timeout of 5 seconds for dropped connections
        socket_list = [client_reader.get_socket()]
        readList, writeList, errorList = select.select(socket_list, [], socket_list, 30)

        if errorList:
            print "Socket error"
            break

        if len(readList) == 0:
            print "Socket timeout"
            break

        try:
            req = read_request(client_reader)
        except IOError, e:
            if e.message == 'Socket closed':
                print 'Client closed socket'
                break

        req.print_request(True)

        # Only a small subset of requests are supported
        if not req.verb in ('GET', 'POST', 'HEAD'):
            resp = HttpHelper.create_response('405', 'Method Not Allowed')
            client_socket.sendall(HttpHelper.response_to_string(resp))
            # log(req, resp, addr)
            # jump to cleanup
            break            

        server_socket = connect_to_server(req)
        server_reader = SocketReader(server_socket)

        server_socket.sendall(HttpHelper.request_to_string(req))
        
        try:
            resp = read_response(server_reader)
        except IOError, e:
            if e.message == 'Socket closed':
                print 'Server closed socket'
                break
#        resp.print_response()
        client_socket.sendall(HttpHelper.response_to_string(resp))

        try:
            # Get the response data if any
            if 'content-length' in resp.headers:
                length = int(resp.headers['content-length'])
                HttpHelper.read_content_length(server_reader, client_reader.get_socket(), length)

            elif 'transfer-encoding' in resp.headers:
                tf_encoding = resp.headers['transfer-encoding']
                if "chunked" in tf_encoding.lower():
                    HttpHelper.read_chunked(server_reader, client_reader.get_socket())

        except socket.error, e:
            print 'Socket.error'


        server_socket.close()
        break

    client_socket.close()
    print "done with request"


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