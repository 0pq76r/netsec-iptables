#!/usr/bin/env python3

import json
import os
import argparse

class Interface:
    def __init__(self, name, ip):
        self.ifname=name
        self.ip=ip
    

class Router:
    nat_head = """
*nat
:OUTPUT ACCEPT [0:0]
:PREROUTING ACCEPT [0:0]
:POSTROUTING ACCEPT [0:0]
"""
    nat_foot = """
COMMIT
"""
    filter_head = """
*filter
:OUTPUT DROP [0:0]
:INPUT DROP [0:0]
:FORWARD DROP [0:0]
"""
    filter_foot = """
COMMIT
"""
    raw_head = """
*raw
:OUTPUT ACCEPT [0:0]
:PREROUTING DROP [0:0]
"""
    raw_foot = """
COMMIT
"""
    
    def __init__(self, routerId):
        self.routerId = routerId
        self.interfaces = dict()

    def addInterface(self, ifId, ip):
        self.interfaces[ifId] = Interface(ifId, ip)
        return self.interfaces[ifId]

print("ARGS ....")
parser = argparse.ArgumentParser()
parser.add_argument("-i", type=str, help="(optional, default = inputs/)")
parser.add_argument("-o", type=str, help="(optional, default = outputs/)")
args = parser.parse_args()

if args.i:
    INPUT_DIR = args.i
else:
    INPUT_DIR = 'inputs/'
if args.o:
    OUTPUT_DIR = args.o
else:
    OUTPUT_DIR = 'outputs/'

try:
    os.system("rm -rf "+OUTPUT_DIR)
except:
    pass

FILES = os.listdir(INPUT_DIR)

for fil in filter(lambda x: ".json" in x, FILES):
    routers=dict();
    subnets=dict();
    with open(INPUT_DIR+fil) as f:
        case=json.loads(f.read())
    for router in case['network']['routers']:
        routers[router['id']]=Router(router['id'])
    for link in case['network']['links']:
        intf = routers[link['routerId']].addInterface(link['interfaceId'], link['ip'])
        subnets[link['subnetId']] = (routers[link['routerId']], intf, '')
    for subnet in case['network']['subnets']:
        subnets[subnet['id']] = (subnets[subnet['id']][0],subnets[subnet['id']][1],subnet['address']+'/'+str(subnet['prefix']))

    for com in case['communications']:
        (s_router, s_intrf, s_net) = subnets[com['sourceSubnetId']]
        (d_router, d_intrf, d_net) = subnets[com['targetSubnetId']]
        # forward, postrouting
        s_router.raw_head += \
            "-A PREROUTING -p " + com['protocol'] + \
            " --sport " + str(com['sourcePortStart']) + ":" + str(com['sourcePortEnd']) + \
            " --dport " + str(com['targetPortStart']) + ":" + str(com['targetPortEnd']) + \
            " -s " + s_net + " -d " + d_net + " -i " + s_intrf.ifname + \
            " -j ACCEPT\n"
        s_router.filter_head += \
            "-A FORWARD -p " + com['protocol'] + \
            " --sport " + str(com['sourcePortStart']) + ":" + str(com['sourcePortEnd']) + \
            " --dport " + str(com['targetPortStart']) + ":" + str(com['targetPortEnd']) + \
            " -s " + s_net + " -d " + d_net + " -i " + s_intrf.ifname + " -o " + d_intrf.ifname + \
            " -m state --state NEW,ESTABLISHED -j ACCEPT\n"
        s_router.filter_head += \
            "-A OUTPUT -p " + com['protocol'] + \
            " --sport " + str(com['sourcePortStart']) + ":" + str(com['sourcePortEnd']) + \
            " --dport " + str(com['targetPortStart']) + ":" + str(com['targetPortEnd']) + \
            " -s " + s_net + " -d " + d_net + " -o " + d_intrf.ifname + \
            " -m state --state NEW,ESTABLISHED -j ACCEPT\n"
        s_router.filter_head += \
            "-A FORWARD -p " + com['protocol'] + \
            " --dport " + str(com['sourcePortStart']) + ":" + str(com['sourcePortEnd']) + \
            " --sport " + str(com['targetPortStart']) + ":" + str(com['targetPortEnd']) + \
            " -d " + s_net + " -s " + d_net + " -o " + s_intrf.ifname + " -i " + d_intrf.ifname + \
            " -m state --state ESTABLISHED -j ACCEPT\n"
        s_router.filter_head += \
            "-A INPUT -p " + com['protocol'] + \
            " --dport " + str(com['sourcePortStart']) + ":" + str(com['sourcePortEnd']) + \
            " --sport " + str(com['targetPortStart']) + ":" + str(com['targetPortEnd']) + \
            " -d " + s_net + " -s " + d_net +  " -i " + d_intrf.ifname + \
            " -m state --state ESTABLISHED -j ACCEPT\n"

    os.makedirs(OUTPUT_DIR+'/'+fil[0:-5])
    for r in routers:
        with open(OUTPUT_DIR+'/'+fil[0:-5]+"/"+str(routers[r].routerId), 'w+') as f:
            f.write(routers[r].nat_head)
            f.write(routers[r].nat_foot)
            f.write(routers[r].filter_head)
            f.write(routers[r].filter_foot)
            f.write(routers[r].raw_head)
            f.write(routers[r].raw_foot)
