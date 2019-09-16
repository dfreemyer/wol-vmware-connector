#!/usr/bin/env python

from settings import *
from pprint import pprint
import requests
import json
import re
import socket
import sys
import logging
import os

from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

VCAPI_SESSION=requests.Session()
VCAPI_SESSION.verify = False

# https://regex101.com/r/2l8eJp/3
DGRAM_REGEX = re.compile(r'(?:^([fF]{12})(([0-9a-fA-F]{12}){16})([0-9a-fA-F]{12})?$)')

def start_vcapi_session():
    response = VCAPI_SESSION.post('https://' + VCENTER_ADDRESS + '/rest/com/vmware/cis/session',auth=(VCENTER_USER,VCENTER_PASS))
    if response.status_code is 200:
        return True
    else:
        logger.error("VCAPI login failed, check your credentials")
        return False

def get_list_of_guests():
    response = VCAPI_SESSION.get('https://' + VCENTER_ADDRESS + '/rest/vcenter/vm')
    vms_json = json.loads(response.text)
    return vms_json["value"]

def guest_has_mac(vmid, mac_addr):
    response = VCAPI_SESSION.get('https://' + VCENTER_ADDRESS + '/rest/vcenter/vm/' + vmid + '/hardware/ethernet')
    nic_json = json.loads(response.text)
    has_mac = False
    for nic in nic_json["value"]:
        mac_response = VCAPI_SESSION.get('https://' + VCENTER_ADDRESS + '/rest/vcenter/vm/' + vmid + '/hardware/ethernet/'+ nic["nic"])
        mac_json = json.loads(mac_response.text)
        mac_value = mac_json["value"]
        this_mac = mac_value["mac_address"].replace(':', '')
        if this_mac == mac_addr:
            has_mac = True
    return has_mac

def power_on_guest(vmid):
    logger.debug("Powering on Guest " + vmid)
    response = VCAPI_SESSION.post('https://' + VCENTER_ADDRESS + '/rest/vcenter/vm/' + vmid + '/power/start')
    if response.status_code == 200:
        logger.info("Guest Powered On Successfully")
    else:
        logger.info("Guest Power-On Failed")

def handle_packet(data):
    payload = bytes.hex(data)
    logger.debug("Received payload: %s" % payload)
    if DGRAM_REGEX.match(payload):
        search = DGRAM_REGEX.search(payload)
        address = search.group(3)
        logger.debug("Forwarding the packet for %s" % (address))
        if start_vcapi_session():
            # Session Started, Lets search the VMs
            guests = get_list_of_guests()
            for guest in guests:
                if guest_has_mac(guest["vm"], address):
                    power_on_guest(guest["vm"])
                    break;
    else:
        logger.debug("Received payload is not valid, ignoring...")



def start_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((BIND_ADDRESS, BIND_PORT))
    while True:
        data, addr = sock.recvfrom(108)
        logger.debug("Received packet from %s:%s" % (addr[0], addr[1]))
        handle_packet(data)


if __name__ == '__main__':
    logFormatter = logging.Formatter("%(asctime)s [%(levelname)s] - %(message)s")
    logger = logging.getLogger()
    logger.setLevel(LOG_LEVEL)

    path = os.path.dirname(os.path.realpath(__file__))
    file = os.path.join(path, "app.log")

    fileHandler = logging.FileHandler(file)
    fileHandler.setFormatter(logFormatter)
    logger.addHandler(fileHandler)

    consoleHandler = logging.StreamHandler(sys.stdout)
    consoleHandler.setFormatter(logFormatter)
    logger.addHandler(consoleHandler)

    try:
        logger.debug("The application has now started listening for packets")
        start_listener()
    except KeyboardInterrupt:
        logger.debug("Exiting because of keyboard interrupt")
        sys.exit()
