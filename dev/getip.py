# import socket

# try:
#     # This will get the primary network interface's IP
#     local_ip = socket.gethostbyname(socket.gethostname())
# except socket.gaierror:
#     # If there's an error resolving the hostname, use localhost
#     local_ip = "127.0.0.1"

# import os
# f = os.popen('ifconfig eth0 | grep "inet\ addr" | cut -d: -f2 | cut -d" " -f1')
# your_ip=f.read()

# import os
# f = os.popen('ifconfig eth0 | grep "inet\ addr" | cut -d: -f2 | cut -d" " -f1')
# your_ip=f.read()

# print ("Local IP: %s" % your_ip)


import netifaces as ni

def get_interface_ip(interface_name):
    try:
        interface_addresses = ni.ifaddresses(interface_name)
        ip_address = interface_addresses[ni.AF_INET][0]['addr']
        return ip_address
    except (KeyError, ValueError, IndexError):
        return None

# Try to get the Ethernet IP first
ethernet_ip = get_interface_ip('eth0')

# If Ethernet IP is not found, try to get the WiFi IP
if ethernet_ip is None:
    wifi_ip = get_interface_ip('wlan0')
    if wifi_ip:
        print(f"WiFi IP: {wifi_ip}")
    else:
        print("No IP found for Ethernet or WiFi.")
else:
    print(f"Ethernet IP: {ethernet_ip}")

# Optionally, print all interfaces for debugging
print(ni.interfaces())