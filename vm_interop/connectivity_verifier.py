"""
Connectivity Verifier module for testing ping, SSH, and port reachability between VMs.
"""

import subprocess
import threading
import platform

class ConnectivityVerifier:
    def __init__(self):
        """Initialize ConnectivityVerifier."""
        pass

    def ping_vm(self, ip, timeout=2):
        try:
            if platform.system() == 'Darwin':
                # macOS: no -W flag, just use -c 1
                result = subprocess.run(['ping', '-c', '1', ip], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            else:
                # Linux: use -W for timeout
                result = subprocess.run(['ping', '-c', '1', '-W', str(timeout), ip], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                return True, "Ping successful"
            else:
                return False, result.stderr.strip() or result.stdout.strip() or "Ping failed"
        except Exception as e:
            return False, str(e)

    def ping_vm_threaded(self, ip, callback, timeout=2):
        def worker():
            success, msg = self.ping_vm(ip, timeout)
            callback(success, msg)
        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def check_ssh(self, source_vm_id, target_ip):
        """Check SSH connectivity between VMs."""
        pass

    def check_port(self, source_vm_id, target_ip, port):
        """Check if a port is reachable between VMs."""
        pass 