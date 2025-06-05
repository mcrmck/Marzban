import ipaddress
import math
import secrets
import socket
import time
from dataclasses import dataclass
import platform
import psutil
import logging
from typing import Optional

import requests

logger = logging.getLogger("marzban")


@dataclass
class MemoryStat():
    total: int
    used: int
    free: int


@dataclass
class CPUStat():
    cores: int
    percent: float


def cpu_usage() -> CPUStat:
    return CPUStat(cores=psutil.cpu_count(), percent=psutil.cpu_percent())


def memory_usage() -> MemoryStat:
    mem = psutil.virtual_memory()
    return MemoryStat(total=mem.total, used=mem.used, free=mem.available)


@dataclass
class RealtimeBandwidth:
    def __post_init__(self):
        io = psutil.net_io_counters()
        self.bytes_recv = io.bytes_recv
        self.bytes_sent = io.bytes_sent
        self.packets_recv = io.packets_recv
        self.packets_sent = io.packets_sent
        self.last_perf_counter = time.perf_counter()

    # data in the form of value per seconds
    incoming_bytes: int
    outgoing_bytes: int
    incoming_packets: int
    outgoing_packets: int

    bytes_recv: int = None
    bytes_sent: int = None
    packets_recv: int = None
    packets_sent: int = None
    last_perf_counter: float = None


@dataclass
class RealtimeBandwidthStat:
    """Real-Time bandwith in value/s unit"""

    incoming_bytes: int
    outgoing_bytes: int
    incoming_packets: int
    outgoing_packets: int


rt_bw = RealtimeBandwidth(
    incoming_bytes=0, outgoing_bytes=0, incoming_packets=0, outgoing_packets=0)


# sample time is 2 seconds, values lower than this may not produce good results
def record_realtime_bandwidth() -> None:
    global rt_bw
    last_perf_counter = rt_bw.last_perf_counter
    io = psutil.net_io_counters()
    rt_bw.last_perf_counter = time.perf_counter()
    sample_time = rt_bw.last_perf_counter - last_perf_counter
    rt_bw.incoming_bytes, rt_bw.bytes_recv = round((io.bytes_recv - rt_bw.bytes_recv) / sample_time), io.bytes_recv
    rt_bw.outgoing_bytes, rt_bw.bytes_sent = round((io.bytes_sent - rt_bw.bytes_sent) / sample_time), io.bytes_sent
    rt_bw.incoming_packets, rt_bw.packets_recv = round((io.packets_recv - rt_bw.packets_recv) / sample_time), io.packets_recv
    rt_bw.outgoing_packets, rt_bw.packets_sent = round((io.packets_sent - rt_bw.packets_sent) / sample_time), io.packets_sent


def realtime_bandwidth() -> RealtimeBandwidthStat:
    return RealtimeBandwidthStat(
        incoming_bytes=rt_bw.incoming_bytes,
        outgoing_bytes=rt_bw.outgoing_bytes,
        incoming_packets=rt_bw.incoming_packets,
        outgoing_packets=rt_bw.outgoing_packets,
    )


def random_password() -> str:
    return secrets.token_urlsafe(16)


def check_port(port: int) -> bool:
    """Check if a port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('', port))
            return True
        except OSError:
            return False


def get_public_ip():
    try:
        resp = requests.get('http://api4.ipify.org/', timeout=5).text.strip()
        if ipaddress.IPv4Address(resp).is_global:
            return resp
    except:
        pass

    try:
        resp = requests.get('http://ipv4.icanhazip.com/', timeout=5).text.strip()
        if ipaddress.IPv4Address(resp).is_global:
            return resp
    except:
        pass

    try:
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        resp = requests.get('https://ifconfig.io/ip', timeout=5).text.strip()
        if ipaddress.IPv4Address(resp).is_global:
            return resp
    except requests.exceptions.RequestException:
        pass
    finally:
        requests.packages.urllib3.util.connection.HAS_IPV6 = True

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(('8.8.8.8', 80))
        resp = sock.getsockname()[0]
        if ipaddress.IPv4Address(resp).is_global:
            return resp
    except (socket.error, IndexError):
        pass
    finally:
        sock.close()

    return '127.0.0.1'


def get_public_ipv6():
    try:
        resp = requests.get('http://api6.ipify.org/', timeout=5).text.strip()
        if ipaddress.IPv6Address(resp).is_global:
            return '[%s]' % resp
    except:
        pass

    try:
        resp = requests.get('http://ipv6.icanhazip.com/', timeout=5).text.strip()
        if ipaddress.IPv6Address(resp).is_global:
            return '[%s]' % resp
    except:
        pass

    return '[::1]'


def readable_size(size_bytes):
    if size_bytes <= 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f'{s} {size_name[i]}'


def get_system_info() -> dict:
    """Get system information."""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return {
            "cpu_usage": cpu_percent,
            "memory_usage": memory.percent,
            "disk_usage": disk.percent,
            "platform": platform.platform(),
            "python_version": platform.python_version()
        }
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return {
            "error": str(e),
            "platform": platform.platform(),
            "python_version": platform.python_version()
        }


def get_process_info(pid: int) -> Optional[dict]:
    """Get information about a process."""
    try:
        process = psutil.Process(pid)
        return {
            "pid": process.pid,
            "name": process.name(),
            "status": process.status(),
            "cpu_percent": process.cpu_percent(),
            "memory_percent": process.memory_percent(),
            "create_time": process.create_time()
        }
    except psutil.NoSuchProcess:
        return None
    except Exception as e:
        logger.error(f"Error getting process info: {e}")
        return None


def get_network_info() -> dict:
    """Get network interface information."""
    try:
        interfaces = {}
        for interface, addrs in psutil.net_if_addrs().items():
            interfaces[interface] = {
                "addresses": [addr.address for addr in addrs if addr.family == socket.AF_INET],
                "netmasks": [addr.netmask for addr in addrs if addr.family == socket.AF_INET],
                "broadcasts": [addr.broadcast for addr in addrs if addr.family == socket.AF_INET]
            }
        return interfaces
    except Exception as e:
        logger.error(f"Error getting network info: {e}")
        return {}




def get_network_io() -> dict:
    """Get network I/O statistics."""
    try:
        io_counters = psutil.net_io_counters()
        return {
            "bytes_sent": io_counters.bytes_sent,
            "bytes_recv": io_counters.bytes_recv,
            "packets_sent": io_counters.packets_sent,
            "packets_recv": io_counters.packets_recv
        }
    except Exception as e:
        logger.error(f"Error getting network I/O info: {e}")
        return {}
