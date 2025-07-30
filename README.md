# 🚀 ESP32 Hardware Tools

**Professional BIOS Dumping & Hardware Analysis Suite**

A comprehensive, user-friendly toolkit for ESP32-based hardware analysis with multiple interfaces: Web UI, Desktop GUI, and powerful CLI tools.

---

## ✨ Features

### 🎯 **Multiple Interfaces**
- **🌐 Web Interface** - Modern browser-based GUI (recommended)
- **🖥️ Desktop GUI** - Native application with Tkinter
- **⚡ CLI Tools** - Powerful command-line interface
- **🔧 Interactive Terminal** - Direct ESP32 communication

### 🔍 **Smart Detection**
- **Auto-discovery** of ESP32 devices
- **Enhanced USB vendor detection** (CP2102, CH340, FTDI, etc.)
- **Confidence scoring** for device identification
- **Real-time connection status**

### 💾 **Advanced Dumping**
- **Full BIOS dumps** with progress indicators
- **Custom address ranges** and sizes
- **Automatic retry logic** for reliability
- **Multiple output formats**

### 🛡️ **User-Friendly Design**
- **Colorful terminal output** with rich formatting
- **Progress bars** and status indicators
- **Automatic dependency management**
- **Smart error handling** with helpful suggestions
- **Configuration persistence**

---

## 🏗️ Project Structure

```
esp32_bios_dumper/
├── tools/                          # Python interface tools
│   ├── esp32_launcher.sh           # 🚀 Main launcher (START HERE)
│   ├── esp32_cli.py               # ⚡ CLI interface
│   ├── esp32_tools.py             # 🌐 Web server
│   ├── esp32_dumper_gui.py        # 🖥️ Desktop GUI
│   ├── requirements.txt           # 📦 Dependencies
│   └── venv/                      # 🐍 Python environment
├── firmware/                      # ESP32 C firmware
│   ├── main/                      # Firmware source
│   ├── CMakeLists.txt            # Build configuration
│   └── sdkconfig                 # ESP-IDF settings
└── README.md                     # 📖 This file
```

---

## 🚀 Quick Start

### **Method 1: Interactive Launcher (Recommended)**

```bash
# Navigate to tools directory
cd esp32_bios_dumper/tools

# Run the enhanced launcher
./esp32_launcher.sh
```

The launcher will:
- ✅ Check all dependencies automatically
- 📦 Set up Python virtual environment
- 🔌 Verify USB permissions
- 🎯 Present a user-friendly menu

### **Method 2: Direct Commands**

```bash
# Web Interface (opens browser automatically)
./esp32_launcher.sh --web

# Desktop GUI
./esp32_launcher.sh --gui

# Command Line Interface
./esp32_launcher.sh --cli

# Quick device detection
./esp32_launcher.sh --detect
```

---

## 🎯 Usage Modes

### 🌐 **Web Interface** (Recommended)
- **Best for**: General use, remote access, modern UI
- **Access**: `http://localhost:8000`
- **Features**: 
  - Real-time WebSocket communication
  - Progress indicators
  - Device management
  - Custom commands

```bash
./esp32_launcher.sh --web
# Browser opens automatically
```

### 🖥️ **Desktop GUI**
- **Best for**: Offline use, traditional desktop feel
- **Features**:
  - Native Tkinter interface
  - Tabbed layout
  - Real-time terminal
  - File management

```bash
./esp32_launcher.sh --gui
```

### ⚡ **CLI Tools**
- **Best for**: Automation, scripting, advanced users
- **Features**:
  - Rich terminal output
  - Progress bars
  - Batch operations
  - Configuration management

```bash
# Interactive CLI menu
python esp32_cli.py

# Direct commands
python esp32_cli.py detect           # Find devices
python esp32_cli.py dump --port /dev/ttyUSB0  # Quick dump
python esp32_cli.py terminal         # Interactive terminal
```

---

## 🔧 Advanced Configuration

### **Configuration File**
Settings are stored in `~/.esp32_tools/config.json`:

```json
{
  "default_port": "/dev/ttyUSB0",
  "default_baud": 115200,
  "auto_detect_port": true,
  "web_server_port": 8000,
  "last_used_port": "/dev/ttyUSB0"
}
```

### **View/Edit Configuration**
```bash
python esp32_cli.py --config
```

---

## 🐛 Troubleshooting

### **Common Issues & Solutions**

#### 🔌 **"Permission denied" on serial port**
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER
# Logout and login again
```

#### 📦 **Missing Python packages**
```bash
# The launcher handles this automatically, but manually:
cd tools
source venv/bin/activate
pip install -r requirements.txt
```

#### 🔍 **ESP32 not detected**
1. **Check USB cable** - Use a data cable, not charge-only
2. **Try different port** - ESP32 may appear on different ttyUSB/ttyACM
3. **Check device manager** - Verify USB drivers are installed
4. **Press reset** - Some ESP32 boards need reset to enter programming mode

#### 🌐 **Web interface not opening**
```bash
# Check if port 8000 is available
netstat -tulpn | grep :8000

# Use different port
python esp32_tools.py --port 8080
```

---

## 📚 Command Reference

### **CLI Commands**
```bash
# Device Operations
esp32_cli.py detect                    # Find ESP32 devices
esp32_cli.py detect --port /dev/ttyUSB0  # Test specific port

# BIOS Dumping
esp32_cli.py dump                      # Quick 8MB dump
esp32_cli.py dump --size 0x400000      # 4MB dump
esp32_cli.py dump --output my_bios.bin # Custom filename
esp32_cli.py dump --start 0x1000       # Custom start address

# Interactive Modes
esp32_cli.py terminal                  # Serial terminal
esp32_cli.py web                       # Web interface
esp32_cli.py gui                       # Desktop GUI

# Configuration
esp32_cli.py --config                  # View settings
esp32_cli.py --version                 # Show version
```

### **Web Interface Endpoints**
- `GET /` - Main interface
- `WebSocket /ws` - Real-time communication
- Commands: `list_ports`, `connect`, `send_command`, `dump_flash`

---

## 🔒 Security & Safety

### **Built-in Protections**
- ✅ **Input validation** on all commands
- ✅ **Timeout handling** prevents hangs
- ✅ **Connection retry logic** for reliability
- ✅ **Error boundaries** prevent crashes
- ✅ **Safe file operations** with proper error handling

### **Best Practices**
- 🔌 Always **disconnect safely** before unplugging
- 💾 **Backup original BIOS** before modifications
- ⚡ Use **proper power supply** for ESP32
- 🔒 **Verify dumps** with checksums when possible

---

## 🤝 Contributing

### **Development Setup**
```bash
# Clone and setup
git clone <repository>
cd esp32_bios_dumper/tools

# Install development dependencies
pip install -r requirements.txt
pip install black pytest flake8

# Run in development mode
./esp32_launcher.sh --web --dev
```

### **Code Style**
- Use **Black** for formatting
- Follow **PEP 8** guidelines
- Add **type hints** where possible
- Include **docstrings** for functions

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🙏 Acknowledgments

- **ESP32 Community** for hardware documentation
- **PySerial** for reliable serial communication
- **FastAPI** for modern web framework
- **Rich** for beautiful terminal output

---

## 📞 Support

### **Getting Help**
1. 📖 **Read this README** thoroughly
2. 🐛 **Check troubleshooting** section
3. 🔍 **Run diagnostics**: `./esp32_launcher.sh --detect`
4. 💬 **Open an issue** with detailed logs

### **Reporting Bugs**
Please include:
- Operating system and version
- Python version (`python --version`)
- Full error messages
- Steps to reproduce
- Hardware details (ESP32 model, USB adapter)

---

**Made with ❤️ for the ESP32 community**

*Happy hardware hacking! 🔧*