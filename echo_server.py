from socket import *
import sys
import select

if (len(sys.argv) != 2):
    print 'Need one argument, port number'
    sys.exit(1)

port = int(sys.argv[1])

print 'Using port: ' + str(port)

listenSocket = socket(AF_INET, SOCK_STREAM)
listenSocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
listenSocket.bind(('', port))
listenSocket.listen(1)
while 1:
    connectionSocket, addr = listenSocket.accept()
    print 'connection from: ' + str(addr[0]) + ':' + str(addr[1])

    while True:
        readList, writeList, errorList = select.select([connectionSocket], [], [], 60)

        if (len(readList) == 0):
            peer = connectionSocket.getpeername()
            print 'connection closed after timeout: ' + str(peer[0]) + ':' + str(peer[1])
            break

        message = connectionSocket.recv(1024)

        if (len(message) == 0):
            peer = connectionSocket.getpeername()
            print 'connection closed by client: ' + str(peer[0]) + ':' + str(peer[1])
            break

        connectionSocket.send(message)

    connectionSocket.close()

listenSocket.shutdown(2)
listenSocket.close()