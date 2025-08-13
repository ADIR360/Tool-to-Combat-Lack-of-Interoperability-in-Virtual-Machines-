"""
VM Manager module for detecting, listing, and controlling VMs across platforms (VMware, VirtualBox, Hyper-V, KVM).
"""

import subprocess
import re
import platform
import socket
import os
import shutil
import plistlib
import json

def detect_environment():
    env = {
        "os": platform.system(),
        "arch": platform.machine(),
        "vbox_available": shutil.which("VBoxManage") is not None,
        "virsh_available": shutil.which("virsh") is not None,
        "qemu_available": shutil.which("qemu-system-x86_64") is not None,
        "vmware_available": shutil.which("vmrun") is not None,
    }
    return env

class VMManager:
    def __init__(self):
        self.env = detect_environment()

    def list_virtualbox_vms(self):
        """List VirtualBox VMs with detailed information."""
        vms = []
        try:
            result = subprocess.run(["VBoxManage", "list", "vms"], capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().splitlines()
                for line in lines:
                    if '"' in line:
                        # Parse "VM Name" {uuid}
                        vm_name = line.split('"')[1]
                        uuid = line.split('{')[1].split('}')[0]
                        
                        # Get detailed VM info
                        vm_info = self.get_virtualbox_vm_info(vm_name)
                        vms.append(vm_info)
        except Exception as e:
            vms.append({"name": "VirtualBox Error", "status": f"Error: {e}", "platform": "VirtualBox"})
        return vms

    def get_virtualbox_vm_info(self, vm_name):
        """Get detailed information about a VirtualBox VM."""
        info = {
            'name': vm_name,
            'status': 'Unknown',
            'platform': 'VirtualBox',
            'os_type': 'Unknown',
            'memory': 'Unknown',
            'cpu_count': 'Unknown',
            'architecture': 'Unknown'
        }
        
        try:
            # Get VM state
            result = subprocess.run(["VBoxManage", "showvminfo", vm_name, "--machinereadable"], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().splitlines()
                for line in lines:
                    if line.startswith('VMState='):
                        state = line.split('=')[1].strip('"')
                        # Map VM states to readable status
                        state_map = {
                            'running': 'Running',
                            'poweroff': 'Stopped',
                            'saved': 'Saved',
                            'paused': 'Paused',
                            'aborted': 'Aborted'
                        }
                        info['status'] = state_map.get(state, state.title())
                    elif line.startswith('memory='):
                        memory_mb = int(line.split('=')[1])
                        info['memory'] = f"{memory_mb} MB"
                    elif line.startswith('cpus='):
                        info['cpu_count'] = line.split('=')[1]
                    elif line.startswith('ostype='):
                        os_type = line.split('=')[1].strip('"')
                        info['os_type'] = os_type
                        # Determine architecture from OS type
                        if '64' in os_type:
                            info['architecture'] = '64-bit'
                        elif '32' in os_type:
                            info['architecture'] = '32-bit'
                        else:
                            info['architecture'] = 'Unknown'
                            
        except Exception as e:
            info['status'] = f"Error: {e}"
            
        return info

    def list_vmware_vms(self):
        """List VMware VMs with detailed information."""
        vms = []
        try:
            # Try to find VMware VMs in common locations
            vmware_paths = [
                os.path.expanduser("~/Documents/Virtual Machines"),
                "/Users/Shared/VMware Fusion",
                "/Applications/VMware Fusion.app/Contents/Library"
            ]
            
            for vmware_path in vmware_paths:
                if os.path.exists(vmware_path):
                    for item in os.listdir(vmware_path):
                        if item.endswith('.vmwarevm') or item.endswith('.vmx'):
                            vm_name = item.replace('.vmwarevm', '').replace('.vmx', '')
                            vm_info = self.get_vmware_vm_info(os.path.join(vmware_path, item))
                            vms.append(vm_info)
                            
        except Exception as e:
            vms.append({"name": "VMware Error", "status": f"Error: {e}", "platform": "VMware"})
        return vms

    def get_vmware_vm_info(self, vm_path):
        """Get detailed information about a VMware VM."""
        info = {
            'name': os.path.basename(vm_path).replace('.vmwarevm', '').replace('.vmx', ''),
            'status': 'Unknown',
            'platform': 'VMware',
            'os_type': 'Unknown',
            'memory': 'Unknown',
            'cpu_count': 'Unknown',
            'architecture': 'Unknown'
        }
        
        try:
            # Try to get VM state using vmrun if available
            if self.env["vmware_available"]:
                result = subprocess.run(["vmrun", "list"], capture_output=True, text=True)
                if result.returncode == 0:
                    running_vms = result.stdout.strip().splitlines()
                    if vm_path in running_vms:
                        info['status'] = 'Running'
                    else:
                        info['status'] = 'Stopped'
            else:
                info['status'] = 'Unknown (vmrun not available)'
                
            # Try to read .vmx file for additional info
            vmx_file = vm_path if vm_path.endswith('.vmx') else os.path.join(vm_path, '*.vmx')
            if os.path.exists(vmx_file):
                try:
                    with open(vmx_file, 'r') as f:
                        content = f.read()
                        # Extract memory size
                        mem_match = re.search(r'memsize\s*=\s*"(\d+)"', content)
                        if mem_match:
                            memory_mb = int(mem_match.group(1))
                            info['memory'] = f"{memory_mb} MB"
                        
                        # Extract CPU count
                        cpu_match = re.search(r'numvcpus\s*=\s*"(\d+)"', content)
                        if cpu_match:
                            info['cpu_count'] = cpu_match.group(1)
                        
                        # Extract guest OS
                        os_match = re.search(r'guestOS\s*=\s*"([^"]+)"', content)
                        if os_match:
                            os_type = os_match.group(1)
                            info['os_type'] = os_type
                            # Determine architecture
                            if '64' in os_type or 'x64' in os_type:
                                info['architecture'] = '64-bit'
                            elif '32' in os_type or 'x86' in os_type:
                                info['architecture'] = '32-bit'
                            else:
                                info['architecture'] = 'Unknown'
                except Exception:
                    pass
                    
        except Exception as e:
            info['status'] = f"Error: {e}"
            
        return info

    def list_kvm_vms(self):
        """List KVM VMs with detailed information."""
        vms = []
        try:
            import libvirt
            conn = libvirt.open("qemu:///system")
            domains = conn.listAllDomains()
            for dom in domains:
                vm_info = self.get_kvm_vm_info(dom)
                vms.append(vm_info)
            conn.close()
        except ImportError:
            vms.append({"name": "KVM Error", "status": "libvirt not installed", "platform": "KVM"})
        except Exception as e:
            vms.append({"name": "KVM Error", "status": str(e), "platform": "KVM"})
        return vms

    def get_kvm_vm_info(self, domain):
        """Get detailed information about a KVM VM."""
        info = {
            'name': domain.name(),
            'status': 'Unknown',
            'platform': 'KVM',
            'os_type': 'Unknown',
            'memory': 'Unknown',
            'cpu_count': 'Unknown',
            'architecture': 'Unknown'
        }
        
        try:
            # Get VM status
            if domain.isActive():
                info['status'] = 'Running'
            else:
                info['status'] = 'Stopped'
            
            # Get VM info
            vm_info = domain.info()
            if vm_info:
                # Memory in KB, convert to MB
                memory_kb = vm_info[2]
                info['memory'] = f"{memory_kb // 1024} MB"
                info['cpu_count'] = str(vm_info[3])
                
            # Try to get OS type from XML description
            try:
                xml_desc = domain.XMLDesc()
                os_match = re.search(r'<os>.*?<type[^>]*>([^<]+)</type>', xml_desc, re.DOTALL)
                if os_match:
                    os_type = os_match.group(1)
                    info['os_type'] = os_type
                    # Determine architecture
                    arch_match = re.search(r'<type[^>]*arch="([^"]+)"', xml_desc)
                    if arch_match:
                        arch = arch_match.group(1)
                        if 'x86_64' in arch or 'amd64' in arch:
                            info['architecture'] = '64-bit'
                        elif 'i386' in arch or 'x86' in arch:
                            info['architecture'] = '32-bit'
                        else:
                            info['architecture'] = arch
            except Exception:
                pass
                
        except Exception as e:
            info['status'] = f"Error: {e}"
            
        return info

    def list_hyperv_vms(self):
        """List Hyper-V VMs with detailed information."""
        vms = []
        try:
            output = subprocess.check_output(
                ["powershell", "-Command", "Get-VM | Select-Object Name, State, ProcessorCount, MemoryStartup | ConvertTo-Json"],
                shell=True
            ).decode()
            
            if output.strip():
                vm_data = json.loads(output)
                if isinstance(vm_data, list):
                    for vm in vm_data:
                        vm_info = {
                            'name': vm.get('Name', 'Unknown'),
                            'status': vm.get('State', 'Unknown'),
                            'platform': 'Hyper-V',
                            'os_type': 'Windows',
                            'memory': f"{vm.get('MemoryStartup', 0) // (1024*1024)} MB",
                            'cpu_count': str(vm.get('ProcessorCount', 0)),
                            'architecture': '64-bit'  # Hyper-V typically runs 64-bit VMs
                        }
                        vms.append(vm_info)
                else:
                    # Single VM
                    vm = vm_data
                    vm_info = {
                        'name': vm.get('Name', 'Unknown'),
                        'status': vm.get('State', 'Unknown'),
                        'platform': 'Hyper-V',
                        'os_type': 'Windows',
                        'memory': f"{vm.get('MemoryStartup', 0) // (1024*1024)} MB",
                        'cpu_count': str(vm.get('ProcessorCount', 0)),
                        'architecture': '64-bit'
                    }
                    vms.append(vm_info)
                    
        except Exception as e:
            vms.append({"name": "Hyper-V Error", "status": f"Error: {e}", "platform": "Hyper-V"})
        return vms

    def list_utm_vms(self):
        """List UTM VMs with detailed information."""
        vms = []
        try:
            utm_dir = os.path.expanduser('~/Library/Containers/com.utmapp.UTM/Data/Documents/')
            if os.path.exists(utm_dir):
                for entry in os.listdir(utm_dir):
                    if entry.endswith('.utm'):
                        utm_path = os.path.join(utm_dir, entry)
                        vm_info = self.get_utm_vm_info(utm_path)
                        vms.append(vm_info)
        except Exception as e:
            vms.append({"name": "UTM Error", "status": f"Error: {e}", "platform": "UTM"})
        return vms

    def get_utm_vm_info(self, utm_path):
        """Get detailed information about a UTM VM."""
        info = {
            'name': os.path.basename(utm_path).replace('.utm', ''),
            'status': 'Unknown (UTM)',
            'platform': 'UTM',
            'os_type': 'Unknown',
            'memory': 'Unknown',
            'cpu_count': 'Unknown',
            'architecture': 'Unknown'
        }
        
        try:
            config_path = os.path.join(utm_path, 'config.plist')
            if os.path.exists(config_path):
                with open(config_path, 'rb') as f:
                    config = plistlib.load(f)
                    
                    # Get basic information
                    if 'Information' in config and 'Name' in config['Information']:
                        info['name'] = config['Information']['Name']
                    
                    # Get system specifications
                    if 'System' in config:
                        system = config['System']
                        if 'MemorySize' in system:
                            memory_mb = system['MemorySize']
                            info['memory'] = f"{memory_mb} MB"
                        if 'CPUCount' in system:
                            info['cpu_count'] = str(system['CPUCount'])
                        if 'Architecture' in system:
                            arch = system['Architecture']
                            info['architecture'] = arch
                            # Map architecture to readable format
                            if arch == 'aarch64':
                                info['architecture'] = '64-bit ARM'
                            elif arch == 'x86_64':
                                info['architecture'] = '64-bit x86'
                            elif arch == 'i386':
                                info['architecture'] = '32-bit x86'
                            else:
                                info['architecture'] = arch
                    
                    # Try to determine OS type from icon or other indicators
                    if 'Information' in config and 'Icon' in config['Information']:
                        icon = config['Information']['Icon']
                        if 'linux' in icon.lower():
                            info['os_type'] = 'Linux'
                        elif 'windows' in icon.lower():
                            info['os_type'] = 'Windows'
                        elif 'mac' in icon.lower():
                            info['os_type'] = 'macOS'
                        else:
                            info['os_type'] = 'Unknown'
                    
                    # Try to determine if VM is running by checking for running processes
                    # This is a basic check - UTM doesn't provide easy status checking
                    try:
                        # Check if there's a QEMU process running for this VM
                        result = subprocess.run(['pgrep', '-f', info['name']], 
                                              capture_output=True, text=True)
                        if result.returncode == 0:
                            info['status'] = 'Running'
                        else:
                            info['status'] = 'Stopped'
                    except Exception:
                        info['status'] = 'Unknown (UTM)'
                    
        except Exception as e:
            info['status'] = f"Error: {e}"
            
        return info

    def list_vms(self):
        """List all available VMs from all platforms."""
        env = self.env
        vms = []
        
        # Add VirtualBox VMs
        if env["vbox_available"]:
            vms.extend(self.list_virtualbox_vms())
            
        # Add VMware VMs
        if env["vmware_available"] or env["os"] == "Darwin":
            vms.extend(self.list_vmware_vms())
            
        # Add KVM VMs
        if env["virsh_available"]:
            vms.extend(self.list_kvm_vms())
            
        # Add Hyper-V VMs
        if env["os"] == "Windows":
            vms.extend(self.list_hyperv_vms())
            
        # Add UTM VMs on macOS
        if env["os"] == "Darwin":
            vms.extend(self.list_utm_vms())
            
        if not vms:
            vms.append({
                "name": "No VMs Found", 
                "status": "N/A", 
                "platform": "None",
                "os_type": "N/A",
                "memory": "N/A",
                "cpu_count": "N/A",
                "architecture": "N/A"
            })
            
        return vms

    def get_environment_info(self):
        """Get comprehensive environment information."""
        env = self.env
        tools = []
        
        if env["vbox_available"]:
            tools.append("VirtualBox")
        if env["vmware_available"]:
            tools.append("VMware")
        if env["virsh_available"]:
            tools.append("KVM/libvirt")
        if env["qemu_available"]:
            tools.append("QEMU")
        if env["os"] == "Windows":
            tools.append("Hyper-V")
        if env["os"] == "Darwin":
            tools.append("UTM")
            
        tool_list = ", ".join(tools) if tools else "None"
        
        return f"Platform: {env['os']} ({env['arch']})\nAvailable Tools: {tool_list}"

    def start_vm(self, vm_id):
        """Start a VM by its identifier."""
        pass

    def stop_vm(self, vm_id):
        """Stop a VM by its identifier."""
        pass

    def get_vm_info(self, vm_name):
        """Get detailed information about a VM by name."""
        vms = self.list_vms()
        for vm in vms:
            if vm['name'] == vm_name:
                return vm
        return None

def get_machine_info():
    """Get comprehensive machine information."""
    info = {
        'type': 'host',
        'os': platform.system(),
        'os_version': platform.version(),
        'hostname': socket.gethostname(),
        'ip': None,
        'vm_platform': None,
        'architecture': platform.machine(),
        'processor': platform.processor()
    }
    
    # Try to get real network IP address
    try:
        # Create a socket to get the real network IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Connect to a remote address (doesn't actually send data)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and ip != '127.0.0.1':
            info['ip'] = ip
        else:
            info['ip'] = '127.0.0.1 (localhost)'
    except Exception:
        # Fallback to hostname method
        try:
            ip = socket.gethostbyname(socket.gethostname())
            if ip and ip != 'Unknown':
                info['ip'] = ip
            else:
                info['ip'] = 'Unknown'
        except Exception:
            info['ip'] = 'Unknown'
        
    # Try to detect if running inside a VM
    vm_type = None
    if info['os'] in ['Linux', 'Darwin']:
        try:
            if os.path.exists('/sys/class/dmi/id/product_name'):
                with open('/sys/class/dmi/id/product_name') as f:
                    prod = f.read().strip()
                    if 'VirtualBox' in prod:
                        vm_type = 'VirtualBox'
                    elif 'VMware' in prod:
                        vm_type = 'VMware'
                    elif 'KVM' in prod or 'QEMU' in prod:
                        vm_type = 'KVM/QEMU'
        except Exception:
            pass
    elif info['os'] == 'Windows':
        try:
            result = subprocess.run(['wmic', 'computersystem', 'get', 'model'], 
                                  capture_output=True, text=True)
            if 'VirtualBox' in result.stdout:
                vm_type = 'VirtualBox'
            elif 'VMware' in result.stdout:
                vm_type = 'VMware'
            elif 'KVM' in result.stdout or 'QEMU' in result.stdout:
                vm_type = 'KVM/QEMU'
        except Exception:
            pass
            
    if vm_type:
        info['type'] = 'vm'
        info['vm_platform'] = vm_type
        
    return info 