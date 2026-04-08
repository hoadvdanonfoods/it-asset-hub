import platform
import subprocess
import socket
from concurrent.futures import ThreadPoolExecutor

def is_up(ip: str) -> bool:
    """Ping an IP to check if it's up."""
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    timeout_param = '-w' if platform.system().lower() == 'windows' else '-W'
    command = ['ping', param, '1', timeout_param, '1000' if param == '-n' else '1', ip]
    try:
        output = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output.returncode == 0
    except Exception:
        return False

def get_hostname(ip: str) -> str:
    """Try to resolve hostname of the IP."""
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ""

def scan_ip(ip: str) -> dict | None:
    if is_up(ip):
        hostname = get_hostname(ip)
        return {"ip": ip, "hostname": hostname or f"Unknown-{ip.replace('.', '-')}", "status": "active"}
    return None

def scan_network(ip_list: list[str]) -> list[dict]:
    results = []
    # Use max_workers=50 to ping 50 IPs concurrently for speed
    with ThreadPoolExecutor(max_workers=50) as executor:
        for result in executor.map(scan_ip, ip_list):
            if result:
                results.append(result)
    return results
