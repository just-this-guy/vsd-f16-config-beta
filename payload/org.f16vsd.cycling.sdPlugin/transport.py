import socket,base64,os,hashlib,struct,select,json

class WebSocket:
    def __init__(self,port):
        self.socket=socket.create_connection(('127.0.0.1',port),timeout=5);self.buffer=b'';self.parts=b''
        key=base64.b64encode(os.urandom(16)).decode()
        self.socket.sendall(('GET / HTTP/1.1\r\nHost: 127.0.0.1:'+str(port)+'\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: '+key+'\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        response=b''
        while b'\r\n\r\n' not in response:
            chunk=self.socket.recv(4096)
            if not chunk:raise ConnectionError('WebSocket handshake closed')
            response+=chunk
            if len(response)>65536:raise ValueError('Oversized handshake')
        headers,self.buffer=response.split(b'\r\n\r\n',1)
        expected=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
        if b' 101 ' not in headers.split(b'\r\n',1)[0] or expected.lower() not in headers.lower():raise ConnectionError('Invalid WebSocket handshake')
        self.socket.settimeout(1)
    def frame(self,data,opcode=1):
        mask=os.urandom(4);n=len(data);header=bytes([0x80|opcode])
        header+=bytes([0x80|n]) if n<126 else bytes([0xfe])+struct.pack('!H',n) if n<65536 else bytes([0xff])+struct.pack('!Q',n)
        self.socket.sendall(header+mask+bytes(b^mask[i%4] for i,b in enumerate(data)))
    def send(self,data):self.frame(json.dumps(data,separators=(',',':')).encode())
    def receive(self,timeout=.05):
        if select.select([self.socket],[],[],timeout)[0]:
            part=self.socket.recv(65536)
            if not part:raise ConnectionError('StreamDock closed')
            self.buffer+=part
        result=[]
        while len(self.buffer)>=2:
            b1,b2=self.buffer[:2];n=b2&127;offset=2
            if n==126:
                if len(self.buffer)<4:break
                n=struct.unpack_from('!H',self.buffer,2)[0];offset=4
            elif n==127:
                if len(self.buffer)<10:break
                n=struct.unpack_from('!Q',self.buffer,2)[0];offset=10
            if n>4*1024*1024:raise ValueError('Oversized WebSocket message')
            mask_len=4 if b2&128 else 0
            if len(self.buffer)<offset+mask_len+n:break
            mask=self.buffer[offset:offset+mask_len];offset+=mask_len
            data=self.buffer[offset:offset+n];self.buffer=self.buffer[offset+n:]
            if mask_len:data=bytes(v^mask[i%4] for i,v in enumerate(data))
            op=b1&15
            if op==8:raise ConnectionError('StreamDock closed')
            if op==9:self.frame(data,10);continue
            if op==10:continue
            if op==1:self.parts=data
            elif op==0:self.parts+=data
            else:continue
            if len(self.parts)>4*1024*1024:raise ValueError('Oversized fragmented message')
            if b1&128:result.append(json.loads(self.parts));self.parts=b''
        return result
