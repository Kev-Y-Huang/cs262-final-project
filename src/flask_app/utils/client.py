import os
import queue
import select
import socket
import sys
import threading
import time

import pyaudio

HOST = socket.gethostname()
TCP_PORT = 1538
UDP_PORT = 1539

BUFF_SIZE = 65536
CHUNK = 10*1024

class Client:
    def __init__(self, host=HOST, tcp_port=TCP_PORT, udp_port=UDP_PORT):
        self.s = socket.socket()
        self.host = host
        self.tcp_port = tcp_port
        self.udp_port = udp_port

        self.exit = threading.Event()

        self.procs = []

    def upload_file(self, file_path):
        filename = os.path.basename(file_path)
        size = len(filename)
        size = bin(size)[2:].zfill(16) # encode filename size as 16 bit binary, limit your filename length to 255 bytes

        self.s.send(size.encode())
        self.s.send(filename.encode())

        filesize = os.path.getsize(file_path)
        filesize = bin(filesize)[2:].zfill(32) # encode filesize as 32 bit binary
        self.s.send(filesize.encode())

        file_to_send = open(file_path, 'rb')

        l = file_to_send.read()
        self.s.sendall(l)
        file_to_send.close()
        print('File Sent')

    def getAudioData(self, client_socket):
        inputs = [client_socket]
        while not self.exit.is_set():
            read_sockets, _, _ = select.select(inputs, [], [], 0.1)
            for sock in read_sockets:
                frame,_= sock.recvfrom(BUFF_SIZE)
                self.audio_q.put(frame)

    def stream_audio(self):
        try:
            client_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            client_socket.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,BUFF_SIZE)
            p = pyaudio.PyAudio()
            stream = p.open(format=p.get_format_from_width(2),
                            channels=1,
                            rate=48000,
                            output=True,
                            frames_per_buffer=CHUNK)
                            
            # create socket
            message = b'Hello'
            client_socket.sendto(message,(self.host,self.udp_port))
            DATA_SIZE,_= client_socket.recvfrom(BUFF_SIZE)
            DATA_SIZE = int(DATA_SIZE.decode())
            self.audio_q = queue.Queue(maxsize=DATA_SIZE)
            cnt=0

            t1 = threading.Thread(target=self.getAudioData, args=(client_socket,))
            t1.start()
            self.procs.append(t1)
            time.sleep(5)
            DURATION = DATA_SIZE*CHUNK/48000
            # print('[Now Playing]... Data',DATA_SIZE,'[Audio Time]:',DURATION ,'seconds')
            while not self.exit.is_set():
                frame = self.audio_q.get()
                stream.write(frame)
                # print('[Queue size while playing]...',q.qsize(),'[Time remaining...]',round(DURATION),'seconds')
                DURATION-=CHUNK/48000
                if self.audio_q.empty():
                    break
        except:
            client_socket.close()
            print('Audio closed')
            sys.exit(1)

    def run_client(self, client):
        self.s.connect((self.host, self.tcp_port))

        stream_proc = threading.Thread(target=client.stream_audio, args=())
        stream_proc.start()
        self.procs.append(stream_proc)

        try:
            while not self.exit.is_set():
                file_path = input()
                self.upload_file(file_path)
        except:
            self.exit.set()
            for proc in self.procs:
                proc.join()
            self.s.close()
            print('Client closed')
            sys.exit(1)

if __name__ == "__main__":
    client = Client()
    client.run_client(client)