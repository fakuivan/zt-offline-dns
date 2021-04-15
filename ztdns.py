#!/usr/bin/env python3.9
from typing import Any, Callable, Dict, Iterable, Iterator, List, NamedTuple, Tuple, Union
from utils import casted_from_json_obj, unpack_exactly, feeder
from itertools import chain
from zt_utils import ZtAddress, ZtNetworkAddress, mk6plane, mkrfc4193
from ipaddress import ip_address, IPv4Address, IPv6Address
from pathlib import Path
from typeguard import typechecked
import json
import argh
import subprocess
import json
from jinja2 import Template
ichain = chain.from_iterable

IPAddress = Union[IPv4Address, IPv6Address]

ZtAddressesResolver = Callable[[Iterable[ZtAddress]], Iterator[List[IPAddress]]]
ZtAddressResolver = Callable[[ZtAddress], List[IPAddress]]

def parse_any_address(resolver: ZtAddressResolver, address: str) -> List[IPAddress]:
    try:
        casted = ZtAddress(address)
    except ValueError:
        return [ip_address(address)]
    return resolver(casted)


class ConfigDNS(NamedTuple):
    domain: str
    servers: List[IPAddress]

    @classmethod
    def from_json_obj(cls, obj: Dict[str, Any], resolver: ZtAddressResolver) -> 'ConfigDNS':
        parse_addr = lambda addr: parse_any_address(resolver, addr)
        domain, raw_servers = casted_from_json_obj(
            list(unpack_exactly(obj, 'domain', 'servers')),
            Tuple[str, List[str]]
        )
        return cls(domain, [*ichain(map(parse_addr, raw_servers))])


class Config(NamedTuple):
    zt_hosts: Dict[ZtAddress, List[str]]
    dns: ConfigDNS
    
    def iter_hosts(self, resolver: ZtAddressResolver
    ) -> Iterator[Tuple[List[IPAddress], List[str]]]:
        for k, v in self.zt_hosts.items():
            yield (resolver(k), v)
    
    @classmethod
    def from_json_obj(cls, obj: Dict[str, Any], resolver: ZtAddressResolver) -> 'Config':
        raw_hosts, raw_dns = unpack_exactly(obj, 'zt_hosts', 'dns')
        zt_hosts = casted_from_json_obj(raw_hosts, Dict[str, List[str]])
        return cls(
            zt_hosts={ZtAddress(k): v for k, v in zt_hosts.items()},
            dns=ConfigDNS.from_json_obj(raw_dns, resolver))


class ControllerCommand(NamedTuple):
    command: Tuple[str, ...]
    
    def call(self, *args: str):
        return json.loads(subprocess.run(
            self.command + args,
            capture_output=True, text=True
            ).stdout)

    def get_networks(self) -> List['ControllerNetworkCommand']:
        networks = casted_from_json_obj(
            self.call('get_networks'), List[str])
        return [ControllerNetworkCommand(
            self, ZtNetworkAddress(net)) for net in networks]


class ControllerNetworkCommand(NamedTuple):
    command: ControllerCommand
    nwid: ZtNetworkAddress
    
    def call(self, *args: str):
        return self.command.call('with_network', str(self.nwid), *args)

    def get_memebers_ips(self, members: Iterable[ZtAddress]
    ) -> Iterator[List[IPAddress]]:
        sixplane, rfc4193 = casted_from_json_obj(
            [*unpack_exactly(self.call('get_pa_modes'), '6plane', 'rfc4193')],
            Tuple[bool, bool])
        for addr in members:
            pa_addresses = (
                [mk6plane(self.nwid, addr)[2]] if sixplane else []) + (
                [mkrfc4193(self.nwid, addr)[1]] if rfc4193 else [])
            
            ips = casted_from_json_obj(
                self.call('get_member_ips', str(addr)),
                List[str])
            
            yield [*map(ip_address, ips)] + pa_addresses

    def set_dns_params(self, domain: str, servers: List[IPAddress]):
        self.call('set_dns_params', domain, *map(str, servers))


@argh.arg('template', help="Path to the jinja2 template for DNS server config", type=Path)
@argh.arg('config_dir', help="Path to the directory with config files for networks", type=Path)
@argh.arg('output_dir', help="Directory to drop the generated config files", type=Path)
@argh.arg('controller_command', nargs = '+',
          help="Command and args used to query and set controller config")
@typechecked
def main(template: Path, config_dir: Path,
         output_dir: Path, controller_command: List[str]):
    """Configure a DNS server for a ZeroTier network"""
    controller_cmd = ControllerCommand((*controller_command,))
    with open(template, 'r') as file:
        template_ = Template(file.read())
    for network in controller_cmd.get_networks():
        resolver = feeder(network.get_memebers_ips)
        config_file = config_dir / (str(network.nwid) + '.json')
        if not config_file.exists():
            continue
        with open(config_file, 'r') as file:
            config = Config.from_json_obj(json.load(file), resolver)
        net_output_dir = output_dir / str(network.nwid)
        net_output_dir.mkdir(parents=True)
        output_file = net_output_dir / (
            template.stem if template.suffix == '.jinja2' else template.name)
        with open(output_file, 'x') as file:
            file.write(template_.render(config=config, resolver=resolver))
        network.set_dns_params(config.dns.domain, config.dns.servers)

if __name__ == '__main__':
    argh.dispatch_command(main)
