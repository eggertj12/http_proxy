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
        self.persistent = False
        self.headers = {}

# This is really unefficient it seems
# TODO: implement a buffered version somehow
def read_line_from_socket(s):
    line = ""
    c = ""
    while c != "\n":
        c = s.recv(1)

        # 0 length read means the connection was closed
        if c == "":
            raise IOError('Nothing to read')

        line = line + c

    return line.strip(" \r\n\t")

# Get the first line of a request and split into parts
def parse_request_line(s, req):
    sp = read_line_from_socket(s)
    #print "request_line: ", sp
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
    #print "response_line: ", sp
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

def send_cached_file(myfile, writing):
    read = 0
    filestat = os.stat(myfile)
    filelength = filestat.st_size
    while read < filelength:
        response = myfile.read(buflen)
        read = read + len(response)
        writing.sendall(response)

# Read data sent via chunked transfer-encoding
# This is primitive and does not support all features yet
def read_chunked(reading, writing):
    chunk_line = read_line_from_socket(reading)
    size = int(chunk_line.split(";", 1)[0], 16)

    # TODO: check for trailing headers is chunk line

    # print "first chunk size: ", size

    # Loop while there are chunks
    while size > 0:
        # Start by sending the chunk size
        writing.sendall(chunk_line + "\r\n")

        read = 0
        while read < size:
            response = reading.recv(min(buflen, size - read))
            # print response
            read = read + len(response)
            writing.sendall(response)

        # Try to read next chunk line, fall back to size zero in case server does not send terminating chunk
        chunk_line = read_line_from_socket(reading)

        if len(chunk_line) == 0:
            chunk_line = read_line_from_socket(reading)

        if len(chunk_line) > 0:
            size = int(chunk_line.split(";", 1)[0], 16)
        else:
            size = 0

        #print "chunk line: ", chunk_line
        #print "chunk size: ", size

    # Send final 0 size chunk to recipient
    writing.sendall(chunk_line + "\r\n")


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
def is_persistent(msg):

    # First check if server wants to close connection
    if (msg.version == 'HTTP/1.1'):
        if ('connection' in msg.headers) and ('close' in msg.headers['connection']):
            return False

    elif (msg.version == 'HTTP/1.0'):        
        if not ('connection' in msg.headers and 'keep-alive' in msg.headers['connection']):
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
    lock = threading.Lock()
    with lock:
        print "ENTERING CACHE_FILE FOLDER\n"
        date = str.replace(str(eut.parsedate(expire_date)), ', ','_')
        #print filename
        os.chdir('cache/' + url)
        print str(os.getcwd()) +  "\n"
        file = open(date + base64.standard_b64encode(filename), "a")
        file.write(data)
        file.close()
        print str(os.getcwd() + "\n")
        os.chdir('..')
        print str(os.getcwd() + "\n")
        os.chdir('..')

#Check if data is on proxy
def is_in_cache(url, filename):
#    if not os.path.exists('cache'):
#        os.makedirs('cache')
    lock = threading.Lock()

    with lock:
        if not os.path.exists('cache'):
            os.makedirs(r'cache')
        if not os.path.exists('cache/' + url):
            os.makedirs(r'cache/' + str(url))
            return None
        mypath = "cache/" + str(url)

        #print "NOW " +str(os.getcwd() + "\n")
        #os.chdir('cache')
        #if not os.path.exists(url):
        #    os.makedirs(url)
        #    os.chdir('..')
        #    return None
        #os.chdir('..')
        print "ISINCACHE 1 " + str(os.getcwd() + "\n")

        searchfile = base64.standard_b64encode(filename)[:29]
        #os.chdir(mypath)
        for file in os.listdir(mypath):
            if file.endswith(searchfile):
                myfile = open(mypath + str(file), 'r')
                content  = myfile.read()
                myfile.close()
                return content
        print "ISINCACHE 2 " + str(os.getcwd() + "\n")

        return None

###
# Handle request
def read_request(request_queue, client_socket, server_socket):
    # Create a message object for the request
    req = Message()

    parse_request_line(client_socket, req)

    # Only a small subset of requests are supported
    if not req.verb in ('GET', 'POST', 'HEAD'):
        resp = create_error_response(req, '405', 'Method Not Allowed')
        client_socket.sendall(create_response(resp))
        log(req, resp, addr)
        # jump to cleanup
        return None            

    parse_headers(client_socket, req)

    # host header is required
    if not ('host' in req.headers):
        resp = create_error_response(req, '400', 'Bad request')
        client_socket.sendall(create_response(resp))
        log(req, resp, addr)
        return None            

    ## CHECK IF FILE IS IN CACHE
    if (is_in_cache(req.headers['host'], req.path) == None):
        req.port = get_dest_port(req)

        try:
            server_socket = open_connection(req)

        # Get this gaierror if it is impossible to open a connection
        # Blame it on the client and send a Bad request response
        except socket.gaierror, e:
            resp = create_error_response(req, '400', 'Bad request')
            client_socket.sendall(create_response(resp))
            log(req, resp, addr)

            # Jump directly to cleanup
            return None

        # Add required via header
        if req.version[:5] == 'HTTP/':
            ver = req.version[5:]
        else:
            ver = req.version
        if 'via' in req.headers:
            req.headers['via'] += ', ' + ver + ' p-p-p-proxy'
        else:
            req.headers['via'] = ver + ' p-p-p-proxy'

        req.persistent = is_persistent(req)

        # Request object is ready push to queue
        request_queue.append(req)

        request_string = create_request(req)
        server_socket.sendall(request_string)

        # Send rest of message if available (POST data)
        if 'content-length' in req.headers:
            length = int(req.headers['content-length'])
            read_content_length(client_socket, server_socket, length)

        elif 'transfer-encoding' in req.headers:
            tf_encoding = req.headers['transfer-encoding']
            # print "transfer-encoding", tf_encoding
            if "chunked" in tf_encoding.lower():
                read_chunked(client_socket, server_socket)

        return server_socket

    else:
        ### RETURN FILE
        print "FILE IS IN CACHE!"
        send_cached_file(is_in_cache(req.headers['host'], req.path),client_socket)
        return None

###
# Handle response
def read_response(req, client_socket, server_socket):
    # Now on to handling the response
    resp = Message()

    parse_response_line(server_socket, resp)
    parse_headers(server_socket, resp)

    response = create_response(resp)

    ################CACHING ###################
    #def cache_file(req.headers['host'], request.path, req.headers['expired-date'], data)
    

    #Logging to file

    log(req, resp, addr)

    # Send the response
    client_socket.sendall(response)

    resp.persistent = is_persistent(resp)

    # Get the response data if any
    if 'content-length' in resp.headers:
        length = int(resp.headers['content-length'])
        read_content_length(server_socket, client_socket, length)

    elif 'transfer-encoding' in resp.headers:
        tf_encoding = resp.headers['transfer-encoding']
        if "chunked" in tf_encoding.lower():
            read_chunked(server_socket, client_socket)

    return resp


###################################################
# Define a handler for threading
# Will serve each connection and then close socket
###################################################

def connecion_handler(client_socket, addr):

    # print debug info
    # print 'entering thread, connection from: ' + str(addr[0]) + ':' + str(addr[1])

    server_socket = None
    request_queue = []
    req = None

    # Loop to handle persistent connections
    while True:


        # select blocks on list of sockets until reading / writing is available
        # or until timeout happens, set timeout of 5 seconds for dropped connections
        if server_socket != None:
            socketList = [client_socket, server_socket]
        else:
            socketList = [client_socket]

        readList, writeList, errorList = select.select(socketList, [], [], 30)


        # empty list of sockets means a timeout occured
        if (len(readList) == 0):
            peer = client_socket.getpeername()
            break

        if (client_socket in readList):
            # print "reading client_socket", readList

            try:
                server_socket = read_request(request_queue, client_socket, server_socket)
            except IOError, e:
                # print "client closed connection"
                break


            # returns None on any error
            if server_socket == None:
                break

            req = request_queue[0]
            request_queue = request_queue[1:]

        elif (server_socket in readList):
            # print "reading server_socket", readList

            try:
                resp = read_response(req, client_socket, server_socket)
            except IOError, e:
                # print "server closed connection"
                break

        # Check if the server_socket should be kept alive, cleanup otherwise
        if not req.persistent:
            server_socket.close()
            break

#        break



    # print "leaving thread"            
    # All work done for thread, close sockets
    client_socket.close()

#################################################
# Program start
#################################################

#Send in two variables, portnr and log.txt
if (len(sys.argv) != 3):
    # print 'Need two arguments, port number and file for logging'
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