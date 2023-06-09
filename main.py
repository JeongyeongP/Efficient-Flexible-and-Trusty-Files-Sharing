import os
from socket import *
import hashlib
import argparse
import threading
import time
import gzip
import json


def _argparse():
    print('Parsing argument...')
    parser = argparse.ArgumentParser()
    parser.add_argument('--ip', dest='ip', action='store', help='peer address')
    argu = parser.parse_args()
    return argu


def create_direct():
    global dir_name
    dir_name = "share"
    if os.path.exists(dir_name):
        print(">>>Share folder already exists")
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
        print(">>>Share folder has been created")


def file_info(dirname):
    dir_path = os.path.abspath(dirname)
    filename_list = os.listdir(dir_path)
    file_dict = {}
    sub_dict = {}
    for i in range(0, len(filename_list)):
        path = os.path.join(dir_path, filename_list[i]) #share/file_name
        if os.path.isfile(path):  # if file exists
            size = os.path.getsize(path)  # get size
            md5 = get_md5(path) # get md5 hash value
            file_dict[filename_list[i]] = [size, md5]
        #Finding sub_directory in the main directory
        elif os.path.isdir(path):
            print('sub dir path is ', path)
            file_dict[filename_list[i]] = subdirect_file_info(path)[1]
    return filename_list, file_dict


def subdirect_file_info(subdir_path):
    sub_filename_list = os.listdir(subdir_path)
    global sub_file_dict
    sub_file_dict = {}
    for i in range(0, len(sub_filename_list)):
        path = os.path.join(subdir_path,sub_filename_list[i])
        if os.path.isfile(path):
            size = os.path.getsize(path)
            md5 = get_md5(path)
            sub_file_dict[sub_filename_list[i]] = [size, md5]
    return sub_filename_list, sub_file_dict


# get md5 hash value of the given file in string
def get_md5(file):
    file_md5 = hashlib.md5()
    with open(file, 'rb') as f:
        for text in f:
            file_md5.update(text)
    return file_md5.hexdigest()


def compressing_file(path):
    file = open(path, 'rb')
    f_compress = gzip.open((path + '.gz'), 'wb')
    f_compress.writelines(file)
    f_compress.close()
    file.close()
    return path + '.gz'


def decompressing_file(path):
    path = compressing_file[:-3]  # getting path except for .gz
    f_compress = gzip.open(compressing_file(path), 'rb')
    f = open(path, 'wb')
    content = f_compress.read()
    f.write(content)
    f.close()
    f_compress.close()


lock = threading.Lock()


class Server:
    def server(self):
        self.connect()
        self.accept()

    def connect(self):
        global server_socket
        server_socket = socket(AF_INET, SOCK_STREAM)
        server_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        server_socket.bind(('', server_port))
        server_socket.listen(1)
        print("...Listening...")
        # time.sleep(3)

    def accept(self):
        global connectionSocket
        while True:
            try:
                connectionSocket, address = server_socket.accept()
                print(">>>Server is connected to", peer_addr)
                self.file_list_sender()
                #time.sleep(0.1)
                #self.file_download(connectionSocket)
                connectionSocket.close()
            except:
                time.sleep(0.2)

    def file_list_sender(self):
        msg = 'online'
        connectionSocket.sendall(msg.encode())
        time.sleep(0.01) #wait for answer
        ans = connectionSocket.recv(buffer_size).decode()
        if ans=='online':
            dict = file_info('share')[1]
            file_dict = json.dumps(dict)
            connectionSocket.sendall(file_dict.encode())
            print("dictionary sent")
            self.file_download()
        if ans != 'online':
            print("We lost peer")

    def file_download(self):
        download_file = {}
        #Get names of files first
        download_file = connectionSocket.recv(buffer_size).decode()
        result = json.loads(download_file)
        lock.acquire()
        dir_path = os.path.abspath('share')
        if len(result) != 0:
            for name in result:
                path = os.path.join(dir_path, name)
                if type(result[name]) is dict:
                    self.folder_download(connectionSocket, name, result[name])
                else:
                    file = open(path, 'wb')
                    while True:
                        data = connectionSocket.recv(buffer_size)
                        if not data:
                            break
                        file.write(data)
                    file.close()
                    #time.sleep(0.01)
            print(">>>Download Completed")
        elif len(result) == 0:
            print("No file to download, already synchronized")
        lock.release()

    def folder_download(self, folder_name, folder_files):
        dir_path = os.path.abspath('share')
        sub_path = os.path.join(dir_path, folder_name)
        os.makedirs(sub_path)
        lock.acquire()
        for name in folder_files:
            path = os.path.join(sub_path, name)
            file = open(path, 'wb')
            while True:
                data = connectionSocket.recv(buffer_size)
                if not data:
                    break
                file.write(data)
            file.close()
            #time.sleep(0.01)
        lock.release()

class Client:
    def client(self):
        self.connect_server()

    def connect_server(self):
        global client_socket
        while True:
            try:
                client_socket = socket(AF_INET, SOCK_STREAM)
                client_socket.connect((peer_addr, peer_port))
                print("...Connection request has sent to ip", peer_addr, "...")
                self.newfile_list_get()
                client_socket.close()
            except ConnectionRefusedError:
                time.sleep(0.1)

    #getting file info from the peer's server
    def newfile_list_get(self):
        global new_file_dict
        new_file_dict = {}
        msg = ''
        msg = client_socket.recv(buffer_size).decode()
        if msg == 'online':
            stat = 'online'
            client_socket.sendall(stat.encode())
            file_dict = client_socket.recv(buffer_size).decode()
            new_file_dict = json.loads(file_dict)
            self.detect_file(new_file_dict)
            #print("new file list is ", new_file_dict)
        elif msg != 'online':
            print("We lost connection")
        return new_file_dict

    def detect_file(self, new_dict):
        origin_dict = file_info('share')[1] #Get dictionary containing info of files in local device
        update_dict = {}
        for file in origin_dict:
            if file not in new_dict:
                update_dict[file] = origin_dict[file]
        dict = json.dumps(update_dict)
        client_socket.sendall(dict.encode())
        self.send_file(update_dict)
        return update_dict

    def send_file(self, send_files):
        # print("...Sending files...")
        lock.acquire()
        dir_path = os.path.abspath('share')
        if len(send_files)!=0:
            for file in send_files:
                path = os.path.join(dir_path, file)
                #sub-directory
                if type(send_files[file]) is dict:
                    self.send_folder(file, send_files[file])
                else:
                    send_f = open(path, 'rb')
                    while True:
                        File = send_f.read(buffer_size)
                        client_socket.sendall(File)
                        if not File:
                            break
                    send_f.close()
        elif len(send_files)==0:
            print("No file to send, already synchronized")
        lock.release()

    def send_folder(self, folder_name, folder_dict):
        # send folder name first
        lock.acquire()
        while True:
            folder = folder_name.snedall(buffer_size)
            if not folder:
                break
        dir_path = os.path.abspath('share')
        sub_folder = os.path.join(dir_path,folder_name)
        for name in folder_dict:
            path = os.path.join(sub_folder,name)
            send_f = open(path, 'rb')
            while True:
                File = send_f.read(buffer_size)
                client_socket.sendall(File)
                if not File:
                    break
            send_f.close()
        lock.release()


if __name__ == "__main__":
    args = _argparse()
    peer_addr = args.ip
    buffer_size = 1024*1024
    server_port = 20001
    peer_port = 20001
    serv = Server()
    cli = Client()
    create_direct()
    server = threading.Thread(target=serv.server)
    client = threading.Thread(target=cli.client)
    server.start()
    #time.sleep(0.02)
    client.start()
