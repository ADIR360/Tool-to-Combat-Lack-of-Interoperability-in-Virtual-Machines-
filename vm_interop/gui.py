import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QComboBox, QTabWidget,
    QTextEdit, QProgressBar, QMessageBox, QGroupBox, QLineEdit,
    QSpinBox, QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QFont
from .converter import VMConverter
from .network_analyzer import NetworkAnalyzer
from .vm_manager import VMManager, get_machine_info
from .connectivity_verifier import ConnectivityVerifier
from .file_transfer import send_file
from .messaging import send_message, TCPServer
from .monitoring import send_stats, MonitoringAgent
from .network_orchestrator import assign_static_ip
import platform
import socket

class ConversionWorker(QThread):
    """Worker thread for VM conversion."""
    progress = pyqtSignal(int)
    log_message = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, input_path, output_path, input_format, output_format, options=None):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.input_format = input_format
        self.output_format = output_format
        self.options = options or {}
        
    def run(self):
        try:
            self.log_message.emit("Initializing converter...")
            self.progress.emit(10)
            
            converter = VMConverter()
            self.log_message.emit("Detecting input file format...")
            self.progress.emit(20)
            
            # Detect actual format
            detected_format = converter._detect_format(self.input_path)
            if detected_format != self.input_format.lower():
                self.log_message.emit(f"Detected format: {detected_format} (was specified as {self.input_format})")
                self.input_format = detected_format
            
            self.log_message.emit(f"Starting conversion: {self.input_format} → {self.output_format}")
            self.progress.emit(40)
            
            success = converter.convert(
                self.input_path,
                self.output_path,
                self.input_format,
                self.output_format,
                **self.options
            )
            
            if success:
                self.progress.emit(100)
                self.log_message.emit("Conversion completed successfully!")
                self.finished.emit(True, "Conversion completed successfully")
            else:
                self.progress.emit(0)
                self.log_message.emit("Conversion failed - check logs for details")
                self.finished.emit(False, "Conversion failed")
                
        except Exception as e:
            self.progress.emit(0)
            error_msg = f"Conversion error: {str(e)}"
            self.log_message.emit(error_msg)
            self.finished.emit(False, error_msg)

class NetworkCaptureWorker(QThread):
    """Worker thread for network capture."""
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, interface, duration, output_file):
        super().__init__()
        self.interface = interface
        self.duration = duration
        self.output_file = output_file
        
    def run(self):
        try:
            analyzer = NetworkAnalyzer(interface=self.interface)
            df = analyzer.capture_traffic(
                duration=self.duration,
                output_file=self.output_file
            )
            self.finished.emit(True, f"Captured {len(df)} packets")
        except Exception as e:
            self.finished.emit(False, str(e))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VM Interoperability Tool")
        self.setMinimumSize(800, 600)  # Reduced for 13-inch MacBook
        self.resize(900, 650)  # Set a reasonable default size
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(4)  # Much tighter spacing
        layout.setContentsMargins(4, 4, 4, 4)  # Minimal margins
        
        # Create tab widget with smaller font
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2a2a2a;
                color: white;
                padding: 6px 12px;
                margin-right: 2px;
                border-radius: 3px;
                font-size: 11px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #3a3a3a;
            }
            QTabBar::tab:hover {
                background-color: #404040;
            }
        """)
        layout.addWidget(tabs)
        
        # Add conversion tab
        conversion_tab = QWidget()
        tabs.addTab(conversion_tab, "VM Conversion")
        self.setup_conversion_tab(conversion_tab)
        
        # Add interop dashboard tab
        interop_tab = QWidget()
        tabs.addTab(interop_tab, "Interop Dashboard")
        self.setup_interop_tab(interop_tab)
        
        # Add network orchestrator tab
        network_tab = QWidget()
        tabs.addTab(network_tab, "Network Orchestrator")
        self.setup_network_tab(network_tab)
        
        # Add status bar with smaller font
        self.statusBar().setStyleSheet("color: white; background-color: #2a2a2a; font-size: 10px;")
        self.statusBar().showMessage("Ready")
        
    def setup_conversion_tab(self, tab):
        """Setup the VM conversion tab - redesigned for better functionality and theme consistency."""
        layout = QVBoxLayout(tab)
        layout.setSpacing(3)  # Much tighter spacing
        layout.setContentsMargins(3, 3, 3, 3)  # Minimal margins
        
        # Header Section
        header_group = QGroupBox("🚀 VM Format Converter")
        header_group.setStyleSheet("""
            QGroupBox {
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
                background-color: #2a2a2a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 6px 0 6px;
            }
        """)
        header_layout = QVBoxLayout()
        
        # Description
        desc_label = QLabel("Convert virtual machine disk images between different formats")
        desc_label.setStyleSheet("color: #e0e0e0; font-size: 10px; padding: 4px; text-align: center; font-weight: normal;")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setMaximumHeight(20)
        header_layout.addWidget(desc_label)
        
        # Supported formats info
        formats_info = QLabel("Supported: VMDK, VDI, VHD, VHDX, QCOW2, RAW, OVA, OVF")
        formats_info.setStyleSheet("color: #17a2b8; font-size: 9px; padding: 2px; text-align: center; font-weight: normal;")
        formats_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        formats_info.setMaximumHeight(16)
        header_layout.addWidget(formats_info)
        
        header_group.setLayout(header_layout)
        layout.addWidget(header_group)
        
        # Input Section
        input_group = QGroupBox("📥 Input VM")
        input_group.setStyleSheet("""
            QGroupBox {
                color: white;
                font-weight: bold;
                font-size: 11px;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
                background-color: #2a2a2a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 6px 0 6px;
            }
        """)
        input_layout = QVBoxLayout()
        input_layout.setSpacing(3)
        
        # File selection row
        file_row = QHBoxLayout()
        file_row.setSpacing(3)
        
        self.input_path = QLineEdit()
        self.input_path.setReadOnly(True)
        self.input_path.setPlaceholderText("Select input VM file...")
        self.input_path.setStyleSheet("""
            QLineEdit {
                color: white;
                background-color: #353535;
                padding: 4px;
                border-radius: 3px;
                font-size: 10px;
            }
            QLineEdit::placeholder-text {
                color: #a0a0a0;
                font-style: italic;
            }
        """)
        self.input_path.setMaximumHeight(24)
        file_row.addWidget(QLabel("File:"))
        file_row.addWidget(self.input_path)
        
        input_file_btn = QPushButton("Browse")
        input_file_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #17a2b8;
                padding: 4px 8px;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #20c997;
            }
            QPushButton:pressed {
                background-color: #138496;
            }
        """)
        input_file_btn.setMaximumHeight(24)
        input_file_btn.clicked.connect(self.select_input_file)
        file_row.addWidget(input_file_btn)
        
        input_layout.addLayout(file_row)
        
        # Format selection row
        format_row = QHBoxLayout()
        format_row.setSpacing(3)
        
        self.input_format = QComboBox()
        self.input_format.addItems(["vmdk", "vdi", "vhd", "vhdx", "qcow2", "raw", "ova", "ovf"])
        self.input_format.setStyleSheet("""
            QComboBox {
                color: white;
                background-color: #353535;
                padding: 4px;
                border-radius: 3px;
                font-size: 10px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid white;
                margin-right: 5px;
            }
        """)
        self.input_format.currentTextChanged.connect(self.update_input_format)
        self.input_format.setMaximumHeight(24)
        format_row.addWidget(QLabel("Format:"))
        format_row.addWidget(self.input_format)
        
        # Auto-detect button
        detect_btn = QPushButton("🔍 Auto-detect")
        detect_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #6c757d;
                padding: 4px 8px;
                border-radius: 3px;
                font-weight: bold;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: #868e96;
            }
            QPushButton:pressed {
                background-color: #545b62;
            }
        """)
        detect_btn.setMaximumHeight(24)
        detect_btn.clicked.connect(self.auto_detect_format)
        format_row.addWidget(detect_btn)
        
        input_layout.addLayout(format_row)
        
        # File info display
        self.file_info_label = QLabel("No file selected")
        self.file_info_label.setStyleSheet("color: #a0a0a0; font-size: 9px; padding: 2px; background-color: #353535; border-radius: 2px;")
        self.file_info_label.setMaximumHeight(16)
        input_layout.addWidget(self.file_info_label)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        # Output Section
        output_group = QGroupBox("📤 Output VM")
        output_group.setStyleSheet("""
            QGroupBox {
                color: white;
                font-weight: bold;
                font-size: 11px;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
                background-color: #2a2a2a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 6px 0 6px;
            }
        """)
        output_layout = QVBoxLayout()
        output_layout.setSpacing(3)
        
        # Output format selection
        output_format_row = QHBoxLayout()
        output_format_row.setSpacing(3)
        
        self.output_format = QComboBox()
        self.output_format.addItems(["vmdk", "vdi", "vhd", "vhdx", "qcow2", "raw", "ova", "ovf"])
        self.output_format.setStyleSheet("""
            QComboBox {
                color: white;
                background-color: #353535;
                padding: 4px;
                border-radius: 3px;
                font-size: 10px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid white;
                margin-right: 5px;
            }
        """)
        self.output_format.currentTextChanged.connect(self.update_output_format)
        self.output_format.setMaximumHeight(24)
        output_format_row.addWidget(QLabel("Format:"))
        output_format_row.addWidget(self.output_format)
        
        output_layout.addLayout(output_format_row)
        
        # Output file selection
        output_file_row = QHBoxLayout()
        output_file_row.setSpacing(3)
        
        self.output_path = QLineEdit()
        self.output_path.setReadOnly(True)
        self.output_path.setPlaceholderText("Select output location...")
        self.output_path.setStyleSheet("""
            QLineEdit {
                color: white;
                background-color: #353535;
                padding: 4px;
                border-radius: 3px;
                font-size: 10px;
            }
            QLineEdit::placeholder-text {
                color: #a0a0a0;
                font-style: italic;
            }
        """)
        self.output_path.textChanged.connect(self.validate_output_path)
        self.output_path.setMaximumHeight(24)
        output_file_row.addWidget(QLabel("Location:"))
        output_file_row.addWidget(self.output_path)
        
        output_file_btn = QPushButton("Browse")
        output_file_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #17a2b8;
                padding: 4px 8px;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #20c997;
            }
            QPushButton:pressed {
                background-color: #138496;
            }
        """)
        output_file_btn.setMaximumHeight(24)
        output_file_btn.clicked.connect(self.select_output_file)
        output_file_row.addWidget(output_file_btn)
        
        output_layout.addLayout(output_file_row)
        
        # Status label for output validation
        self.output_status = QLabel()
        self.output_status.setStyleSheet("color: #a0a0a0; font-size: 9px; padding: 2px;")
        self.output_status.setMaximumHeight(16)
        output_layout.addWidget(self.output_status)
        
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)
        
        # Conversion Options Section
        options_group = QGroupBox("⚙️ Conversion Options")
        options_group.setStyleSheet("""
            QGroupBox {
                color: white;
                font-weight: bold;
                font-size: 11px;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
                background-color: #2a2a2a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 6px 0 6px;
            }
        """)
        options_layout = QHBoxLayout()
        options_layout.setSpacing(8)
        
        # Compression option
        self.compress_checkbox = QCheckBox("Compress output")
        self.compress_checkbox.setStyleSheet("color: white; font-size: 10px;")
        self.compress_checkbox.setMaximumHeight(20)
        options_layout.addWidget(self.compress_checkbox)
        
        # Overwrite option
        self.overwrite_checkbox = QCheckBox("Overwrite existing")
        self.overwrite_checkbox.setStyleSheet("color: white; font-size: 10px;")
        self.overwrite_checkbox.setMaximumHeight(20)
        options_layout.addWidget(self.overwrite_checkbox)
        
        options_layout.addStretch()
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Progress Section
        progress_group = QGroupBox("📊 Progress")
        progress_group.setStyleSheet("""
            QGroupBox {
                color: white;
                font-weight: bold;
                font-size: 11px;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
                background-color: #2a2a2a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 6px 0 6px;
            }
        """)
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(3)
        
        # Progress bar
        self.progress = QProgressBar()
        self.progress.setStyleSheet("""
            QProgressBar {
                border-radius: 3px;
                text-align: center;
                color: white;
                font-size: 9px;
                background-color: #353535;
            }
            QProgressBar::chunk {
                background-color: #28a745;
                border-radius: 2px;
            }
        """)
        self.progress.setMaximumHeight(18)
        progress_layout.addWidget(self.progress)
        
        # Progress status
        self.progress_status = QLabel("Ready to convert")
        self.progress_status.setStyleSheet("color: #e0e0e0; font-size: 9px; padding: 2px; text-align: center;")
        self.progress_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_status.setMaximumHeight(16)
        progress_layout.addWidget(self.progress_status)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # Action Buttons Section
        button_group = QGroupBox("🎯 Actions")
        button_group.setStyleSheet("""
            QGroupBox {
                color: white;
                font-weight: bold;
                font-size: 11px;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
                background-color: #2a2a2a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 6px 0 6px;
            }
        """)
        button_layout = QHBoxLayout()
        button_layout.setSpacing(6)
        
        # Convert button
        convert_btn = QPushButton("🚀 Start Conversion")
        convert_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #28a745;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #34ce57;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #a0a0a0;
            }
        """)
        convert_btn.setMaximumHeight(28)
        convert_btn.clicked.connect(self.start_conversion)
        convert_btn.setEnabled(False)  # Initially disabled
        self.convert_btn = convert_btn  # Store reference
        button_layout.addWidget(convert_btn)
        
        # Clear button
        clear_btn = QPushButton("🧹 Clear All")
        clear_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #6c757d;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #868e96;
            }
            QPushButton:pressed {
                background-color: #545b62;
            }
        """)
        clear_btn.setMaximumHeight(28)
        clear_btn.clicked.connect(self.clear_all_fields)
        button_layout.addWidget(clear_btn)
        
        button_layout.addStretch()
        button_group.setLayout(button_layout)
        layout.addWidget(button_group)
        
        # Log Display Section
        log_group = QGroupBox("📝 Conversion Log")
        log_group.setStyleSheet("""
            QGroupBox {
                color: white;
                font-weight: bold;
                font-size: 11px;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
                background-color: #2a2a2a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 6px 0 6px;
            }
        """)
        log_layout = QVBoxLayout()
        log_layout.setSpacing(3)
        
        # Log display
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("""
            QTextEdit {
                color: #e0e0e0;
                background-color: #353535;
                border-radius: 3px;
                padding: 6px;
                font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
                font-size: 9px;
            }
        """)
        self.log_display.setMaximumHeight(80)
        self.log_display.setPlaceholderText("Conversion log will appear here...")
        log_layout.addWidget(self.log_display)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        # Add stretch to push everything to the top
        layout.addStretch()
        
    def update_input_format(self, format_name):
        """Update input format and validate input file with improved feedback."""
        if self.input_path.text():
            self.log_display.append(f"🔄 Input format changed to: {format_name}")
            self.validate_input_path()
            self.update_convert_button_state()
            
    def update_output_format(self, format_name):
        """Update output format and validate output path with improved feedback."""
        if self.output_path.text():
            # Update output path extension if it exists
            old_path = self.output_path.text()
            if old_path and "." in old_path:
                base_path = os.path.splitext(old_path)[0]
                new_path = f"{base_path}.{format_name}"
                self.output_path.setText(new_path)
                self.log_display.append(f"🔄 Output format changed to: {format_name}")
                self.log_display.append(f"📁 Output path updated to: {os.path.basename(new_path)}")
                self.validate_output_path()
                self.update_convert_button_state()
            
    def validate_input_path(self):
        """Validate input file path and format with improved feedback."""
        input_path = self.input_path.text()
        if not input_path:
            return False
            
        if not os.path.exists(input_path):
            self.log_display.append(f"❌ Error: Input file not found: {input_path}")
            self.file_info_label.setText("File not found")
            self.file_info_label.setStyleSheet("color: #dc3545; font-size: 9px; padding: 2px; background-color: #353535; border-radius: 2px;")
            return False
            
        # Check if file extension matches selected format
        ext = os.path.splitext(input_path)[1].lower().lstrip('.')
        selected_format = self.input_format.currentText()
        
        # Try to detect actual format
        try:
            from .converter import VMConverter
            converter = VMConverter()
            detected_format = converter._detect_format(input_path)
            
            if detected_format and detected_format != selected_format.lower():
                self.log_display.append(f"ℹ️ Info: File detected as {detected_format} format (extension suggests {ext})")
                # Update the input format combo box to match detected format
                index = self.input_format.findText(detected_format)
                if index >= 0:
                    self.input_format.setCurrentIndex(index)
                    self.log_display.append(f"✅ Updated input format to {detected_format}")
                    self.file_info_label.setText(f"Detected format: {detected_format}")
                    self.file_info_label.setStyleSheet("color: #17a2b8; font-size: 9px; padding: 2px; background-color: #353535; border-radius: 2px;")
            elif detected_format:
                self.log_display.append(f"✅ Format validation: {selected_format} ✓")
                self.file_info_label.setText(f"Format: {selected_format}")
                self.file_info_label.setStyleSheet("color: #28a745; font-size: 9px; padding: 2px; background-color: #353535; border-radius: 2px;")
            else:
                self.log_display.append(f"⚠️ Warning: Could not detect file format")
                
        except Exception as e:
            self.log_display.append(f"⚠️ Warning: Could not detect file format: {e}")
            if ext != selected_format:
                self.log_display.append(f"⚠️ Warning: File extension ({ext}) doesn't match selected format ({selected_format})")
            
        return True
        
    def validate_output_path(self):
        """Validate output file path and format with improved feedback."""
        output_path = self.output_path.text()
        if not output_path:
            self.output_status.setText("")
            self.output_status.setStyleSheet("color: #a0a0a0; font-size: 9px; padding: 2px;")
            return False
            
        # Check if output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            self.output_status.setText("Output directory will be created")
            self.output_status.setStyleSheet("color: #ffc107; font-size: 9px; padding: 2px; background-color: #353535; border-radius: 2px;")
        else:
            self.output_status.setText("")
            self.output_status.setStyleSheet("color: #a0a0a0; font-size: 9px; padding: 2px;")
            
        # Check if output file already exists
        if os.path.exists(output_path):
            if self.overwrite_checkbox.isChecked():
                self.output_status.setText("File will be overwritten")
                self.output_status.setStyleSheet("color: #ffc107; font-size: 9px; padding: 2px; background-color: #353535; border-radius: 2px;")
            else:
                self.output_status.setText("Warning: Output file already exists")
                self.output_status.setStyleSheet("color: #dc3545; font-size: 9px; padding: 2px; background-color: #353535; border-radius: 2px;")
                return False
            
        return True
        
    def select_input_file(self):
        """Handle input file selection with improved functionality."""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select Input VM",
            "",
            "VM Files (*.vmdk *.vdi *.vhd *.vhdx *.qcow2 *.raw *.ova *.ovf);;All Files (*.*)"
        )
        if file_name:
            self.input_path.setText(file_name)
            self.update_file_info(file_name)
            self.validate_input_path()
            self.update_convert_button_state()
            
    def update_file_info(self, file_path):
        """Update file information display."""
        try:
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                size_mb = file_size / (1024 * 1024)
                if size_mb > 1024:
                    size_str = f"{size_mb/1024:.1f} GB"
                else:
                    size_str = f"{size_mb:.1f} MB"
                
                self.file_info_label.setText(f"File: {os.path.basename(file_path)} | Size: {size_str}")
                self.file_info_label.setStyleSheet("color: #28a745; font-size: 9px; padding: 2px; background-color: #353535; border-radius: 2px;")
            else:
                self.file_info_label.setText("File not found")
                self.file_info_label.setStyleSheet("color: #dc3545; font-size: 9px; padding: 2px; background-color: #353535; border-radius: 2px;")
        except Exception as e:
            self.file_info_label.setText(f"Error reading file: {str(e)}")
            self.file_info_label.setStyleSheet("color: #dc3545; font-size: 9px; padding: 2px; background-color: #353535; border-radius: 2px;")
            
    def auto_detect_format(self):
        """Auto-detect the format of the selected input file."""
        input_path = self.input_path.text()
        if not input_path:
            self.log_display.append("No input file selected for format detection.")
            return
            
        if not os.path.exists(input_path):
            self.log_display.append("Input file not found.")
            return
            
        try:
            from .converter import VMConverter
            converter = VMConverter()
            detected_format = converter._detect_format(input_path)
            
            if detected_format:
                # Update the input format combo box
                index = self.input_format.findText(detected_format)
                if index >= 0:
                    self.input_format.setCurrentIndex(index)
                    self.log_display.append(f"✅ Auto-detected format: {detected_format}")
                    self.file_info_label.setText(f"Detected format: {detected_format}")
                    self.file_info_label.setStyleSheet("color: #17a2b8; font-size: 9px; padding: 2px; background-color: #353535; border-radius: 2px;")
                else:
                    self.log_display.append(f"⚠️ Detected format '{detected_format}' not in supported formats list")
            else:
                self.log_display.append("❌ Could not detect file format")
                
        except Exception as e:
            self.log_display.append(f"❌ Format detection failed: {str(e)}")
            
    def update_convert_button_state(self):
        """Update the convert button state based on input validation."""
        input_path = self.input_path.text()
        output_path = self.output_path.text()
        
        if input_path and output_path and os.path.exists(input_path):
            self.convert_btn.setEnabled(True)
            self.convert_btn.setStyleSheet("""
                QPushButton {
                    color: white;
                    background-color: #28a745;
                    padding: 6px 12px;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #34ce57;
                }
                QPushButton:pressed {
                    background-color: #1e7e34;
                }
            """)
        else:
            self.convert_btn.setEnabled(False)
            self.convert_btn.setStyleSheet("""
                QPushButton {
                    color: white;
                    background-color: #6c757d;
                    padding: 6px 12px;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 11px;
                }
            """)
            
    def clear_all_fields(self):
        """Clear all input and output fields."""
        self.input_path.clear()
        self.output_path.clear()
        self.input_format.setCurrentIndex(0)
        self.output_format.setCurrentIndex(0)
        self.file_info_label.setText("No file selected")
        self.file_info_label.setStyleSheet("color: #a0a0a0; font-size: 9px; padding: 2px; background-color: #353535; border-radius: 2px;")
        self.output_status.setText("")
        self.log_display.clear()
        self.progress.setValue(0)
        self.progress_status.setText("Ready to convert")
        self.convert_btn.setEnabled(False)
        self.compress_checkbox.setChecked(False)
        self.overwrite_checkbox.setChecked(False)
        
    def select_output_file(self):
        """Handle output file selection with improved functionality."""
        # Get the selected output format
        output_format = self.output_format.currentText()
        
        # Get the input filename (without extension)
        input_filename = os.path.splitext(os.path.basename(self.input_path.text()))[0] if self.input_path.text() else "output"
        
        # Open folder picker
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder", "")
        if folder:
            output_path = os.path.join(folder, f"{input_filename}.{output_format}")
            self.output_path.setText(output_path)
            self.validate_output_path()
            self.update_convert_button_state()
            
    def start_conversion(self):
        """Start VM conversion process with improved functionality and user feedback."""
        input_path = self.input_path.text()
        output_path = self.output_path.text()
        input_format = self.input_format.currentText()
        output_format = self.output_format.currentText()

        # Clear previous log
        self.log_display.clear()
        self.log_display.append("🚀 Starting VM conversion process...")

        # Validate input
        if not input_path or not output_path:
            self.log_display.append("❌ Error: Please select input and output files.")
            QMessageBox.warning(self, "Error", "Please select input and output files")
            return
            
        if not self.validate_input_path():
            self.log_display.append("❌ Error: Invalid input file.")
            QMessageBox.warning(self, "Error", "Invalid input file")
            return
            
        if not self.validate_output_path():
            if not self.overwrite_checkbox.isChecked():
                reply = QMessageBox.question(
                    self,
                    "Confirm Overwrite",
                    "Output file already exists. Do you want to overwrite it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    self.log_display.append("❌ Conversion cancelled by user.")
                    return
                    
        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
                self.log_display.append(f"✅ Created output directory: {output_dir}")
            except Exception as e:
                self.log_display.append(f"❌ Failed to create output directory: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to create output directory: {str(e)}")
                return
                
        # Prepare conversion options
        options = {}
        if self.compress_checkbox.isChecked():
            options['compress'] = True
            self.log_display.append("📦 Compression enabled")
            
        if self.overwrite_checkbox.isChecked():
            options['overwrite'] = True
            self.log_display.append("🔄 Overwrite mode enabled")
            
        # Start conversion
        self.progress.setValue(0)
        self.progress_status.setText("Converting...")
        self.convert_btn.setEnabled(False)
        self.convert_btn.setText("Converting...")
        
        self.log_display.append(f"🔄 Starting conversion: {input_format} → {output_format}")
        self.log_display.append(f"📁 Input: {os.path.basename(input_path)}")
        self.log_display.append(f"📁 Output: {os.path.basename(output_path)}")
        
        # Create and start conversion worker
        self.worker = ConversionWorker(
            input_path,
            output_path,
            input_format,
            output_format,
            options
        )
        self.worker.progress.connect(self.progress.setValue)
        self.worker.log_message.connect(self.log_display.append)
        self.worker.finished.connect(self.conversion_finished)
        self.worker.start()

    def conversion_finished(self, success, message):
        """Handle conversion completion with improved feedback."""
        if success:
            self.progress.setValue(100)
            self.progress_status.setText("Conversion completed successfully!")
            self.log_display.append(f"✅ {message}")
            self.log_display.append("🎉 Conversion completed successfully!")
            
            # Show success message
            QMessageBox.information(self, "Success", f"VM conversion completed successfully!\n\nOutput: {os.path.basename(self.output_path.text())}")
            
            # Update file info
            if os.path.exists(self.output_path.text()):
                output_size = os.path.getsize(self.output_path.text())
                size_mb = output_size / (1024 * 1024)
                if size_mb > 1024:
                    size_str = f"{size_mb/1024:.1f} GB"
                else:
                    size_str = f"{size_mb:.1f} MB"
                self.log_display.append(f"📊 Output file size: {size_str}")
        else:
            self.progress.setValue(0)
            self.progress_status.setText("Conversion failed")
            self.log_display.append(f"❌ {message}")
            self.log_display.append("💥 Conversion failed. Check the log for details.")
            
            # Show error message
            QMessageBox.critical(self, "Conversion Failed", f"VM conversion failed:\n\n{message}")
            
        # Reset UI state
        self.convert_btn.setEnabled(True)
        self.convert_btn.setText("🚀 Start Conversion")
        self.update_convert_button_state()

    def setup_interop_tab(self, tab):
        """Setup the interop dashboard tab."""
        layout = QVBoxLayout(tab)
        layout.setSpacing(3)  # Much tighter spacing
        layout.setContentsMargins(3, 3, 3, 3)  # Minimal margins
        
        # --- Environment Information Section ---
        env_group = QGroupBox("🔧 Environment Information")
        env_group.setStyleSheet("""
            QGroupBox {
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 6px 0 6px;
            }
        """)
        env_layout = QVBoxLayout()
        
        self.env_info_label = QLabel()
        self.env_info_label.setStyleSheet("""
            color: white;
            padding: 8px;
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2a2a2a, stop:1 #353535);
            border-radius: 4px;
            font-size: 11px;
        """)
        self.env_info_label.setToolTip("Shows the detected OS, architecture, and available VM tool.")
        self.env_info_label.setWordWrap(True)
        self.env_info_label.setMaximumHeight(40)  # Much smaller height
        env_layout.addWidget(self.env_info_label)
        
        env_group.setLayout(env_layout)
        layout.addWidget(env_group)

        # --- Machine Info Section ---
        machine_info = get_machine_info()
        
        # Create table widget for machine info
        self.machine_info_table = QTableWidget()
        self.machine_info_table.setColumnCount(2)
        self.machine_info_table.setHorizontalHeaderLabels(["Property", "Value"])
        
        # Set table properties
        self.machine_info_table.setAlternatingRowColors(True)
        self.machine_info_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.machine_info_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.machine_info_table.verticalHeader().setVisible(False)
        self.machine_info_table.setMaximumHeight(120)  # Much smaller height
        
        # Style the machine info table
        self.machine_info_table.setStyleSheet("""
            QTableWidget {
                color: white;
                background-color: #2a2a2a;
                gridline-color: #404040;
                selection-background-color: #404040;
                alternate-background-color: #353535;
            }
            QTableWidget::item {
                padding: 1px;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: #404040;
            }
            QHeaderView::section {
                background-color: #404040;
                color: white;
                padding: 2px;
                font-weight: bold;
                font-size: 10px;
            }
            QHeaderView::section:hover {
                background-color: #505050;
            }
        """)
        
        # Set column resize modes
        header = self.machine_info_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Property
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Value
        
        # Populate machine info table
        self.load_machine_info_table()
        
        # Add machine info table above VM list
        machine_info_group = QGroupBox("🏠 Host Environment Information")
        machine_info_group.setStyleSheet("""
            QGroupBox {
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 6px 0 6px;
            }
        """)
        machine_info_layout = QVBoxLayout()
        machine_info_layout.addWidget(self.machine_info_table)
        machine_info_group.setLayout(machine_info_layout)
        layout.addWidget(machine_info_group)

        # --- VM List Section ---
        vm_group = QGroupBox("🖥️ Virtual Machines")
        vm_group.setStyleSheet("""
            QGroupBox {
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 6px 0 6px;
            }
        """)
        vm_layout = QVBoxLayout()
        self.vm_manager = VMManager()
        
        # Create table widget for VM list
        self.vm_list = QTableWidget()
        self.vm_list.setColumnCount(7)
        self.vm_list.setHorizontalHeaderLabels(["Name", "Status", "Platform", "OS Type", "Architecture", "Memory", "CPU"])
        
        # Set table properties
        self.vm_list.setAlternatingRowColors(True)
        self.vm_list.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.vm_list.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.vm_list.verticalHeader().setVisible(False)
        self.vm_list.setMaximumHeight(140)  # Much smaller height
        
        # Style the table
        self.vm_list.setStyleSheet("""
            QTableWidget {
                color: white;
                background-color: #2a2a2a;
                gridline-color: #404040;
                selection-background-color: #404040;
                alternate-background-color: #353535;
            }
            QTableWidget::item {
                padding: 1px;
                border: none;
                font-size: 10px;
            }
            QTableWidget::item:selected {
                background-color: #404040;
            }
            QHeaderView::section {
                background-color: #404040;
                color: white;
                padding: 2px;
                font-weight: bold;
                font-size: 10px;
            }
            QHeaderView::section:hover {
                background-color: #505050;
            }
        """)
        
        # Set column resize modes
        header = self.vm_list.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Name - stretch
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Status
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Platform
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # OS Type
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Architecture
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Memory
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # CPU
        
        self.load_vm_list()
        vm_layout.addWidget(self.vm_list)
        reload_btn = QPushButton("Reload VM List")
        reload_btn.setStyleSheet("color: white;")
        reload_btn.clicked.connect(self.load_vm_list)
        reload_btn.setMaximumHeight(24)  # Much smaller height
        vm_layout.addWidget(reload_btn)
        vm_group.setLayout(vm_layout)
        layout.addWidget(vm_group)

        # --- Connectivity Verifier Section ---
        conn_group = QGroupBox("🔗 Connectivity Verifier")
        conn_group.setStyleSheet("""
            QGroupBox {
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 6px 0 6px;
            }
        """)
        conn_layout = QHBoxLayout()
        conn_layout.setSpacing(3)  # Much tighter spacing
        
        self.source_ip_field = QLineEdit()
        self.source_ip_field.setPlaceholderText("Source IP")
        self.source_ip_field.setStyleSheet("""
            QLineEdit {
                color: white; 
                background-color: #2a2a2a; 
                padding: 3px;
            }
            QLineEdit::placeholder-text {
                color: #a0a0a0;
                font-style: italic;
            }
        """)
        self.source_ip_field.setMaximumHeight(24)  # Much smaller height
        conn_layout.addWidget(QLabel("From:"))
        conn_layout.addWidget(self.source_ip_field)
        
        self.dest_ip_field = QLineEdit()
        self.dest_ip_field.setPlaceholderText("Destination IP")
        self.dest_ip_field.setStyleSheet("""
            QLineEdit {
                color: white; 
                background-color: #2a2a2a; 
                padding: 3px;
            }
            QLineEdit::placeholder-text {
                color: #a0a0a0;
                font-style: italic;
            }
        """)
        self.dest_ip_field.setMaximumHeight(24)  # Much smaller height
        conn_layout.addWidget(QLabel("To:"))
        conn_layout.addWidget(self.dest_ip_field)
        
        verify_btn = QPushButton("Test Connectivity")
        verify_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #17a2b8;
                padding: 4px 8px;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #20c997;
            }
            QPushButton:pressed {
                background-color: #138496;
            }
        """)
        verify_btn.setMaximumHeight(24)  # Much smaller height
        verify_btn.clicked.connect(self.on_verify_connectivity)
        conn_layout.addWidget(verify_btn)
        
        self.connectivity_status = QLabel()
        self.connectivity_status.setStyleSheet("color: white; padding: 4px; background-color: #2a2a2a; border-radius: 3px; font-size: 10px;")
        self.connectivity_status.setMaximumHeight(24)  # Much smaller height
        
        conn_layout.addWidget(self.connectivity_status)
        conn_layout.addStretch()  # Add stretch to push everything to the left
        
        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)

        # --- File Transfer Section ---
        file_group = QGroupBox("📁 File Transfer")
        file_group.setStyleSheet("""
            QGroupBox {
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 6px 0 6px;
            }
        """)
        file_layout = QVBoxLayout()
        file_layout.setSpacing(3)
        
        # Top row - File path, browse, and send button
        top_row = QHBoxLayout()
        top_row.setSpacing(3)
        
        self.file_path_field = QLineEdit()
        self.file_path_field.setPlaceholderText("Local File Path")
        self.file_path_field.setStyleSheet("""
            QLineEdit {
                color: white; 
                background-color: #2a2a2a; 
                padding: 3px;
            }
            QLineEdit::placeholder-text {
                color: #a0a0a0;
                font-style: italic;
            }
        """)
        self.file_path_field.setMaximumHeight(24)  # Much smaller height
        top_row.addWidget(QLabel("File:"))
        top_row.addWidget(self.file_path_field)
        
        file_browse_btn = QPushButton("Browse")
        file_browse_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #6c757d;
                padding: 4px 8px;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #868e96;
            }
            QPushButton:pressed {
                background-color: #545b62;
            }
        """)
        file_browse_btn.setMaximumHeight(24)  # Much smaller height
        file_browse_btn.clicked.connect(self.on_browse_file)
        top_row.addWidget(file_browse_btn)
        
        file_send_btn = QPushButton("Send File")
        file_send_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #28a745;
                padding: 4px 8px;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #34ce57;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        file_send_btn.setMaximumHeight(24)  # Much smaller height
        file_send_btn.clicked.connect(self.on_send_file_clicked)
        top_row.addWidget(file_send_btn)
        
        # Add expand/collapse button for additional fields
        self.file_expand_btn = QPushButton("⚙️ Advanced")
        self.file_expand_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #17a2b8;
                padding: 4px 8px;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #20c997;
            }
            QPushButton:pressed {
                background-color: #138496;
            }
        """)
        self.file_expand_btn.setMaximumHeight(24)  # Much smaller height
        self.file_expand_btn.setCheckable(True)
        self.file_expand_btn.clicked.connect(self.toggle_file_transfer_fields)
        top_row.addWidget(self.file_expand_btn)
        
        file_layout.addLayout(top_row)
        
        # Advanced fields (initially hidden)
        self.file_advanced_widget = QWidget()
        self.file_advanced_widget.setVisible(False)
        advanced_layout = QVBoxLayout(self.file_advanced_widget)
        advanced_layout.setSpacing(3)
        
        # Connection details row
        conn_row = QHBoxLayout()
        conn_row.setSpacing(3)
        
        self.file_dest_ip_field = QLineEdit()
        self.file_dest_ip_field.setPlaceholderText("Destination IP")
        self.file_dest_ip_field.setStyleSheet("""
            QLineEdit {
                color: white; 
                background-color: #2a2a2a; 
                padding: 3px;
            }
            QLineEdit::placeholder-text {
                color: #a0a0a0;
                font-style: italic;
            }
        """)
        self.file_dest_ip_field.setMaximumHeight(24)  # Much smaller height
        conn_row.addWidget(QLabel("To IP:"))
        conn_row.addWidget(self.file_dest_ip_field)
        
        self.file_user_field = QLineEdit()
        self.file_user_field.setPlaceholderText("Username")
        self.file_user_field.setStyleSheet("""
            QLineEdit {
                color: white; 
                background-color: #2a2a2a; 
                padding: 3px;
            }
            QLineEdit::placeholder-text {
                color: #a0a0a0;
                font-style: italic;
            }
        """)
        self.file_user_field.setMaximumHeight(24)  # Much smaller height
        conn_row.addWidget(QLabel("User:"))
        conn_row.addWidget(self.file_user_field)
        
        self.file_pass_field = QLineEdit()
        self.file_pass_field.setPlaceholderText("Password")
        self.file_pass_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.file_pass_field.setStyleSheet("""
            QLineEdit {
                color: white; 
                background-color: #2a2a2a; 
                padding: 3px;
            }
            QLineEdit::placeholder-text {
                color: #a0a0a0;
                font-style: italic;
            }
        """)
        self.file_pass_field.setMaximumHeight(24)  # Much smaller height
        conn_row.addWidget(QLabel("Pass:"))
        conn_row.addWidget(self.file_pass_field)
        
        advanced_layout.addLayout(conn_row)
        file_layout.addWidget(self.file_advanced_widget)
        
        # Status row
        status_row = QHBoxLayout()
        status_row.setSpacing(3)
        
        self.transfer_log = QLabel()
        self.transfer_log.setStyleSheet("color: white; padding: 4px; background-color: #2a2a2a; border-radius: 3px; font-size: 10px;")
        self.transfer_log.setMaximumHeight(24)  # Much smaller height
        status_row.addWidget(self.transfer_log)
        status_row.addStretch()
        
        file_layout.addLayout(status_row)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # --- Messaging Console Section ---
        msg_group = QGroupBox("💬 Messaging Console")
        msg_group.setStyleSheet("""
            QGroupBox {
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 6px 0 6px;
            }
        """)
        msg_layout = QVBoxLayout()
        msg_layout.setSpacing(3)
        
        # Top row - Input fields, send button, and expand button
        top_row = QHBoxLayout()
        top_row.setSpacing(3)
        
        self.message_ip_field = QLineEdit()
        self.message_ip_field.setPlaceholderText("Destination IP")
        self.message_ip_field.setToolTip("Enter the IP address of the recipient VM.")
        self.message_ip_field.setStyleSheet("""
            QLineEdit {
                color: white; 
                background-color: #2a2a2a; 
                padding: 3px;
            }
            QLineEdit::placeholder-text {
                color: #a0a0a0;
                font-style: italic;
            }
        """)
        self.message_ip_field.setMaximumHeight(24)  # Much smaller height
        top_row.addWidget(QLabel("To:"))
        top_row.addWidget(self.message_ip_field)
        
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type your message here...")
        self.message_input.setToolTip("Type your message here.")
        self.message_input.setStyleSheet("""
            QLineEdit {
                color: white; 
                background-color: #2a2a2a; 
                padding: 3px;
            }
            QLineEdit::placeholder-text {
                color: #a0a0a0;
                font-style: italic;
            }
        """)
        self.message_input.setMaximumHeight(24)  # Much smaller height
        top_row.addWidget(QLabel("Message:"))
        top_row.addWidget(self.message_input)
        
        msg_send_btn = QPushButton("Send Message")
        msg_send_btn.setToolTip("Send the message to the specified IP.")
        msg_send_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #28a745;
                padding: 4px 8px;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #34ce57;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        msg_send_btn.setMaximumHeight(24)  # Much smaller height
        msg_send_btn.clicked.connect(self.on_send_message_clicked)
        top_row.addWidget(msg_send_btn)
        
        # Add expand/collapse button for server controls
        self.msg_expand_btn = QPushButton("🖥️ Server")
        self.msg_expand_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #17a2b8;
                padding: 4px 8px;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #20c997;
            }
            QPushButton:pressed {
                background-color: #138496;
            }
        """)
        self.msg_expand_btn.setMaximumHeight(24)  # Much smaller height
        self.msg_expand_btn.setCheckable(True)
        self.msg_expand_btn.clicked.connect(self.toggle_messaging_server_fields)
        top_row.addWidget(self.msg_expand_btn)
        
        msg_layout.addLayout(top_row)
        
        # Server controls (initially hidden)
        self.msg_server_widget = QWidget()
        self.msg_server_widget.setVisible(False)
        server_layout = QVBoxLayout(self.msg_server_widget)
        server_layout.setSpacing(3)
        
        # Server controls row
        server_row = QHBoxLayout()
        server_row.setSpacing(3)
        
        self.msg_server_start_btn = QPushButton("Start Server")
        self.msg_server_start_btn.setToolTip("Start the built-in messaging server to receive messages.")
        self.msg_server_start_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #2d5aa0;
                padding: 4px 8px;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #4a7bc8;
            }
            QPushButton:pressed {
                background-color: #1e3f6b;
            }
        """)
        self.msg_server_start_btn.setMaximumHeight(24)  # Much smaller height
        self.msg_server_start_btn.clicked.connect(self.on_start_msg_server)
        server_row.addWidget(self.msg_server_start_btn)
        
        self.msg_server_stop_btn = QPushButton("Stop Server")
        self.msg_server_stop_btn.setToolTip("Stop the built-in messaging server.")
        self.msg_server_stop_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #dc3545;
                padding: 4px 8px;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #e74c3c;
            }
            QPushButton:pressed {
                background-color: #c82333;
            }
        """)
        self.msg_server_stop_btn.setMaximumHeight(24)  # Much smaller height
        self.msg_server_stop_btn.clicked.connect(self.on_stop_msg_server)
        server_row.addWidget(self.msg_server_stop_btn)
        
        self.msg_server_status = QLabel("Server stopped")
        self.msg_server_status.setToolTip("Shows the status of the built-in messaging server.")
        self.msg_server_status.setStyleSheet("color: white; font-weight: bold; padding: 4px; background-color: #6c757d; border-radius: 3px; font-size: 10px;")
        self.msg_server_status.setMaximumHeight(24)  # Much smaller height
        server_row.addWidget(self.msg_server_status)
        server_row.addStretch()
        
        server_layout.addLayout(server_row)
        msg_layout.addWidget(self.msg_server_widget)
        
        # Message log
        self.message_log = QTextEdit()
        self.message_log.setReadOnly(True)
        self.message_log.setToolTip("Received and sent messages will appear here.")
        self.message_log.setStyleSheet("""
            QTextEdit {
                color: white;
                background-color: #2a2a2a;
                border-radius: 3px;
                padding: 6px;
                font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
                font-size: 10px;
            }
        """)
        self.message_log.setMaximumHeight(60)  # Much smaller height
        msg_layout.addWidget(QLabel("Message Log:"))
        msg_layout.addWidget(self.message_log)
        
        msg_group.setLayout(msg_layout)
        layout.addWidget(msg_group)

        # --- Monitoring Dashboard Section ---
        mon_group = QGroupBox("📊 Monitoring Dashboard")
        mon_group.setStyleSheet("""
            QGroupBox {
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 6px 0 6px;
            }
        """)
        mon_layout = QHBoxLayout()
        mon_layout.setSpacing(3)  # Much tighter spacing
        
        self.cpu_label = QLabel("CPU: N/A")
        self.cpu_label.setToolTip("Shows the current CPU usage.")
        self.cpu_label.setStyleSheet("color: white; font-size: 10px;")
        self.cpu_label.setMaximumHeight(18)  # Much smaller height
        self.ram_label = QLabel("RAM: N/A")
        self.ram_label.setToolTip("Shows the current RAM usage.")
        self.ram_label.setStyleSheet("color: white; font-size: 10px;")
        self.ram_label.setMaximumHeight(18)  # Much smaller height
        self.disk_label = QLabel("Disk: N/A")
        self.disk_label.setToolTip("Shows the current Disk usage.")
        self.disk_label.setStyleSheet("color: white; font-size: 10px;")
        self.disk_label.setMaximumHeight(18)  # Much smaller height
        self.mon_agent_status = QLabel("Agent stopped")
        self.mon_agent_status.setToolTip("Shows the status of the monitoring agent.")
        self.mon_agent_status.setStyleSheet("color: white; font-size: 10px;")
        self.mon_agent_status.setMaximumHeight(18)  # Much smaller height
        self.mon_agent_start_btn = QPushButton("Start Agent")
        self.mon_agent_start_btn.setToolTip("Start the monitoring agent to display real-time stats.")
        self.mon_agent_start_btn.setStyleSheet("color: white; font-size: 10px; padding: 2px 6px;")
        self.mon_agent_start_btn.setMaximumHeight(22)  # Much smaller height
        self.mon_agent_stop_btn = QPushButton("Stop Agent")
        self.mon_agent_stop_btn.setToolTip("Stop the monitoring agent.")
        self.mon_agent_stop_btn.setStyleSheet("color: white; font-size: 10px; padding: 2px 6px;")
        self.mon_agent_stop_btn.setMaximumHeight(22)  # Much smaller height
        self.mon_agent_start_btn.clicked.connect(self.on_start_mon_agent)
        self.mon_agent_stop_btn.clicked.connect(self.on_stop_mon_agent)
        mon_layout.addWidget(self.cpu_label)
        mon_layout.addWidget(self.ram_label)
        mon_layout.addWidget(self.disk_label)
        mon_layout.addWidget(self.mon_agent_start_btn)
        mon_layout.addWidget(self.mon_agent_stop_btn)
        mon_layout.addWidget(self.mon_agent_status)
        mon_group.setLayout(mon_layout)
        layout.addWidget(mon_group)

        # Network Orchestrator has been moved to its own dedicated tab

        self.msg_server = None
        self.mon_agent = None

        self.update_env_info()

    def load_vm_list(self):
        """Load and display the list of VMs with detailed information in a table format."""
        vms = self.vm_manager.list_vms()
        
        if vms and not (len(vms) == 1 and vms[0].get('name') == 'No VMs Found'):
            self.vm_list.setRowCount(len(vms))
            
            for i, vm in enumerate(vms):
                # Create table items for each column
                name_item = QTableWidgetItem(vm.get('name', 'Unknown'))
                status_item = QTableWidgetItem(vm.get('status', 'Unknown'))
                platform_item = QTableWidgetItem(vm.get('platform', 'Unknown'))
                os_type_item = QTableWidgetItem(vm.get('os_type', 'Unknown'))
                architecture_item = QTableWidgetItem(vm.get('architecture', 'Unknown'))
                memory_item = QTableWidgetItem(vm.get('memory', 'Unknown'))
                cpu_item = QTableWidgetItem(vm.get('cpu_count', 'Unknown'))
                
                # Set status colors
                status = vm.get('status', 'Unknown').lower()
                if 'running' in status:
                    status_item.setBackground(Qt.GlobalColor.darkGreen)
                    status_item.setForeground(Qt.GlobalColor.white)
                elif 'stopped' in status or 'off' in status:
                    status_item.setBackground(Qt.GlobalColor.darkRed)
                    status_item.setForeground(Qt.GlobalColor.white)
                elif 'paused' in status or 'saved' in status:
                    status_item.setBackground(Qt.GlobalColor.darkYellow)
                    status_item.setForeground(Qt.GlobalColor.black)
                else:
                    status_item.setBackground(Qt.GlobalColor.darkGray)
                    status_item.setForeground(Qt.GlobalColor.white)
                
                # Set items in table
                self.vm_list.setItem(i, 0, name_item)
                self.vm_list.setItem(i, 1, status_item)
                self.vm_list.setItem(i, 2, platform_item)
                self.vm_list.setItem(i, 3, os_type_item)
                self.vm_list.setItem(i, 4, architecture_item)
                self.vm_list.setItem(i, 5, memory_item)
                self.vm_list.setItem(i, 6, cpu_item)
                
                # Add tooltips with additional information
                tooltip = f"Name: {vm.get('name', 'Unknown')}\n"
                tooltip += f"Status: {vm.get('status', 'Unknown')}\n"
                tooltip += f"Platform: {vm.get('platform', 'Unknown')}\n"
                tooltip += f"OS Type: {vm.get('os_type', 'Unknown')}\n"
                tooltip += f"Architecture: {vm.get('architecture', 'Unknown')}\n"
                tooltip += f"Memory: {vm.get('memory', 'Unknown')}\n"
                tooltip += f"CPU: {vm.get('cpu_count', 'Unknown')}"
                
                if vm.get('ip'):
                    tooltip += f"\nIP Address: {vm.get('ip')}"
                if vm.get('vm_platform'):
                    tooltip += f"\nRunning on: {vm.get('vm_platform')}"
                
                name_item.setToolTip(tooltip)
                status_item.setToolTip(tooltip)
                platform_item.setToolTip(tooltip)
                
        else:
            # No VMs found - show message
            self.vm_list.setRowCount(1)
            self.vm_list.setColumnCount(1)
            self.vm_list.setHorizontalHeaderLabels(["Information"])
            
            # Create message item
            message = "No VMs found.\n\nPlease check if you have any virtualization software installed:\n"
            message += "• VirtualBox\n"
            message += "• VMware Fusion/Workstation\n"
            message += "• KVM/QEMU\n"
            message += "• Hyper-V (Windows)\n"
            message += "• UTM (macOS)"
            
            message_item = QTableWidgetItem(message)
            message_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.vm_list.setItem(0, 0, message_item)
            
            # Reset to original column count for when VMs are found
            self.vm_list.setColumnCount(7)
            self.vm_list.setHorizontalHeaderLabels(["Name", "Status", "Platform", "OS Type", "Architecture", "Memory", "CPU"])
        
        # Auto-resize columns and rows
        self.vm_list.resizeColumnsToContents()
        self.vm_list.resizeRowsToContents()

    def on_verify_connectivity(self):
        """Ping destination IP and show result."""
        ip1 = self.source_ip_field.text()
        ip2 = self.dest_ip_field.text()
        if not ip2:
            self.connectivity_status.setText("Destination IP required.")
            return
        verifier = ConnectivityVerifier()
        result = verifier.ping_vm(ip2)
        if result:
            self.connectivity_status.setText(f"{ip1} can reach {ip2} ✅")
        else:
            self.connectivity_status.setText(f"{ip1} cannot reach {ip2} ❌")

    def on_browse_file(self):
        """Open file dialog to select a file for transfer."""
        file_name, _ = QFileDialog.getOpenFileName(self, "Select File to Send", "", "All Files (*.*)")
        if file_name:
            self.file_path_field.setText(file_name)

    def on_send_file_clicked(self):
        """Send file to another VM using SFTP."""
        file_path = self.file_path_field.text()
        ip = self.file_dest_ip_field.text()
        user = self.file_user_field.text()
        pwd = self.file_pass_field.text()
        if not all([file_path, ip, user, pwd]):
            self.transfer_log.setText("All fields required.")
            return
        # Check SSH server availability
        try:
            sock = socket.create_connection((ip, 22), timeout=5)
            sock.close()
        except Exception:
            self.transfer_log.setText("SSH server not available on target. Ensure SSH is enabled (OpenSSH on Windows, sshd on Linux/Mac).")
            return
        remote_path = os.path.join("/home", user, os.path.basename(file_path))
        success, msg = send_file(ip, user, pwd, file_path, remote_path)
        self.transfer_log.setText(msg if not success else "File sent!")

    def on_send_message_clicked(self):
        """Send a message to another VM."""
        ip = self.message_ip_field.text()
        msg = self.message_input.text()
        if not ip or not msg:
            self.message_log.append("IP and message required.")
            return
        port = 12345  # Default port for demo
        success, errmsg = send_message(ip, port, msg)
        if success:
            self.message_log.append(f"To {ip}: {msg}")
        else:
            self.message_log.append(f"Failed to send to {ip}: {errmsg}")

    def update_monitor_data(self, stats_dict):
        """Update monitoring dashboard with stats."""
        try:
            self.cpu_label.setText(f"CPU: {stats_dict.get('cpu', 'N/A')}%")
            self.ram_label.setText(f"RAM: {stats_dict.get('ram', 'N/A')}%")
            self.disk_label.setText(f"Disk: {stats_dict.get('disk', 'N/A')}%")
        except Exception as e:
            self.cpu_label.setText("CPU: Error")
            self.ram_label.setText("RAM: Error")
            self.disk_label.setText("Disk: Error")
            QMessageBox.warning(self, "Monitoring Error", f"Error updating stats: {e}")

    def on_assign_static_ip_clicked(self):
        """Assign a static IP to a VM via SSH with improved error handling and user feedback."""
        # Validate all required fields
        ip = self.net_ip_field.text().strip()
        user = self.net_user_field.text().strip()
        pwd = self.net_pass_field.text().strip()
        target_ip = self.net_target_ip_field.text().strip()
        subnet = self.net_subnet_field.text().strip()
        gateway = self.net_gateway_field.text().strip()
        
        if not all([ip, user, pwd, target_ip]):
            self.net_status_display.setText("❌ Error: All fields are required!\n\nPlease fill in:\n• VM IP Address\n• SSH Username\n• SSH Password\n• New Static IP")
            return
        
        # Validate IP address format
        if not self._is_valid_ip(target_ip):
            self.net_status_display.setText(f"❌ Error: Invalid IP address format: {target_ip}\n\nPlease use format: 192.168.1.100")
            return
        
        if subnet and not self._is_valid_ip(subnet):
            self.net_status_display.setText(f"❌ Error: Invalid subnet mask format: {subnet}\n\nPlease use format: 255.255.255.0")
            return
        
        if gateway and not self._is_valid_ip(gateway):
            self.net_status_display.setText(f"❌ Error: Invalid gateway IP format: {gateway}\n\nPlease use format: 192.168.1.1")
            return
        
        # Show progress and status
        self.net_progress.setVisible(True)
        self.net_progress.setValue(0)
        self.net_status_display.setText("🔄 Connecting to VM and configuring network...")
        
        try:
            # Test SSH connection first
            self.net_progress.setValue(20)
            if not self._test_ssh_connection(ip, user, pwd):
                self.net_progress.setValue(0)
                self.net_progress.setVisible(False)
                self.net_status_display.setText("❌ SSH Connection Failed!\n\nPlease check:\n• VM IP address is correct\n• SSH service is running on VM\n• Username and password are correct\n• VM is powered on and accessible")
                return
            
            self.net_progress.setValue(40)
            self.net_status_display.setText("✅ SSH connection successful!\n\nDetecting VM operating system...")
            
            # Detect remote OS
            os_type = self._detect_remote_os(ip, user, pwd)
            if not os_type:
                self.net_progress.setValue(0)
                self.net_progress.setVisible(False)
                self.net_status_display.setText("❌ Could not detect VM operating system!\n\nPlease ensure the VM is running and accessible.")
                return
            
            self.net_progress.setValue(60)
            self.net_status_display.setText(f"✅ Detected OS: {os_type}\n\nConfiguring network interface...")
            
            # Configure network based on OS
            if os_type.lower().startswith('linux'):
                success, msg = self._configure_linux_network(ip, user, pwd, target_ip, subnet, gateway)
            elif os_type.lower().startswith('windows'):
                success, msg = self._configure_windows_network(ip, user, pwd, target_ip, subnet, gateway)
            else:
                success, msg = False, f"Unsupported operating system: {os_type}"
            
            self.net_progress.setValue(100)
            self.net_progress.setVisible(False)
            
            if success:
                self.net_status_display.setText(f"✅ Static IP Assignment Successful!\n\nVM {ip} has been configured with:\n• IP Address: {target_ip}\n• Subnet Mask: {subnet or 'Default'}\n• Gateway: {gateway or 'Default'}\n\n⚠️  Note: You may need to reconnect to the VM using the new IP address.")
                QMessageBox.information(self, "Success", f"Static IP {target_ip} has been successfully assigned to VM {ip}!")
            else:
                self.net_status_display.setText(f"❌ Network Configuration Failed!\n\nError: {msg}\n\nPlease check:\n• VM has appropriate permissions\n• Network interface exists\n• No conflicting IP addresses")
                QMessageBox.warning(self, "Error", f"Failed to assign static IP: {msg}")
                
        except Exception as e:
            self.net_progress.setValue(0)
            self.net_progress.setVisible(False)
            error_msg = f"❌ Unexpected Error!\n\nError: {str(e)}\n\nPlease try again or check your connection."
            self.net_status_display.setText(error_msg)
            QMessageBox.critical(self, "Error", f"Unexpected error: {str(e)}")
    
    def on_test_ssh_connection(self):
        """Test SSH connectivity to the VM."""
        ip = self.net_ip_field.text().strip()
        user = self.net_user_field.text().strip()
        pwd = self.net_pass_field.text().strip()
        
        if not all([ip, user, pwd]):
            self.net_status_display.setText("❌ Error: Please fill in VM IP, Username, and Password fields first!")
            return
        
        if not self._is_valid_ip(ip):
            self.net_status_display.setText(f"❌ Error: Invalid IP address format: {ip}")
            return
        
        self.net_status_display.setText("🔄 Testing SSH connection...")
        
        if self._test_ssh_connection(ip, user, pwd):
            os_type = self._detect_remote_os(ip, user, pwd)
            if os_type:
                self.net_status_display.setText(f"✅ SSH Connection Successful!\n\nVM Details:\n• IP Address: {ip}\n• Operating System: {os_type}\n• SSH Access: ✓ Available\n\nReady for network configuration!")
            else:
                self.net_status_display.setText(f"✅ SSH Connection Successful!\n\nVM Details:\n• IP Address: {ip}\n• SSH Access: ✓ Available\n\n⚠️  Could not detect OS type")
        else:
            self.net_status_display.setText("❌ SSH Connection Failed!\n\nPlease check:\n• VM IP address is correct\n• SSH service is running on VM\n• Username and password are correct\n• VM is powered on and accessible")
    
    def on_reset_network_dhcp(self):
        """Reset VM network configuration to use DHCP."""
        ip = self.net_ip_field.text().strip()
        user = self.net_user_field.text().strip()
        pwd = self.net_pass_field.text().strip()
        
        if not all([ip, user, pwd]):
            self.net_status_display.setText("❌ Error: Please fill in VM IP, Username, and Password fields first!")
            return
        
        reply = QMessageBox.question(
            self,
            "Confirm DHCP Reset",
            f"Are you sure you want to reset the network configuration of VM {ip} to use DHCP?\n\nThis will remove the static IP configuration.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.No:
            self.net_status_display.setText("DHCP reset cancelled by user.")
            return
        
        self.net_progress.setVisible(True)
        self.net_progress.setValue(0)
        self.net_status_display.setText("🔄 Resetting network configuration to DHCP...")
        
        try:
            # Test SSH connection
            if not self._test_ssh_connection(ip, user, pwd):
                self.net_progress.setValue(0)
                self.net_progress.setVisible(False)
                self.net_status_display.setText("❌ SSH Connection Failed!")
                return
            
            self.net_progress.setValue(50)
            
            # Detect OS and reset network
            os_type = self._detect_remote_os(ip, user, pwd)
            if os_type.lower().startswith('linux'):
                success, msg = self._reset_linux_network_dhcp(ip, user, pwd)
            elif os_type.lower().startswith('windows'):
                success, msg = self._reset_windows_network_dhcp(ip, user, pwd)
            else:
                success, msg = False, f"Unsupported operating system: {os_type}"
            
            self.net_progress.setValue(100)
            self.net_progress.setVisible(False)
            
            if success:
                self.net_status_display.setText(f"✅ DHCP Reset Successful!\n\nVM {ip} network configuration has been reset to use DHCP.\n\n⚠️  Note: The VM will obtain a new IP address automatically.")
                QMessageBox.information(self, "Success", f"Network configuration for VM {ip} has been reset to DHCP!")
            else:
                self.net_status_display.setText(f"❌ DHCP Reset Failed!\n\nError: {msg}")
                QMessageBox.warning(self, "Error", f"Failed to reset network configuration: {msg}")
                
        except Exception as e:
            self.net_progress.setValue(0)
            self.net_progress.setVisible(False)
            self.net_status_display.setText(f"❌ Unexpected Error!\n\nError: {str(e)}")
            QMessageBox.critical(self, "Error", f"Unexpected error: {str(e)}")
    
    def toggle_file_transfer_fields(self):
        """Toggle visibility of advanced file transfer fields."""
        is_visible = self.file_advanced_widget.isVisible()
        self.file_advanced_widget.setVisible(not is_visible)
        self.file_expand_btn.setText("⚙️ Advanced" if not is_visible else "⚙️ Hide")
        
    def toggle_messaging_server_fields(self):
        """Toggle visibility of messaging server controls."""
        is_visible = self.msg_server_widget.isVisible()
        self.msg_server_widget.setVisible(not is_visible)
        self.msg_expand_btn.setText("🖥️ Server" if not is_visible else "🖥️ Hide")
        
    def on_clear_network_fields(self):
        """Clear all network orchestration input fields."""
        self.net_ip_field.clear()
        self.net_user_field.clear()
        self.net_pass_field.clear()
        self.net_target_ip_field.clear()
        self.net_subnet_field.clear()
        self.net_gateway_field.clear()
        self.net_status_display.setText("🧹 All fields cleared!\n\nReady for new network configuration.")
        self.net_progress.setVisible(False)
    
    def _is_valid_ip(self, ip):
        """Validate IP address format."""
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            for part in parts:
                if not part.isdigit() or int(part) < 0 or int(part) > 255:
                    return False
            return True
        except:
            return False
    
    def _test_ssh_connection(self, ip, user, pwd):
        """Test SSH connectivity to the VM."""
        try:
            import paramiko
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username=user, password=pwd, timeout=10)
            ssh.close()
            return True
        except Exception:
            return False
    
    def _detect_remote_os(self, ip, user, pwd):
        """Detect the operating system of the remote VM."""
        try:
            import paramiko
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username=user, password=pwd, timeout=10)
            
            # Try Linux commands first
            try:
                stdin, stdout, stderr = ssh.exec_command('uname -s')
                os_type = stdout.read().decode().strip()
                if os_type:
                    ssh.close()
                    return f"Linux ({os_type})"
            except:
                pass
            
            # Try Windows commands
            try:
                stdin, stdout, stderr = ssh.exec_command('ver')
                os_version = stdout.read().decode().strip()
                if os_version:
                    ssh.close()
                    return "Windows"
            except:
                pass
            
            ssh.close()
            return "Unknown"
        except Exception:
            return None
    
    def _configure_linux_network(self, ip, user, pwd, target_ip, subnet, gateway):
        """Configure Linux VM network interface."""
        try:
            import paramiko
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username=user, password=pwd, timeout=10)
            
            # Get network interface name
            stdin, stdout, stderr = ssh.exec_command("ip route | grep default | awk '{print $5}' | head -1")
            interface = stdout.read().decode().strip()
            if not interface:
                interface = "eth0"  # Default fallback
            
            # Create network configuration
            if subnet and gateway:
                config_cmd = f"sudo ip addr add {target_ip}/{self._get_subnet_bits(subnet)} dev {interface} && sudo ip route add default via {gateway}"
            elif subnet:
                config_cmd = f"sudo ip addr add {target_ip}/{self._get_subnet_bits(subnet)} dev {interface}"
            else:
                config_cmd = f"sudo ip addr add {target_ip}/24 dev {interface}"
            
            stdin, stdout, stderr = ssh.exec_command(config_cmd)
            exit_status = stdout.channel.recv_exit_status()
            
            ssh.close()
            
            if exit_status == 0:
                return True, "Network configured successfully"
            else:
                return False, f"Network configuration failed with exit status {exit_status}"
                
        except Exception as e:
            return False, str(e)
    
    def _configure_windows_network(self, ip, user, pwd, target_ip, subnet, gateway):
        """Configure Windows VM network interface."""
        try:
            import paramiko
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username=user, password=pwd, timeout=10)
            
            # Get network adapter index
            stdin, stdout, stderr = ssh.exec_command("Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | Select-Object -First 1 | Select-Object -ExpandProperty InterfaceIndex")
            adapter_index = stdout.read().decode().strip()
            
            if not adapter_index:
                return False, "No active network adapter found"
            
            # Configure static IP
            if subnet and gateway:
                config_cmd = f"New-NetIPAddress -InterfaceIndex {adapter_index} -IPAddress {target_ip} -PrefixLength {self._get_subnet_bits(subnet)} -DefaultGateway {gateway}"
            else:
                config_cmd = f"New-NetIPAddress -InterfaceIndex {adapter_index} -IPAddress {target_ip} -PrefixLength 24"
            
            stdin, stdout, stderr = ssh.exec_command(f"powershell -Command '{config_cmd}'")
            exit_status = stdout.channel.recv_exit_status()
            
            ssh.close()
            
            if exit_status == 0:
                return True, "Network configured successfully"
            else:
                return False, f"Network configuration failed with exit status {exit_status}"
                
        except Exception as e:
            return False, str(e)
    
    def _reset_linux_network_dhcp(self, ip, user, pwd):
        """Reset Linux VM network to DHCP."""
        try:
            import paramiko
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username=user, password=pwd, timeout=10)
            
            # Get network interface name
            stdin, stdout, stderr = ssh.exec_command("ip route | grep default | awk '{print $5}' | head -1")
            interface = stdout.read().decode().strip()
            if not interface:
                interface = "eth0"
            
            # Reset to DHCP
            reset_cmd = f"sudo dhclient {interface}"
            stdin, stdout, stderr = ssh.exec_command(reset_cmd)
            exit_status = stdout.channel.recv_exit_status()
            
            ssh.close()
            
            if exit_status == 0:
                return True, "Network reset to DHCP successfully"
            else:
                return False, f"DHCP reset failed with exit status {exit_status}"
                
        except Exception as e:
            return False, str(e)
    
    def _reset_windows_network_dhcp(self, ip, user, pwd):
        """Reset Windows VM network to DHCP."""
        try:
            import paramiko
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username=user, password=pwd, timeout=10)
            
            # Get network adapter index
            stdin, stdout, stderr = ssh.exec_command("Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | Select-Object -First 1 | Select-Object -ExpandProperty InterfaceIndex")
            adapter_index = stdout.read().decode().strip()
            
            if not adapter_index:
                return False, "No active network adapter found"
            
            # Reset to DHCP
            reset_cmd = f"Set-NetIPInterface -InterfaceIndex {adapter_index} -Dhcp Enabled"
            stdin, stdout, stderr = ssh.exec_command(f"powershell -Command '{reset_cmd}'")
            exit_status = stdout.channel.recv_exit_status()
            
            ssh.close()
            
            if exit_status == 0:
                return True, "Network reset to DHCP successfully"
            else:
                return False, f"DHCP reset failed with exit status {exit_status}"
                
        except Exception as e:
            return False, str(e)
    
    def _get_subnet_bits(self, subnet):
        """Convert subnet mask to CIDR notation."""
        try:
            parts = subnet.split('.')
            binary = ''.join([bin(int(part))[2:].zfill(8) for part in parts])
            return binary.count('1')
        except:
            return 24  # Default to /24
    
    def on_start_msg_server(self):
        """Start the built-in TCP messaging server."""
        if self.msg_server and self.msg_server.is_alive():
            self.msg_server_status.setText("Server already running")
            return
        def on_message(addr, msg):
            self.message_log.append(f"From {addr[0]}:{addr[1]}: {msg}")
        try:
            self.msg_server = TCPServer(port=12345, on_message=on_message)
            self.msg_server.start()
            self.msg_server_status.setText("Server running on port 12345")
            self.message_log.append("✅ Messaging server started on port 12345")
            self.message_log.append("📡 Server is listening on 0.0.0.0:12345")
            self.message_log.append("💡 Other VMs can connect to this server using your IP address")
        except Exception as e:
            self.msg_server_status.setText(f"Error: {e}")
            self.message_log.append(f"❌ Failed to start server: {e}")

    def on_stop_msg_server(self):
        """Stop the built-in TCP messaging server."""
        if self.msg_server and self.msg_server.is_alive():
            try:
                self.msg_server.stop()
                self.msg_server.join(timeout=2)
                self.msg_server_status.setText("Server stopped")
            except Exception as e:
                self.msg_server_status.setText(f"Error: {e}")
        else:
            self.msg_server_status.setText("Server not running")

    def on_start_mon_agent(self):
        """Start the monitoring agent in a background thread."""
        if self.mon_agent and self.mon_agent.is_alive():
            self.mon_agent_status.setText("Agent already running")
            return
        def on_stats(stats):
            self.update_monitor_data(stats)
        try:
            self.mon_agent = MonitoringAgent(interval=2, on_stats=on_stats)
            self.mon_agent.start()
            self.mon_agent_status.setText("Agent running")
        except Exception as e:
            self.mon_agent_status.setText(f"Error: {e}")

    def on_stop_mon_agent(self):
        """Stop the monitoring agent."""
        if self.mon_agent and self.mon_agent.is_alive():
            try:
                self.mon_agent.stop()
                self.mon_agent.join(timeout=2)
                self.mon_agent_status.setText("Agent stopped")
            except Exception as e:
                self.mon_agent_status.setText(f"Error: {e}")
        else:
            self.mon_agent_status.setText("Agent not running")

    def update_env_info(self):
        """Update the environment info label with detected platform/tool."""
        if hasattr(self, 'vm_manager'):
            info = self.vm_manager.get_environment_info()
            self.env_info_label.setText(info)

    def load_machine_info_table(self):
        """Load and display the machine info in a table format."""
        machine_info = get_machine_info()
        
        # Clear existing rows
        self.machine_info_table.setRowCount(0)

        # Add rows for each property
        self.machine_info_table.insertRow(0)
        self.machine_info_table.setItem(0, 0, QTableWidgetItem("Hostname"))
        self.machine_info_table.setItem(0, 1, QTableWidgetItem(machine_info.get('hostname', 'Unknown')))

        self.machine_info_table.insertRow(1)
        self.machine_info_table.setItem(1, 0, QTableWidgetItem("Operating System"))
        self.machine_info_table.setItem(1, 1, QTableWidgetItem(f"{machine_info.get('os', 'Unknown')} {machine_info.get('os_version', '')}"))

        self.machine_info_table.insertRow(2)
        self.machine_info_table.setItem(2, 0, QTableWidgetItem("Architecture"))
        self.machine_info_table.setItem(2, 1, QTableWidgetItem(machine_info.get('architecture', 'Unknown')))

        self.machine_info_table.insertRow(3)
        self.machine_info_table.setItem(3, 0, QTableWidgetItem("Processor"))
        self.machine_info_table.setItem(3, 1, QTableWidgetItem(machine_info.get('processor', 'Unknown')))

        self.machine_info_table.insertRow(4)
        self.machine_info_table.setItem(4, 0, QTableWidgetItem("IP Address"))
        self.machine_info_table.setItem(4, 1, QTableWidgetItem(machine_info.get('ip', 'Unknown')))

        self.machine_info_table.insertRow(5)
        self.machine_info_table.setItem(5, 0, QTableWidgetItem("Environment Type"))
        self.machine_info_table.setItem(5, 1, QTableWidgetItem(f"{'VM' if machine_info.get('type') == 'vm' else 'Host'}"))

        if machine_info.get('vm_platform'):
            self.machine_info_table.insertRow(6)
            self.machine_info_table.setItem(6, 0, QTableWidgetItem("Running on"))
            self.machine_info_table.setItem(6, 1, QTableWidgetItem(machine_info.get('vm_platform')))

        # Auto-resize columns and rows
        self.machine_info_table.resizeColumnsToContents()
        self.machine_info_table.resizeRowsToContents()

    def setup_network_tab(self, tab):
        """Setup the dedicated Network Orchestrator tab - redesigned for compact layout."""
        layout = QVBoxLayout(tab)
        layout.setSpacing(3)  # Minimal spacing
        layout.setContentsMargins(3, 3, 3, 3)  # Minimal margins
        
        # Compact Header
        header_label = QLabel("🌐 Network Orchestrator Console")
        header_label.setStyleSheet("""
            color: white;
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2d5aa0, stop:1 #1e3f6b);
            padding: 8px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 14px;
            text-align: center;
        """)
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_label.setMaximumHeight(40)
        layout.addWidget(header_label)
        
        # Compact Description
        description = QLabel("Remotely configure network settings on VMs via SSH")
        description.setStyleSheet("color: #e0e0e0; font-size: 11px; padding: 4px; margin-bottom: 8px; font-weight: 500; text-align: center;")
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setMaximumHeight(20)
        layout.addWidget(description)
        
        # Compact Guide Section - Horizontal Layout
        guide_group = QGroupBox("📚 Quick Guide")
        guide_group.setStyleSheet("color: white; font-weight: bold; font-size: 11px; background-color: #2a2a2a; border-radius: 4px;")
        guide_layout = QHBoxLayout()
        guide_layout.setSpacing(8)
        
        # Step 1
        step1 = QLabel("1. Enter VM IP & SSH credentials")
        step1.setStyleSheet("color: #e0e0e0; font-size: 10px; font-weight: 500; padding: 4px; background-color: #353535; border-radius: 3px;")
        step1.setWordWrap(True)
        step1.setMaximumWidth(120)
        guide_layout.addWidget(step1)
        
        # Step 2
        step2 = QLabel("2. Set new network configuration")
        step2.setStyleSheet("color: #e0e0e0; font-size: 10px; font-weight: 500; padding: 4px; background-color: #353535; border-radius: 3px;")
        step2.setWordWrap(True)
        step2.setMaximumWidth(120)
        guide_layout.addWidget(step2)
        
        # Step 3
        step3 = QLabel("3. Execute network operations")
        step3.setStyleSheet("color: #e0e0e0; font-size: 10px; font-weight: 500; padding: 4px; background-color: #353535; border-radius: 3px;")
        step3.setWordWrap(True)
        step3.setMaximumWidth(120)
        guide_layout.addWidget(step3)
        
        guide_group.setLayout(guide_layout)
        layout.addWidget(guide_group)
        
        # Compact Network Status Display
        status_group = QGroupBox("Status")
        status_group.setStyleSheet("color: white; font-weight: bold; font-size: 11px; background-color: #2a2a2a; border-radius: 4px;")
        status_layout = QVBoxLayout()
        status_layout.setSpacing(2)
        
        self.net_status_display = QTextEdit()
        self.net_status_display.setReadOnly(True)
        self.net_status_display.setMaximumHeight(50)  # Much smaller height
        self.net_status_display.setStyleSheet("""
            QTextEdit {
                color: #f0f0f0;
                background-color: #2a2a2a;
                border-radius: 3px;
                padding: 4px;
                font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
                font-size: 10px;
                font-weight: 500;
            }
        """)
        self.net_status_display.setPlaceholderText("Network orchestration status will appear here...")
        status_layout.addWidget(self.net_status_display)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # Compact Input Fields Section - Two Columns
        input_group = QGroupBox("Configuration")
        input_group.setStyleSheet("color: white; font-weight: bold; font-size: 11px; background-color: #2a2a2a; border-radius: 4px;")
        input_layout = QHBoxLayout()
        input_layout.setSpacing(6)
        
        # Left column - VM connection details
        left_column = QGroupBox("VM Connection")
        left_column.setStyleSheet("color: #e0e0e0; font-weight: 500; font-size: 10px; background-color: #353535; border-radius: 3px;")
        left_layout = QVBoxLayout()
        left_layout.setSpacing(2)
        
        # VM IP
        left_layout.addWidget(QLabel("VM IP:"))
        self.net_ip_field = QLineEdit()
        self.net_ip_field.setPlaceholderText("192.168.1.100")
        self.net_ip_field.setStyleSheet("""
            QLineEdit {
                color: #f0f0f0; 
                background-color: #2a2a2a; 
                padding: 3px; 
                font-weight: 500;
                font-size: 10px;
            }
            QLineEdit::placeholder-text {
                color: #a0a0a0;
                font-style: italic;
            }
        """)
        self.net_ip_field.setToolTip("Enter the IP address of the VM you want to configure")
        self.net_ip_field.setMaximumHeight(22)  # Much smaller height
        left_layout.addWidget(self.net_ip_field)
        
        # Username
        left_layout.addWidget(QLabel("Username:"))
        self.net_user_field = QLineEdit()
        self.net_user_field.setPlaceholderText("root")
        self.net_user_field.setStyleSheet("""
            QLineEdit {
                color: #f0f0f0; 
                background-color: #2a2a2a; 
                padding: 3px; 
                font-weight: 500;
                font-size: 10px;
            }
            QLineEdit::placeholder-text {
                color: #a0a0a0;
                font-style: italic;
            }
        """)
        self.net_user_field.setToolTip("Enter the SSH username for the VM")
        self.net_user_field.setMaximumHeight(22)  # Much smaller height
        left_layout.addWidget(self.net_user_field)
        
        # Password
        left_layout.addWidget(QLabel("Password:"))
        self.net_pass_field = QLineEdit()
        self.net_pass_field.setPlaceholderText("SSH Password")
        self.net_pass_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.net_pass_field.setStyleSheet("""
            QLineEdit {
                color: #f0f0f0; 
                background-color: #2a2a2a; 
                padding: 3px; 
                font-weight: 500;
                font-size: 10px;
            }
            QLineEdit::placeholder-text {
                color: #a0a0a0;
                font-style: italic;
            }
        """)
        self.net_pass_field.setToolTip("Enter the SSH password for the VM")
        self.net_pass_field.setMaximumHeight(22)  # Much smaller height
        left_layout.addWidget(self.net_pass_field)
        
        left_column.setLayout(left_layout)
        
        # Right column - Network configuration
        right_column = QGroupBox("Network Settings")
        right_column.setStyleSheet("color: #e0e0e0; font-weight: 500; font-size: 10px; background-color: #353535; border-radius: 3px;")
        right_layout = QVBoxLayout()
        right_layout.setSpacing(2)
        
        # New IP
        right_layout.addWidget(QLabel("New IP:"))
        self.net_target_ip_field = QLineEdit()
        self.net_target_ip_field.setPlaceholderText("192.168.1.200")
        self.net_target_ip_field.setStyleSheet("""
            QLineEdit {
                color: #f0f0f0; 
                background-color: #2a2a2a; 
                padding: 3px; 
                font-weight: 500;
                font-size: 10px;
            }
            QLineEdit::placeholder-text {
                color: #a0a0a0;
                font-style: italic;
            }
        """)
        self.net_target_ip_field.setToolTip("Enter the new static IP address you want to assign to the VM")
        self.net_target_ip_field.setMaximumHeight(22)  # Much smaller height
        right_layout.addWidget(self.net_target_ip_field)
        
        # Subnet
        right_layout.addWidget(QLabel("Subnet:"))
        self.net_subnet_field = QLineEdit()
        self.net_subnet_field.setPlaceholderText("255.255.255.0")
        self.net_subnet_field.setStyleSheet("""
            QLineEdit {
                color: #f0f0f0; 
                background-color: #2a2a2a; 
                padding: 3px; 
                font-weight: 500;
                font-size: 10px;
            }
            QLineEdit::placeholder-text {
                color: #a0a0a0;
                font-style: italic;
            }
        """)
        self.net_subnet_field.setToolTip("Enter the subnet mask for the network")
        self.net_subnet_field.setMaximumHeight(22)  # Much smaller height
        right_layout.addWidget(self.net_subnet_field)
        
        # Gateway
        right_layout.addWidget(QLabel("Gateway:"))
        self.net_gateway_field = QLineEdit()
        self.net_gateway_field.setPlaceholderText("192.168.1.1")
        self.net_gateway_field.setStyleSheet("""
            QLineEdit {
                color: #f0f0f0; 
                background-color: #2a2a2a; 
                padding: 3px; 
                font-weight: 500;
                font-size: 10px;
            }
            QLineEdit::placeholder-text {
                color: #a0a0a0;
                font-style: italic;
            }
        """)
        self.net_gateway_field.setToolTip("Enter the gateway IP address for the network")
        self.net_gateway_field.setMaximumHeight(22)  # Much smaller height
        right_layout.addWidget(self.net_gateway_field)
        
        right_column.setLayout(right_layout)
        
        input_layout.addWidget(left_column)
        input_layout.addWidget(right_column)
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        # Compact Action Buttons Section
        button_group = QGroupBox("Operations")
        button_group.setStyleSheet("color: white; font-weight: bold; font-size: 11px; background-color: #2a2a2a; border-radius: 4px;")
        button_layout = QHBoxLayout()
        button_layout.setSpacing(4)
        
        # Test Connection Button
        test_conn_btn = QPushButton("🔍 Test SSH")
        test_conn_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #2d5aa0;
                padding: 4px 8px;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #4a7bc8;
            }
            QPushButton:pressed {
                background-color: #1e3f6b;
            }
        """)
        test_conn_btn.setToolTip("Test SSH connectivity to the VM before making changes")
        test_conn_btn.setMaximumHeight(24)  # Much smaller height
        test_conn_btn.clicked.connect(self.on_test_ssh_connection)
        button_layout.addWidget(test_conn_btn)
        
        # Assign Static IP Button
        net_assign_btn = QPushButton("🌐 Set IP")
        net_assign_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #28a745;
                padding: 4px 8px;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #34ce57;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        net_assign_btn.setToolTip("Assign a static IP address to the VM")
        net_assign_btn.setMaximumHeight(24)  # Much smaller height
        net_assign_btn.clicked.connect(self.on_assign_static_ip_clicked)
        button_layout.addWidget(net_assign_btn)
        
        # Reset Network Button
        reset_net_btn = QPushButton("🔄 DHCP")
        reset_net_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #ffc107;
                padding: 4px 8px;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #ffca2c;
            }
            QPushButton:pressed {
                background-color: #e0a800;
            }
        """)
        reset_net_btn.setToolTip("Reset the VM's network configuration to use DHCP")
        reset_net_btn.setMaximumHeight(24)  # Much smaller height
        reset_net_btn.clicked.connect(self.on_reset_network_dhcp)
        button_layout.addWidget(reset_net_btn)
        
        # Clear Fields Button
        clear_btn = QPushButton("🧹 Clear")
        clear_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #6c757d;
                padding: 4px 8px;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #868e96;
            }
            QPushButton:pressed {
                background-color: #545b62;
            }
        """)
        clear_btn.setToolTip("Clear all input fields")
        clear_btn.setMaximumHeight(24)  # Much smaller height
        clear_btn.clicked.connect(self.on_clear_network_fields)
        button_layout.addWidget(clear_btn)
        
        button_group.setLayout(button_layout)
        layout.addWidget(button_group)
        
        # Compact Progress indicator
        progress_group = QGroupBox("Progress")
        progress_group.setStyleSheet("color: white; font-weight: bold; font-size: 11px; background-color: #2a2a2a; border-radius: 4px;")
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(2)
        
        self.net_progress = QProgressBar()
        self.net_progress.setVisible(False)
        self.net_progress.setMaximumHeight(18)  # Much smaller height
        self.net_progress.setStyleSheet("""
            QProgressBar {
                border-radius: 3px;
                text-align: center;
                color: white;
                font-size: 9px;
            }
            QProgressBar::chunk {
                background-color: #28a745;
                border-radius: 2px;
            }
        """)
        progress_layout.addWidget(self.net_progress)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # Compact Technical Details Section
        tech_group = QGroupBox("🔧 Technical Info")
        tech_group.setStyleSheet("color: white; font-weight: bold; font-size: 11px; background-color: #2a2a2a; border-radius: 4px;")
        tech_layout = QHBoxLayout()
        tech_layout.setSpacing(8)
        
        # Port information
        port_info = QLabel("📡 SSH: Port 22")
        port_info.setStyleSheet("color: #17a2b8; font-weight: bold; font-size: 10px; padding: 3px; background-color: #353535; border-radius: 2px;")
        tech_layout.addWidget(port_info)
        
        # Supported OS info
        os_info = QLabel("💻 Linux & Windows")
        os_info.setStyleSheet("color: #28a745; font-weight: bold; font-size: 10px; padding: 3px; background-color: #353535; border-radius: 2px;")
        tech_layout.addWidget(os_info)
        
        # Security info
        security_info = QLabel("🔒 SSH Encrypted")
        security_info.setStyleSheet("color: #dc3545; font-weight: bold; font-size: 10px; padding: 3px; background-color: #353535; border-radius: 2px;")
        tech_layout.addWidget(security_info)
        
        tech_group.setLayout(tech_layout)
        layout.addWidget(tech_group)
        
        # Add stretch to push everything to the top
        layout.addStretch()

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QWidget {
            color: white;
            font-size: 10px;
        }
        QLabel, QLineEdit, QPushButton, QGroupBox, QTextEdit, QComboBox, QProgressBar, QTabWidget, QMainWindow {
            color: white;
        }
        QLabel {
            color: white;
            font-size: 10px;
        }
        QLineEdit {
            color: white;
            background-color: #2a2a2a;
            font-size: 10px;
        }
        QTextEdit {
            color: white;
            background-color: #2a2a2a;
            font-size: 10px;
        }
        QGroupBox {
            font-size: 11px;
            font-weight: bold;
            margin-top: 6px;
            padding-top: 6px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 6px;
            padding: 0 4px 0 4px;
            font-size: 11px;
        }
        QPushButton {
            font-size: 10px;
        }
        QComboBox {
            font-size: 10px;
        }
        QProgressBar {
            font-size: 9px;
        }
    """)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 