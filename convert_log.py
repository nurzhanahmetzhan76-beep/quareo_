import os

with open('c:/Users/user/Desktop/retailpool/server.log', 'rb') as f:
    content = f.read()

text = content.decode('utf-16le', errors='replace')
with open('c:/Users/user/Desktop/retailpool/server_utf8.log', 'w', encoding='utf-8') as f:
    f.write(text[-10000:])
