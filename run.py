#!/usr/bin/env python3

import json
import os
import argparse

class Subnet:
    def __init__(self, id, net):
        self.id = id
        self.net=net
        self.ifaces=list()
    
class Interface:
    def __init__(self, name, ip, router,subnet):
        self.router=router
        self.name=name
        self.ip=ip
        self.subnet = subnet
        self.net = ""

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return self.name + "@R" + str(self.router.routerId)

class Router:
    default = """
*nat
:OUTPUT ACCEPT [0:0]
:PREROUTING ACCEPT [0:0]
:POSTROUTING ACCEPT [0:0]
COMMIT
"""
    filter_head = """*filter
:INPUT DROP [0:0]
:OUTPUT DROP [0:0]
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

    def addInterface(self, iface, ip, subnet):
        self.interfaces[iface] = Interface(iface, ip, self, subnet)
        return self.interfaces[iface]

print("ARGS ....")
parser = argparse.ArgumentParser()
parser.add_argument("-i", type=str, help="(optional, default = inputs/)")
parser.add_argument("-o", type=str, help="(optional, default = outputs/)")
args = parser.parse_args()

def dfs(subnets, src, dst, pos, orig):
    for netif in subnets[pos].ifaces:
        if netif.router.routerId == orig:
            continue
        for _,routif in netif.router.interfaces.items():
            if routif.subnet == subnets[dst]:
                return [(netif, routif)]
            if not routif.subnet == subnets[pos]:
                k = dfs(subnets, src, dst, routif.subnet.id, netif.router.routerId)
                if k:
                    return [(netif, routif), *k]
    return None

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
    for subnet in case['network']['subnets']:
        subnets[subnet['id']] = Subnet(subnet['id'], subnet['address']+'/'+str(subnet['prefix']))
    for link in case['network']['links']:
        iface = routers[link['routerId']].addInterface(link['interfaceId'], link['ip'], subnets[link['subnetId']])
        subnets[link['subnetId']].ifaces.append(iface)

    for com in case['communications']: 
        s_net = subnets[com['sourceSubnetId']].net
        d_net = subnets[com['targetSubnetId']].net
        if com['protocol'] == 'icmp':
            tpl = " -s " + s_net + " -d " + d_net
            tpl_ret = " -d " + s_net + " -s " + d_net
            contrack=""
            contrack_ret=""
        else:
            tpl = \
                " --sport " + str(com['sourcePortStart']) + ":" + str(com['sourcePortEnd']) + \
                " --dport " + str(com['targetPortStart']) + ":" + str(com['targetPortEnd']) + \
                " -s " + s_net + " -d " + d_net
            tpl_ret = \
                " --dport " + str(com['sourcePortStart']) + ":" + str(com['sourcePortEnd']) + \
                " --sport " + str(com['targetPortStart']) + ":" + str(com['targetPortEnd']) + \
                " -d " + s_net + " -s " + d_net
            contrack=" -m state --state NEW,ESTABLISHED "
            contrack_ret=" -m state --state ESTABLISHED "

        print('----------')
        print(fil)
        path = dfs(subnets, com['sourceSubnetId'], com['targetSubnetId'], com['sourceSubnetId'], -1)
        print('=----------')
        print(path)

        for (sif, dif) in path:
            r = sif.router
            r.raw_head += \
                "-A PREROUTING -p " + com['protocol'] + tpl + \
                " -o " + dif.name + " -i" + sif.name +\
                " -j ACCEPT\n"
            r.raw_head += \
                "-A PREROUTING -p " + com['protocol'] + tpl_ret + \
                " -i " + dif.name + " -o " + sif.name + \
                " -j ACCEPT\n"
            r.filter_head += \
                "-A FORWARD -p " + com['protocol'] +  tpl +\
                " -o " + dif.name + " -i " + sif.name + \
                contrack + \
                " -j ACCEPT\n"
            if com['protocol'] != "udp" or com['direction'] == "bidirectional":
                r.filter_head += \
                    "-A FORWARD -p " + com['protocol'] +  tpl_ret +\
                    " -i " + dif.name + " -o " + sif.name + \
                    contrack_ret + \
                    " -j ACCEPT\n"

    os.makedirs(OUTPUT_DIR+'/'+fil[0:-5])
    for r in routers:
        with open(OUTPUT_DIR+'/'+fil[0:-5]+"/"+str(routers[r].routerId), 'w+') as f:
            f.write(routers[r].default)
            f.write(routers[r].filter_head)
            f.write(routers[r].filter_foot)
            f.write(routers[r].raw_head)
            f.write(routers[r].raw_foot)
