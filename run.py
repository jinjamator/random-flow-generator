#!/usr/bin/env -S jinjamator -vvv -t
from simplenetlink import SimpleNetlink
from pyperf2 import Server, Client
import random
from time import sleep
from pprint import pformat

streams = {}
ip = SimpleNetlink()

log.info(f"preparing {stream_count} streams")
available_stream_ports = list(range(stream_port_min, stream_port_max + 1))

for base_int in sender_base_interfaces + receiver_base_interfaces:
    self._log.info(f'setup: ensure base interface {base_int} is up')
    ip.ensure_interface_exists(base_int,state='up')

def allocate_stream(stream_id):
    stream_config = {
        "id": stream_id,
        "receiver_prefix": random.choice(receiver_prefixes),
        "sender_prefix": random.choice(sender_prefixes),
        "protocol": random.choice(stream_protocols),
        "port": random.choice(available_stream_ports),
        "receiver_namespace": f"{namespace_prefix}{stream_id}_rx",
        "sender_namespace": f"{namespace_prefix}{stream_id}_tx",
        "stream_duration": random.choice(
            range(stream_duration_min, stream_duration_max + 1)
        ),
        "stream_pause": random.choice(range(stream_pause_min, stream_pause_max + 1)),
        "stream_restarts": random.choice(
            range(stream_restarts_min, stream_restarts_max + 1)
        ),
        "sender_base_interface": random.choice(sender_base_interfaces),
        "receiver_base_interface": random.choice(receiver_base_interfaces),
        "time_until_restart": None,
        "restart_count": 0,
    }
    receiver_prefixes.remove(stream_config["receiver_prefix"])
    sender_prefixes.remove(stream_config["sender_prefix"])
    available_stream_ports.remove(stream_config["port"])
    return stream_config


def maintain_stream(stream_id):
    log.info(f"{stream_id}: maintaining stream")
    if stream_id not in streams:
        log.info(f"{stream_id}: stream is not allocated -> allocating")
        streams[stream_id] = {
            "configuration": allocate_stream(stream_id),
            "instances": {"rx": None, "tx": None},
        }
        log.info(f"{stream_id}: allocated new stream configuration:\n{pformat(streams[stream_id]['configuration'])}")
        server_ip=streams[stream_id]["configuration"]["receiver_prefix"].split('/')[0]
    if not streams[stream_id]["instances"]["rx"]:
        log.info(f"{stream_id}: no rx instance on stream  -> creating")
        ip.ensure_interface_exists(
            f"iperf_{stream_id}_rx",
            namespace=streams[stream_id]["configuration"]["receiver_namespace"],
            link_state="up",
            parent_interface=streams[stream_id]["configuration"][
                "receiver_base_interface"
            ],
            type="ipvlan",
            ipv4=[streams[stream_id]["configuration"]["receiver_prefix"]],
        )
        ip.add_route("0.0.0.0/0", receiver_default_gateway)
        streams[stream_id]["instances"]["rx"] = Server()
        streams[stream_id]["instances"]["rx"].set_options(
            protocol=streams[stream_id]["configuration"]["protocol"], 
            server_ip=server_ip, 
            test_duration=streams[stream_id]["configuration"]["stream_duration"] + 1, # give receiver an extra second
            use_linux_namespace=streams[stream_id]["configuration"]["receiver_namespace"],
            port=streams[stream_id]["configuration"]["port"]
        )
    if not streams[stream_id]["instances"]["tx"]:
        log.info(f"no tx instance on stream {stream_id} -> creating")
        ip.ensure_interface_exists(
            f"iperf_{stream_id}_tx",
            namespace=streams[stream_id]["configuration"]["sender_namespace"],
            link_state="up",
            parent_interface=streams[stream_id]["configuration"][
                "sender_base_interface"
            ],
            type="ipvlan",
            ipv4=[streams[stream_id]["configuration"]["sender_prefix"]],
        )
        ip.add_route("0.0.0.0/0", sender_default_gateway)
        streams[stream_id]["instances"]["tx"] = Client()
        streams[stream_id]["instances"]["tx"].set_options(
            protocol=streams[stream_id]["configuration"]["protocol"], 
            test_duration=streams[stream_id]["configuration"]["stream_duration"],
            server_ip=server_ip,
            use_linux_namespace=streams[stream_id]["configuration"]["sender_namespace"],
            port=streams[stream_id]["configuration"]["port"]

        )
    if streams[stream_id]["instances"]["tx"].status == 'stopped' and streams[stream_id]["instances"]["rx"].status == 'stopped':
        log.info(f'{stream_id}: both, RX and TX instances are stopped')
        if streams[stream_id]["configuration"]["restart_count"] < streams[stream_id]["configuration"]["stream_restarts"]:
            # reuse this stream
            streams[stream_id]["configuration"]["restart_count"]+=1
            streams[stream_id]["configuration"]["time_until_restart"]=streams[stream_id]["configuration"]["stream_pause"]
        else:
            # decomission this stream and allocate a new one
            # return resources
            log.info(f'{stream_id}: stream is EOL -> decomissioning')
            receiver_prefixes.append(streams[stream_id]["configuration"]['receiver_prefix'])
            sender_prefixes.append(streams[stream_id]["configuration"]['sender_prefix'])
            available_stream_ports.append(streams[stream_id]["configuration"]['port'])
            ip.set_current_namespace(streams[stream_id]["configuration"]['receiver_namespace'])
            ip.interface_delete_ipv4( f"iperf_{stream_id}_rx",streams[stream_id]["configuration"]['receiver_prefix'])
            ip.set_current_namespace(streams[stream_id]["configuration"]['sender_namespace'])
            ip.interface_delete_ipv4( f"iperf_{stream_id}_tx",streams[stream_id]["configuration"]['sender_prefix'])
            # ip.delete_namespace(streams[stream_id]["configuration"]['receiver_namespace'])
            # ip.delete_namespace(streams[stream_id]["configuration"]['sender_namespace'])
            del streams[stream_id]
            return None

  
    if streams[stream_id]["instances"]["tx"].status != 'running' and streams[stream_id]["instances"]["rx"].status != 'running':
        log.info(f'{stream_id}: both, RX and TX instances for stream not running')
        
        if not streams[stream_id]["configuration"]["time_until_restart"]:
            self._log.info(f'{stream_id}: starting')
            streams[stream_id]["instances"]["rx"].start()
            streams[stream_id]["instances"]["tx"].start()
        else:
            self._log.info(f'{stream_id}: waiting for {streams[stream_id]["configuration"]["time_until_restart"]}s')
            streams[stream_id]["configuration"]["time_until_restart"]-=1



while True:
    for stream_id in range(1, stream_count + 1):
        maintain_stream(stream_id)
    sleep(1)
# ip.ensure_interface_exists("iperf_", namespace='test', link_state='up', parent_interface='eth0', type='ipvlan',  ipv4=['100.64.0.11/24'])

def cleanup():
    for ns in self.get_namespaces():
        log.info('cleanup:removing namespace {ns}')
        ip.delete_namespace(ns)

import atexit
atexit.register(cleanup)
