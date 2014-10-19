from socket import *
import socket
import sys
import select
import threading
import datetime
import logging

buflen = 4096

class Message:
    """ Class to hold request info """
    def __init__(self):
        self.headers = {}
    
def read_line_from_socket(s):
    line = ""
    c = ""
    while c != "\n":
        c = s.recv(1)
        line = line + c
    return line.strip(" \r\n\t")

def parse_request_line(s, req):
    sp = read_line_from_socket(s)
#    print "request_line: ", sp[0]
    req.verb, req.path, req.version = sp.split(" ")
    return

def parse_response_line(s, resp):
    sp = read_line_from_socket(s)
    resp.version, resp.status, resp.text = sp.split(" ", 2)
    return

def parse_headers(s, req):
    line = read_line_from_socket(s)
    while len(line) > 0:
#       print "line: ", line
        splitted = line.split(':', 1)
        key = splitted[0].lower()
        value = splitted[1]
        req.headers[key] = value.strip(" \n\r\t")
        line = read_line_from_socket(s)
#       print buf
    return

def create_request(req):
    request = req.verb + " " + req.path + " " + req.version + "\r\n"
    for header in req.headers:
        request += header + ": " + req.headers[header] + "\r\n"
    request = request + "\r\n"
    return request

def create_response(resp):
    response = resp.version + " " + resp.status + " " + resp.text + "\r\n"
    for header in resp.headers:
        response += header + ": " + resp.headers[header] + "\r\n"
    response = response + "\r\n"
    return response

def get_dest_port(req):
    if ':' in req.headers['host']:
        req.headers['host'], port = req.headers['host'].split(':')
    else:
        port = '80'
    return port

def open_connection(req):
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn.connect((req.headers["host"], int(req.port)))
    return conn

def log(req, response, addr):
    # log =  ': ' + str(addr[0]) + ':' + str(addr[1]) + ' ' + req.verb + ' ' + req.path + ' : ' \
    # + str(response.split()[1] + ' ' + str(response.split()[2]))
    # logging.basicConfig(filename=sys.argv[2], format='%(asctime)s %(message)s', datefmt='%Y-%m-%dT%H:%M:%S+0000')
    # logging.warning(log)
    pass
   

###################################################
# Define a handler for threading
# Will serve each connection and then close socket
###################################################

def echoThread(connectionsocket, addr):

    # print debug info
    print 'connection from: ' + str(addr[0]) + ':' + str(addr[1])

    # Loop to handle multiple messages, and messages bigger than buffer size
    while True:

        # # select blocks on list of sockets until reading / writing is available
        # # or until timeout happens
        # readList, writeList, errorList = select.select([connectionsocket], [], [], 30)

        # # empty list of sockets means a timeout occured
        # if (len(readList) == 0):
        #     peer = connectionsocket.getpeername()
        #     break

#        packet, addr1 = connectionsocket.recvfrom(buflen)

        # length of 0 means connection was closed

        # TODO: detect closecd connection
        # if (len(packet) == 0):
        #     break

        req = Message()

        parse_request_line(connectionsocket, req)
        parse_headers(connectionsocket, req)

        # host header is required
        if not ('host' in req.headers):
            print 'invalid request'
            break

        req.port = get_dest_port(req)
        connection = open_connection(req)

        request_string = create_request(req)
        print request_string
        connection.send(request_string)
        print "request sent"

        # TODO: send rest of message if available

        resp = Message()

        parse_response_line(connection, resp)
        print "response line read"
        parse_headers(connection, resp)
        print "headers read"

        print resp.headers

        response = create_response(resp)
        print response

        # print len(response)
        # print "--------------------------------------------------"
        # print response
        # print "--------------------------------------------------"

        #Logging to file
#        log(req, response, addr)

        lengd = int(resp.headers['content-length'])
        print "lengd:", lengd

        #Used to fetch from response until all data has been sent
        connectionsocket.send(response)

        read = 0
        while read < lengd:
            response = connection.recv(buflen)
            read = read + len(response)
            connectionsocket.send(response)
            print "len(response), read, content-length", len(response), int(read), int(lengd)

        break

    print "leaving thread"            
    # All work done for thread, close socket
    connectionsocket.close()

#################################################
# Program start
#################################################

#Send in two variables, portnr and log.txt
if (len(sys.argv) != 3):
    print 'Need two arguments, port number and file for logging'
    sys.exit(1)

port = int(sys.argv[1])

# Set up a listening socket for accepting connection
listenSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
listenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
listenSocket.bind(('', port))
try:
    listenSocket.listen(1)

    # Then it's easy peasy from here on, just sit back and wait
    while True:
        connectionSocket, addr = listenSocket.accept()
        connectionSocket.settimeout(30)

        # dispatch to thread, set it as deamon as not to keep process alive
        thr = threading.Thread(target=echoThread, args=(connectionSocket, addr))
        thr.daemon = True
        thr.start()
#        echoThread(connectionSocket, addr)
except timeout:
    print 'connection closed after timeout'
    
# clean up afterwards
listenSocket.shutdown(2)
listenSocket.close()