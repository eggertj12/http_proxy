from socket import *
import sys
import select
import threading

###################################################
# Define a handler for threading
# Will serve each connection and then close socket
###################################################

def echoThread(socket, addr):

    # print debug info
    print 'connection from: ' + str(addr[0]) + ':' + str(addr[1])

    # Loop to handle multiple messages, and messages bigger than buffer size
    while True:

        # select blocks on list of sockets until reading / writing is available
        # or until timeout happens
        readList, writeList, errorList = select.select([socket], [], [], 60)

        # empty list of sockets means a timeout occured
        if (len(readList) == 0):
            peer = socket.getpeername()
            print 'connection closed after timeout: ' + str(peer[0]) + ':' + str(peer[1])
            break

        # Socket was ready. Read message and check it's length
        message = socket.recv(1024)
        messageLength = len(message)

        # A zero length message on a stream from select means it has been closed
        if (messageLength == 0):
            peer = socket.getpeername()
            print 'connection closed by client: ' + str(peer[0]) + ':' + str(peer[1])
            break

        print message
        
        # # In case of incomplete sending it needs to be wrapped in a loop
        # # to make sure everything gets sent
        # sentBytes = 0
        # while (sentBytes < messageLength):
        #     sent = socket.send(message[sentBytes:])

        #     # Again 0 bytes through socket means it has closed, this time probably by some error
        #     if (sent == 0):
        #         print 'Error sending on connection.'
        #         sys.exit(1)
        #     sentBytes += sent

    # All work done for thread, close socket
    socket.close()

#################################################
# Program start
#################################################

if (len(sys.argv) != 2):
    print 'Need one argument, port number'
    sys.exit(1)

port = int(sys.argv[1])

# Set up a listening socket for accepting connection
listenSocket = socket(AF_INET, SOCK_STREAM)
listenSocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
listenSocket.bind(('', port))
listenSocket.listen(1)

# Then it's easy peasy from here on, just sit back and wait
while True:
    connectionSocket, addr = listenSocket.accept()

    # dispatch to thread, set it as deamon as not to keep process alive
    thr = threading.Thread(target=echoThread, args=(connectionSocket, addr))
    thr.deamon = True
    thr.start()

# clean up afterwards
listenSocket.shutdown(2)
listenSocket.close()
