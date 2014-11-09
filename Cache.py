import threading
import urllib
import email.utils as eut
import os
import datetime

from SocketReader import SocketReader
from Message import Message

# Class for handling the cache
class Cache:
    CACHE_FOLDER = 'cache/'

    # Create cache filename, and create folder if not already existing
    @staticmethod
    def filename(url, filename, expire_date, content_type):
        my_dir = Cache.CACHE_FOLDER + str(url)

        ExpireDate = str(expire_date)
        if ExpireDate == 'None':
            return None

        date = str.replace(str.replace(str.replace(ExpireDate, ':', ''), ' ', ''), '-', '')
        lock = threading.Lock()
        with lock:
            if not os.path.exists(my_dir):
                os.makedirs(my_dir)

        filename = filename.split("?")[0] + '|' + content_type

        return my_dir + '/' + date + urllib.quote_plus(filename)


    # Save response message to file to store headers
    @staticmethod
    def cache_headers(message, filename):
        lock = threading.Lock()
        data = message.to_string()
        filename = filename + '.hdr'
        with lock:
            file = open(filename, "w")
            file.write(data)
            file.close()

    # Restore headers from saved file
    @staticmethod
    def restore_headers(message, filename):
        lock = threading.Lock()
        filename = filename + '.hdr'
        with lock:
            try:
                file = open(filename, "r")
                file.readline()
                message.parse_headers(file)
                file.close()
            except:
                return


    # Saving data to cache file
    @staticmethod
    def cache_file(filename, data):
        lock = threading.Lock()
        with lock:
            file = open(filename, "ab+")
            file.write(data)
            file.close()


    # Check if data is on proxy cache
    @staticmethod
    def is_in_cache(url, filename):
        lock = threading.Lock()
        mypath = Cache.CACHE_FOLDER + str(url) + '/'
        with lock:
            if not os.path.exists('cache'):
                os.makedirs('cache')
            if not os.path.exists(Cache.CACHE_FOLDER + url):
                return None

            searchfile = urllib.quote_plus(filename)

            for f in os.listdir(mypath):
                s_file = f.split('%7C')[0]
                if s_file.endswith(searchfile):
                    currenttime = datetime.datetime.now()
                    filetime = datetime.datetime.strptime(str(s_file)[0:14], "%Y%m%d%H%M%S")
                    if currenttime < filetime:
                        if f.endswith('.hdr'):
                            f = f[:-4]
                        myfile = mypath + f
                        return myfile
                    else:
                        #If the f is expired it is thrown away
                        os.remove(mypath + f)

            return None

    # Serve a file from cache
    @staticmethod
    def send_cached_file(message, writing):
        read = 0

        myfile = message.cache_file

        currfile = open(myfile,'r')

        filelength = os.path.getsize(myfile)
        content_type = urllib.unquote_plus(myfile).split('|')[-1]

        Cache.restore_headers(message, myfile)
        # Serve everything with content-length method, remove chunked if it was set
        if 'content-encoding' in message.headers:
            message.headers['content-encoding'] = str.replace(message.headers['content-encoding'].lower(), 'chunked', '')

        message.headers['custom-header'] = 'SERVED FROM CACHE'
        message.headers['content-type'] = content_type
        message.headers['content-length'] = str(filelength)
        writing.sendall(message.to_string())

        while read < filelength:
            response = currfile.read(SocketReader.READ_SIZE)
            read = read + len(response)
            writing.sendall(response)
        currfile.close()
