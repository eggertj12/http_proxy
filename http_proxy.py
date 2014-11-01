from socket import *
import socket
import sys
import select
import threading
import datetime
import logging
from urlparse import urlsplit
import base64
import email.utils as eut
import os

buflen = 4096

# A simple class to hold request / response messages
class Message:
    """ Class to hold request info """
    def __init__(self):
        self.verb = ''
        self.path = ''
        self.version = ''
        self.status = ''
        self.text = ''
        self.headers = {}

# This is really unefficient it seems
# TODO: implement a buffered version somehow
def read_line_from_socket(s):
    line = ""
    c = ""
    while c != "\n":
        c = s.recv(1)
        line = line + c
    return line.strip(" \r\n\t")

# Get the first line of a request and split into parts
def parse_request_line(s, req):
    sp = read_line_from_socket(s)
    # print "request_line: ", sp
    req.verb, req.path, req.version = sp.split(" ")
    o = urlsplit(req.path)
    req.path = o.path
    if len(o.query) > 0:
        req.path += "?" + o.query
    if len(o.fragment) > 0:
        req.path += "#" + o.fragment
    return

# Get the first line of a response and split into parts
def parse_response_line(s, resp):
    sp = read_line_from_socket(s)
    # print "response_line: ", sp
    resp.version, resp.status, resp.text = sp.split(" ", 2)
    return

# Read the headers line by line and store in dictionary
def parse_headers(s, req):
    line = read_line_from_socket(s)
    while len(line) > 0:
        splitted = line.split(':', 1)
        key = splitted[0].lower()
        value = splitted[1]
        req.headers[key] = value.strip(" \n\r\t")
        line = read_line_from_socket(s)
    return

# Rebuild the request to send to server
def create_request(req):
    request = req.verb + " " + req.path + " " + req.version + "\r\n"
    for header in req.headers:
        request += header + ": " + req.headers[header] + "\r\n"
    request = request + "\r\n"
    return request

# Rebuild the response received to send back to client
def create_response(resp):
    response = resp.version + " " + resp.status + " " + resp.text + "\r\n"
    for header in resp.headers:
        response += header + ": " + resp.headers[header] + "\r\n"
    response = response + "\r\n"
    return response

# Parse host value for port number. Defaults to 80 on not found
def get_dest_port(req):
    if ':' in req.headers['host']:
        req.headers['host'], port = req.headers['host'].split(':')
    else:
        port = '80'
    return port

# Open a socket to the requested server
def open_connection(req):
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn.connect((req.headers["host"], int(req.port)))
    return conn

# Read data sent via buffered mode
def read_content_length(reading, writing, length):
    read = 0
    while read < length:
        response = reading.recv(buflen)
        read = read + len(response)
        writing.sendall(response)


# Read data sent via chunked transfer-encoding
# This is primitive and does not support all features yet
def read_chunked(reading, writing):
    chunk_line = read_line_from_socket(reading)
    size = int(chunk_line.split(";", 1)[0], 16)

    # TODO: check for trailing headers is chunk line

    # Loop while there are chunks
    while size > 0:
        # Start by sending the chunk size
        writing.sendall(chunk_line + "\r\n")

        read = 0
        while read < size:
            response = reading.recv(min(buflen, size - read))
            read = read + len(response)
            writing.sendall(response)

        # Try to read next chunk line, fall back to size zero in case server does not send terminating chunk
        chunk_line = read_line_from_socket(reading)
        if len(chunk_line) > 0:
            size = int(chunk_line.split(";", 1)[0], 16)
        else:
            size = 0

    # TODO: check for trailer-part

    # Read remaining stuff
    line = read_line_from_socket(reading)
    while len(line) > 0:
        # Most likely the connection has been closed by now
        # but there could be more to come
        try:
            writing.sendall(line + "\r\n")
        except socket.error, e:
            pass
        line = read_line_from_socket(reading)
    return

# Determine if the connection is to be kept alive
def is_persistent(req, resp):

    # This is not correct according to the spec. Upstream and downstream should be handled seperately
    # Probably close enough though for the time being

    # First check if server wants to close connection
    if (resp.version == 'HTTP/1.1'):
        if ('connection' in resp.headers) and ('close' in resp.headers['connection']):
            return False

    elif (resp.version == 'HTTP/1.0'):        
        if not ('connection' in resp.headers and 'keep-alive' in resp.headers['connection']):
            return False
    
    # Made it here, assume server wants a persistent connection
    # Then check client request
    if (resp.version == 'HTTP/1.1'):
        if ('connection' in resp.headers) and ('close' in resp.headers['connection']):
            return False
        else:
            return True

    elif (resp.version == 'HTTP/1.0'):
        # Proxies must not keep connections to 1.0 clients
        return False
        
    # Unknown version, assume it is something newer than HTTP/1.1 and default to persistent
    return True

# Helper to create a response in case of error
def create_error_response(req, status, message):
    # set up a Message object for the logger
    resp = Message()
    if hasattr(req, 'version'):
        resp.version = req.version
    else:
        resp.version = 'HTTP/1.1'
    resp.status = status
    resp.text = message
    return resp

# Write the request / response line to given log file
def log(req, response, addr):
    if not ('host' in req.headers):
        req.headers['host'] = ''

    log =  ': ' + str(addr[0]) + ':' + str(addr[1]) + ' ' + req.verb + ' ' + req.headers['host'] + req.path + ' : ' \
    + response.status + ' ' + response.text
    logging.basicConfig(filename=sys.argv[2], format='%(asctime)s %(message)s', datefmt='%Y-%m-%dT%H:%M:%S+0000')
    logging.warning(log)

#Saving data to cache
def cache_file(url, filename, expire_date, data):  
    date = str.replace(str(eut.parsedate(expire_date)), ', ','_')
    print filename
    os.chdir('cache/' + url)
    file = open(date + base64.standard_b64encode(filename), "a")
    file.write(data)
    file.close()
    os.chdir('..')
    os.chdir('..')

#Check if data is on proxy
def is_in_cache(url, filename):
    if not os.path.exists('cache'):
        os.makedirs('cache')
        os.chdir('cache')
    if not os.path.exists(url):
        os.makedirs(url)
        os.chdir('..')
        return None

    searchfile = base64.standard_b64encode(filename)[:29]
    for file in os.listdir('cache\\' + url +'\\'):
        if file.endswith(searchfile):
            myfile = open('cache\\' + url +'\\' + file, 'r')
            content  = myfile.read()
            myfile.close()
            return content
    return None

###################################################
# Define a handler for threading
# Will serve each connection and then close socket
###################################################

def connecion_handler(connectionsocket, addr):

    # print debug info
    print 'connection from: ' + str(addr[0]) + ':' + str(addr[1])

    # Loop to handle persistent connections
    while True:

        # select blocks on list of sockets until reading / writing is available
        # or until timeout happens, set timeout of 5 seconds for dropped connections
        readList, writeList, errorList = select.select([connectionsocket], [], [], 30)

        # empty list of sockets means a timeout occured
        if (len(readList) == 0):
            peer = connectionsocket.getpeername()
            break

        # length of 0 means connection was closed

        # TODO: detect closecd connection
        # if (len(packet) == 0):
        #     break

        # Create a message object for the request
        req = Message()

        parse_request_line(connectionsocket, req)

        # Only a small subset of requests are supported
        if not req.verb in ('GET', 'POST', 'HEAD'):
            resp = create_error_response(req, '405', 'Method Not Allowed')
            connectionsocket.sendall(create_response(resp))
            log(req, resp, addr)
            # jump to cleanup
            break            

        parse_headers(connectionsocket, req)

        # host header is required
        if not ('host' in req.headers):
            resp = create_error_response(req, '400', 'Bad request')
            connectionsocket.sendall(create_response(resp))
            log(req, resp, addr)
            break            

        req.port = get_dest_port(req)

        try:
            connection = open_connection(req)

        # Get this gaierror if it is impossible to open a connection
        # Blame it on the client and send a Bad request response
        except socket.gaierror, e:
            resp = create_error_response(req, '400', 'Bad request')
            connectionsocket.sendall(create_response(resp))
            log(req, resp, addr)

            # Jump directly to cleanup
            break

        # Add required via header
        if req.version[:5] == 'HTTP/':
            ver = req.version[5:]
        else:
            ver = req.version
        if 'via' in req.headers:
            req.headers['via'] += ', ' + ver + ' p-p-p-proxy'
        else:
            req.headers['via'] = ver + ' p-p-p-proxy'

        request_string = create_request(req)
        connection.sendall(request_string)

        # Send rest of message if available (POST data)
        if 'content-length' in req.headers:
            length = int(req.headers['content-length'])
            read_content_length(connectionsocket, connection, length)

        elif 'transfer-encoding' in req.headers:
            tf_encoding = req.headers['transfer-encoding']
            # print "transfer-encoding", tf_encoding
            if "chunked" in tf_encoding.lower():
                read_chunked(connectionsocket, connection)

        # Now on to handling the response
        resp = Message()

        parse_response_line(connection, resp)
        parse_headers(connection, resp)

        response = create_response(resp)

        ############# NOT FINISHED
        # Cache data from server

        #if ('expires' in resp.headers):
        #    cache_file(req.headers['host'], req.path, resp.headers['expires'], "hallo world")

        ##############

        #Logging to file
        log(req, resp, addr)

        # Send the response
        connectionsocket.sendall(response)

        # Get the response data if any
        if 'content-length' in resp.headers:
            length = int(resp.headers['content-length'])
            read_content_length(connection, connectionsocket, length)

        elif 'transfer-encoding' in resp.headers:
            tf_encoding = resp.headers['transfer-encoding']
            if "chunked" in tf_encoding.lower():
                read_chunked(connection, connectionsocket)

        # Check if the connection should be kept alive, cleanup otherwise
        if not is_persistent(req, resp):
            connection.close()
            break

    # print "leaving thread"            
    # All work done for thread, close sockets
    connectionsocket.close()

#################################################
# Program start
#################################################

#Send in two variables, portnr and log.txt
if (len(sys.argv) != 3):
    print 'Need two arguments, port number and file for logging'
    sys.exit(1)

port = int(sys.argv[1])

threaded = True

# Set up a listening socket for accepting connection
listenSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
listenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
listenSocket.bind(('', port))
try:
    listenSocket.listen(5)

    # Then it's easy peasy from here on, just sit back and wait
    while True:
        connectionSocket, addr = listenSocket.accept()
        # Does this make sense
        connectionSocket.settimeout(30)

        if threaded:
            # dispatch to thread, set it as deamon as not to keep process alive
            thr = threading.Thread(target=connecion_handler, args=(connectionSocket, addr))
            thr.daemon = True
            thr.start()
        else:
            connecion_handler(connectionSocket, addr)

except timeout:
    print 'connection closed after timeout'
    
# clean up afterwards
listenSocket.shutdown(2)
listenSocket.close()