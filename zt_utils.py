#!/usr/bin/env python3.9
from utils import only_contains
from ipaddress import IPv6Network, IPv6Address
from typing import Tuple

"""
Utility functions for configuring ZeroTier
"""

class ZtAddress(int):
    def __new__(cls, address: str) -> 'ZtAddress':
        if len(address) != 10 or not only_contains(address, set('0123456789abcdefABCDEF')):
            raise ValueError("Node Address must be a 10 digit hexadecimal number")
        return super().__new__(cls, int(address, 16))
    
    def __str__(self) -> str:
        return f"{self:010x}"

    def __repr__(self) -> str:
        return f"ZtAddress('{str(self)}')"

class ZtNetworkAddress(int):
    def __new__(cls, address: str) -> 'ZtNetworkAddress':
        if len(address) != 16 or not only_contains(address, set('0123456789abcdefABCDEF')):
            raise ValueError("Network Address must be a 16 digit hexadecimal number")
        return super().__new__(cls, int(address, 16))

    def __str__(self) -> str:
        return f"{self:016x}"

    def __repr__(self) -> str:
        return f"ZtNetworkAddress('{str(self)}')"

def mk6plane(nwid: ZtNetworkAddress, nodeid: ZtAddress
) -> Tuple[IPv6Network, IPv6Network, IPv6Address]:
    """
    Given a ZeroTier node and network ID, return
    a tuple where the first element is the subnet for the
    whole 6plane network, the second is the subnet 
    assigned to the given node id and the 6plane address
    for that node
    """
    prefix = (nwid ^ (nwid >> 8*4)) & ((1 << 8*4) - 1)
    net = IPv6Network(((0xfc << 8*15) +
                       (prefix << 8*11) +
                       (nodeid << 8*6), 80))
    return net.supernet(new_prefix=40), net, net[1]


def mkrfc4193(nwid: ZtNetworkAddress, nodeid: ZtAddress
) -> Tuple[IPv6Network, IPv6Address]:
    """
    Given a ZeroTier node and network ID, return
    a tuple where the first element is the subnet for the
    whole rfc4193 network, the second is node address on
    that network.
    """
    net = IPv6Network(((0xfd << 8*15) +
                       (nwid << 8*7) +
                       (0x9993 << 8*5), 88))
    return net, net[nodeid]
