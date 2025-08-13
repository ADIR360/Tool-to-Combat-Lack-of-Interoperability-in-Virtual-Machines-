import os
import subprocess
import logging
from typing import Optional, List, Dict
import tempfile
import shutil

class VMConverter:
    """Handles VM format conversion between different virtualization platforms."""
    
    SUPPORTED_FORMATS = {
        'vmdk': 'VMware Virtual Disk',
        'vdi': 'VirtualBox Virtual Disk',
        'vhd': 'Microsoft Virtual Hard Disk',
        'vhdx': 'Microsoft Virtual Hard Disk v2',
        'qcow2': 'QEMU Copy On Write v2',
        'raw': 'Raw Disk Image',
        'ova': 'Open Virtual Appliance',
        'ovf': 'Open Virtualization Format'
    }
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.setup_logging()
        
    def setup_logging(self):
        """Configure logging for the converter."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('vm_converter.log'),
                logging.StreamHandler()
            ]
        )
    
    def convert(self, input_path: str, output_path: str, input_format: str, output_format: str) -> bool:
        """
        Convert VM from one format to another.
        Returns True if successful, False otherwise. Logs errors.
        """
        try:
            if not os.path.exists(input_path):
                self.logger.error(f"Input file not found: {input_path}")
                return False
                
            # Auto-detect input format if it doesn't match the file
            detected_format = self._detect_format(input_path)
            if detected_format != input_format.lower():
                self.logger.warning(f"Detected format {detected_format} differs from specified format {input_format}")
                input_format = detected_format
                
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            if input_format == "ova" or input_format == "ovf":
                return self._convert_ova_ovf(input_path, output_path, output_format)
            elif output_format == "ova" or output_format == "ovf":
                return self._convert_to_ova_ovf(input_path, output_path, input_format)
            else:
                return self._convert_disk_format(input_path, output_path, input_format, output_format)
        except Exception as e:
            self.logger.error(f"Conversion failed: {str(e)}")
            return False
            
    def _convert_ova_ovf(self, input_path: str, output_path: str, output_format: str) -> bool:
        """Convert from OVA/OVF to other formats."""
        try:
            temp_vmdk = os.path.splitext(output_path)[0] + "_temp.vmdk"
            ovftool_cmd = ["ovftool", input_path, temp_vmdk]
            result = subprocess.run(ovftool_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                self.logger.error(f"ovftool failed: {result.stderr}")
                return False
            success = self._convert_disk_format(temp_vmdk, output_path, "vmdk", output_format)
            if os.path.exists(temp_vmdk):
                os.remove(temp_vmdk)
            return success
        except Exception as e:
            self.logger.error(f"OVA/OVF conversion failed: {str(e)}")
            return False
            
    def _convert_to_ova_ovf(self, input_path: str, output_path: str, input_format: str) -> bool:
        """Convert to OVA/OVF format."""
        try:
            # Check if ovftool is available
            if not self._check_ovftool():
                return self._create_simple_ovf(input_path, output_path, input_format)
                
            if input_format != "vmdk":
                temp_vmdk = os.path.splitext(output_path)[0] + "_temp.vmdk"
                success = self._convert_disk_format(input_path, temp_vmdk, input_format, "vmdk")
                if not success:
                    return False
                input_path = temp_vmdk
            ovftool_cmd = ["ovftool", input_path, output_path]
            result = subprocess.run(ovftool_cmd, capture_output=True, text=True)
            if input_format != "vmdk" and os.path.exists(temp_vmdk):
                os.remove(temp_vmdk)
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"Conversion to OVA/OVF failed: {str(e)}")
            return False
    
    def _check_ovftool(self) -> bool:
        """Check if ovftool is available on the system."""
        try:
            result = subprocess.run(["ovftool", "--version"], capture_output=True, text=True)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.SubprocessError):
            return False
    
    def _create_simple_ovf(self, input_path: str, output_path: str, input_format: str) -> bool:
        """Create a simple OVF file when ovftool is not available."""
        temp_files = []
        try:
            # First convert to VMDK if not already
            if input_format != "vmdk":
                temp_vmdk = os.path.splitext(output_path)[0] + "_temp.vmdk"
                success = self._convert_disk_format(input_path, temp_vmdk, input_format, "vmdk")
                if not success:
                    return False
                input_path = temp_vmdk
                input_format = "vmdk"
                temp_files.append(temp_vmdk)
            
            # Get file size
            file_size = os.path.getsize(input_path)
            
            # Create a better filename for the VMDK reference
            vmdk_name = os.path.splitext(os.path.basename(output_path))[0] + ".vmdk"
            
            # Create OVF content
            ovf_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Envelope xmlns="http://schemas.dmtf.org/ovf/envelope/1" xmlns:ovf="http://schemas.dmtf.org/ovf/envelope/1" xmlns:rasd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData" xmlns:vssd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <References>
    <File ovf:href="{vmdk_name}" ovf:id="file1" ovf:size="{file_size}"/>
  </References>
  <DiskSection>
    <Info>Virtual disk information</Info>
    <Disk ovf:capacity="10" ovf:capacityAllocationUnits="byte * 2^30" ovf:diskId="disk1" ovf:fileRef="file1" ovf:format="http://www.vmware.com/interfaces/specifications/vmdk.html#streamOptimized"/>
  </DiskSection>
  <NetworkSection>
    <Info>The list of logical networks</Info>
    <Network ovf:name="VM Network">
      <Description>The VM Network</Description>
    </Network>
  </NetworkSection>
  <VirtualSystem ovf:id="vm1">
    <Info>A virtual machine</Info>
    <Name>Converted VM</Name>
    <OperatingSystemSection ovf:id="96" ovf:version="1">
      <Info>The kind of installed guest operating system</Info>
      <Description>Other</Description>
    </OperatingSystemSection>
    <VirtualHardwareSection>
      <Info>Virtual hardware requirements</Info>
      <System>
        <vssd:ElementName>Virtual Hardware Family</vssd:ElementName>
        <vssd:InstanceID>0</vssd:InstanceID>
        <vssd:VirtualSystemIdentifier>vm1</vssd:VirtualSystemIdentifier>
        <vssd:VirtualSystemType>vmx-07</vssd:VirtualSystemType>
      </System>
      <Item>
        <rasd:Caption>1 virtual CPU</rasd:Caption>
        <rasd:Description>Number of virtual CPUs</rasd:Description>
        <rasd:ElementName>1 virtual CPU</rasd:ElementName>
        <rasd:InstanceID>1</rasd:InstanceID>
        <rasd:ResourceType>3</rasd:ResourceType>
        <rasd:VirtualQuantity>1</rasd:VirtualQuantity>
      </Item>
      <Item>
        <rasd:Caption>512 MB of memory</rasd:Caption>
        <rasd:Description>Memory Size</rasd:Description>
        <rasd:ElementName>512 MB of memory</rasd:ElementName>
        <rasd:InstanceID>2</rasd:InstanceID>
        <rasd:ResourceType>4</rasd:ResourceType>
        <rasd:VirtualQuantity>512</rasd:VirtualQuantity>
      </Item>
      <Item>
        <rasd:Caption>SCSI Controller</rasd:Caption>
        <rasd:Description>SCSI Controller</rasd:Description>
        <rasd:ElementName>SCSI Controller</rasd:ElementName>
        <rasd:InstanceID>3</rasd:InstanceID>
        <rasd:ResourceSubType>lsilogic</rasd:ResourceSubType>
        <rasd:ResourceType>6</rasd:ResourceType>
      </Item>
      <Item>
        <rasd:Caption>Hard disk 1</rasd:Caption>
        <rasd:Description>Hard disk</rasd:Description>
        <rasd:ElementName>Hard disk 1</rasd:ElementName>
        <rasd:HostResource>ovf:/disk/disk1</rasd:HostResource>
        <rasd:InstanceID>4</rasd:InstanceID>
        <rasd:Parent>3</rasd:Parent>
        <rasd:ResourceType>17</rasd:ResourceType>
      </Item>
      <Item>
        <rasd:Caption>Network adapter 1</rasd:Caption>
        <rasd:Description>Network adapter</rasd:Description>
        <rasd:ElementName>Network adapter 1</rasd:ElementName>
        <rasd:InstanceID>5</rasd:InstanceID>
        <rasd:ResourceType>10</rasd:ResourceType>
        <rasd:VirtualQuantity>1</rasd:VirtualQuantity>
      </Item>
    </VirtualHardwareSection>
  </VirtualSystem>
</Envelope>"""
            
            # Write OVF file
            with open(output_path, 'w') as f:
                f.write(ovf_content)
            
            # Copy the VMDK file to the same directory as OVF
            output_dir = os.path.dirname(output_path)
            vmdk_path = os.path.join(output_dir, vmdk_name)
            
            if input_path != vmdk_path:
                shutil.copy2(input_path, vmdk_path)
            
            self.logger.info(f"Created simple OVF file: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create simple OVF: {str(e)}")
            return False
        finally:
            # Clean up temporary files
            self._cleanup_temp_files(temp_files)
    
    def _cleanup_temp_files(self, temp_files: List[str]):
        """Clean up temporary files."""
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    self.logger.debug(f"Cleaned up temporary file: {temp_file}")
            except Exception as e:
                self.logger.warning(f"Failed to clean up temporary file {temp_file}: {e}")
            
    def _convert_disk_format(self, input_path: str, output_path: str, input_format: str, output_format: str) -> bool:
        """Convert between disk formats using qemu-img."""
        try:
            qemu_cmd = ["qemu-img", "convert", "-f", input_format, "-O", output_format, input_path, output_path]
            result = subprocess.run(qemu_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"qemu-img failed: {result.stderr}")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Disk format conversion failed: {str(e)}")
            return False
    
    def _detect_format(self, file_path: str) -> str:
        """Detect the format of a virtual machine image by examining the file header."""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(8)
                
            # Check for QCOW2
            if header.startswith(b'QFI'):
                return 'qcow2'
            # Check for VMDK
            elif header.startswith(b'KDMV'):
                return 'vmdk'
            # Check for VDI
            elif header.startswith(b'<<< Oracle VM VirtualBox Disk Image'):
                return 'vdi'
            # Check for VHD
            elif header.startswith(b'conectix'):
                return 'vhd'
            # Check for VHDX
            elif header.startswith(b'vhdxfile'):
                return 'vhdx'
            # Check for RAW (no specific header)
            else:
                # Try to determine if it's raw by checking if it's a multiple of common sector sizes
                file_size = os.path.getsize(file_path)
                if file_size % 512 == 0 or file_size % 4096 == 0:
                    return 'raw'
                else:
                    # Default to raw if we can't determine
                    return 'raw'
                    
        except Exception as e:
            self.logger.warning(f"Could not detect format for {file_path}: {e}")
            # Fallback to extension-based detection
            extension = os.path.splitext(file_path)[1].lower().lstrip('.')
            if extension in self.SUPPORTED_FORMATS:
                return extension
            return 'raw'  # Default to raw if format is unknown
    
    def _can_convert_directly(self, input_format: str, output_format: str) -> bool:
        """Check if direct conversion is possible between formats."""
        # Add logic to determine if direct conversion is possible
        return True  # Simplified for now
    
    def _convert_to_raw(self, input_path: str, output_path: str, input_format: str) -> bool:
        """Convert any format to RAW format."""
        try:
            if input_format == 'vmdk':
                self._vmdk_to_raw(input_path, output_path)
            elif input_format == 'vdi':
                self._vdi_to_raw(input_path, output_path)
            elif input_format == 'vhd':
                self._vhd_to_raw(input_path, output_path)
            elif input_format == 'vhdx':
                self._vhdx_to_raw(input_path, output_path)
            elif input_format == 'qcow2':
                self._qcow2_to_raw(input_path, output_path)
            else:
                raise ValueError(f"Unsupported input format: {input_format}")
            return True
        except Exception as e:
            self.logger.error(f"Conversion to RAW failed: {str(e)}")
            return False
    
    def _convert_from_raw(self, input_path: str, output_path: str, output_format: str) -> bool:
        """Convert from RAW format to any other format."""
        try:
            if output_format == 'vmdk':
                self._raw_to_vmdk(input_path, output_path)
            elif output_format == 'vdi':
                self._raw_to_vdi(input_path, output_path)
            elif output_format == 'vhd':
                self._raw_to_vhd(input_path, output_path)
            elif output_format == 'vhdx':
                self._raw_to_vhdx(input_path, output_path)
            elif output_format == 'qcow2':
                self._raw_to_qcow2(input_path, output_path)
            else:
                raise ValueError(f"Unsupported output format: {output_format}")
            return True
        except Exception as e:
            self.logger.error(f"Conversion from RAW failed: {str(e)}")
            return False
    
    def _vmdk_to_raw(self, input_path: str, output_path: str):
        """Convert VMDK to RAW using qemu-img."""
        subprocess.run([
            'qemu-img', 'convert',
            '-f', 'vmdk',
            '-O', 'raw',
            input_path,
            output_path
        ], check=True)
    
    def _raw_to_vmdk(self, input_path: str, output_path: str):
        """Convert RAW to VMDK using qemu-img."""
        subprocess.run([
            'qemu-img', 'convert',
            '-f', 'raw',
            '-O', 'vmdk',
            input_path,
            output_path
        ], check=True)
    
    def _vdi_to_raw(self, input_path: str, output_path: str):
        """Convert VDI to RAW using VBoxManage."""
        subprocess.run([
            'VBoxManage', 'clonehd',
            input_path,
            output_path,
            '--format', 'RAW'
        ], check=True)
    
    def _raw_to_vdi(self, input_path: str, output_path: str):
        """Convert RAW to VDI using VBoxManage."""
        subprocess.run([
            'VBoxManage', 'convertfromraw',
            input_path,
            output_path,
            '--format', 'VDI'
        ], check=True)
    
    def _vhd_to_raw(self, input_path: str, output_path: str):
        """Convert VHD to RAW using qemu-img."""
        subprocess.run([
            'qemu-img', 'convert',
            '-f', 'vhd',
            '-O', 'raw',
            input_path,
            output_path
        ], check=True)
    
    def _raw_to_vhd(self, input_path: str, output_path: str):
        """Convert RAW to VHD using qemu-img."""
        subprocess.run([
            'qemu-img', 'convert',
            '-f', 'raw',
            '-O', 'vhd',
            input_path,
            output_path
        ], check=True)
    
    def _vhdx_to_raw(self, input_path: str, output_path: str):
        """Convert VHDX to RAW using qemu-img."""
        subprocess.run([
            'qemu-img', 'convert',
            '-f', 'vhdx',
            '-O', 'raw',
            input_path,
            output_path
        ], check=True)
    
    def _raw_to_vhdx(self, input_path: str, output_path: str):
        """Convert RAW to VHDX using qemu-img."""
        subprocess.run([
            'qemu-img', 'convert',
            '-f', 'raw',
            '-O', 'vhdx',
            input_path,
            output_path
        ], check=True)
    
    def _qcow2_to_raw(self, input_path: str, output_path: str):
        """Convert QCOW2 to RAW using qemu-img."""
        subprocess.run([
            'qemu-img', 'convert',
            '-f', 'qcow2',
            '-O', 'raw',
            input_path,
            output_path
        ], check=True)
    
    def _raw_to_qcow2(self, input_path: str, output_path: str):
        """Convert RAW to QCOW2 using qemu-img."""
        subprocess.run([
            'qemu-img', 'convert',
            '-f', 'raw',
            '-O', 'qcow2',
            input_path,
            output_path
        ], check=True) 