import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
result = sock.connect_ex(('127.0.0.1', 9092))
if result == 0:
   print("Cổng 9092 đang MỞ. Kafka đã sẵn sàng!")
else:
   print("Cổng 9092 đang ĐÓNG. Kiểm tra lại Docker nhé.")
sock.close()