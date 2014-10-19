from socket import *
import socket
import sys
import select
import threading
import datetime
import logging

buflen = 4096

class Request:
    """ Class to hold request info """
    def __init__(self):
        self.headers = {}
    
def parse_request_line(buf, req):
    sp = buf.split("\n", 1)
#    print "request_line: ", sp[0]
    req.verb, req.path, req.version = sp[0].split(" ")
    return sp[1]

def parse_headers(buf, req):
    line, buf = buf.split("\n", 1)
    line = line.strip(" \n\r\t")
    while len(line) > 0:
#       print "line: ", line
        splitted = line.split(':', 1)
        key = splitted[0].lower()
        value = splitted[1]
        req.headers[key] = value.strip(" \n\r\t")
        splitted = buf.split("\n", 1)
        line = splitted[0]
        try:
            buf = splitted[1]
        except Exception:
            buf = "\n"
        # buf = buf.split("\n", 1)
        line = line.strip(" \n\r\t")
#       print buf
    return buf

def create_request(url):
    response = requests.get(url)
#    print "PRINTED RESPONSE " + response
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

def create_response():
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

        # select blocks on list of sockets until reading / writing is available
        # or until timeout happens
        readList, writeList, errorList = select.select([connectionsocket], [], [], 30)

        # empty list of sockets means a timeout occured
        if (len(readList) == 0):
            peer = connectionsocket.getpeername()
            break

        packet, addr1 = connectionsocket.recvfrom(buflen)

        # length of 0 means connection was closed
        if (len(packet) == 0):
            break

        req = Request()

        trimmed = parse_request_line(packet, req)
        trimmed = parse_headers(trimmed, req)

        # host header is required
        if not ('host' in req.headers):
            print 'invalid request'
            break

        req.port = get_dest_port(req)
        connection = open_connection(req)
        connection.send(packet)
        response = connection.recv(buflen)
        lengd = len(response)
        #Used to fetch from response until all data has been sent
        connectionsocket.send(response)
        if lengd == buflen:
            while len(response)!= 0:
                response = connection.recv(buflen)
                connectionsocket.send(response)

        #Logging to file
        log =  ': ' + str(addr[0]) + ':' + str(addr[1]) + ' ' + req.verb + ' ' + req.path + ' : ' \
            + req.verb + ' ' + req.path
        logging.basicConfig(filename=sys.argv[2], format='%(asctime)s %(message)s', datefmt='%Y-%m-%dT%H:%M:%S+0000')
        logging.warning(log)
            
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
except timeout:
    print 'connection closed after timeout'
    
# clean up afterwards
listenSocket.shutdown(2)
listenSocket.close()