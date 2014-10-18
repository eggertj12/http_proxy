#from socket import *
import socket
import sys
import select
import threading
import datetime

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
        readList, writeList, errorList = select.select([connectionsocket], [], [], 60)

        # empty list of sockets means a timeout occured
        if (len(readList) == 0):
            peer = connectionsocket.getpeername()
            print 'connection closed after timeout: ' + str(peer[0]) + ':' + str(peer[1])
            break
        packet, addr1 = connectionsocket.recvfrom(1024)
#        requestname = (packet.split('\n'))[0]
#        hostaddr = (packet.split(' '))[1]
#        hostaddr2 = (packet.split(' '))[3]
        hostaddr = (packet.split('\n')[1]).split(' ')[1]
        hostipaddr = socket.gethostbyname(hostaddr.strip(' \t\n\r'))
        
#        print requestname
        print 'hostaddress is: ' + hostaddr
        print 'ipaddress is: ' + hostipaddr

        #For the log file
        date = datetime.datetime.today()
        print date + ' : ' + str(addr[0]) + ':' + str(addr[1]) + ' ' + packet.split()[0] + ' ' + packet.split()[1] + ' : '
            
    # All work done for thread, close socket
    socket.close()

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
listenSocket.listen(1)

#Test for writing to fil
logfile = sys.argv[2]
file = open( logfile, 'w')
file.write('hallo')
file.close()

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