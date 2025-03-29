import threading

from time import *

def print_numbers():
    for i in range(5):
        print(i)
        sleep(2)

def print_alphabet():
    for letter in "abcdefghijh":
        print(letter)
        sleep(2)


#print_numbers()
#print_alphabet()


thread1 = threading.Thread(target=print_numbers)
thread2 = threading.Thread(target=print_alphabet)

thread1.start()
thread2.start()

thread1.join()
thread2.join()

print("Hello")