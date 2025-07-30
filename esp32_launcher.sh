#!/bin/bash
# ESP32 Hardware Tools - Enhanced Launcher Script
# User-friendly launcher with automatic setup and error handling

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Banner function
show_banner() {
    echo -e "${PURPLE}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${PURPLE}║${GREEN}                           🚀 ESP32 Hardware Tools 🚀                        ${PURPLE}║${NC}"
    echo -e "${PURPLE}║${CYAN}                     Professional BIOS Dumping & Analysis                     ${PURPLE}║${NC}"
    echo -e "${PURPLE}║${YELLOW}                              Enhanced Launcher                               ${PURPLE}║${NC}"
    echo -e "${PURPLE}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo
}

# Error handling function
handle_error() {
    echo -e "${RED}❌ Error: $1${NC}" >&2
    echo -e "${YELLOW}💡 Suggestion: $2${NC}" >&2
    exit 1
}

# Check dependencies
check_dependencies() {
    echo -e "${BLUE}🔍 Checking dependencies...${NC}"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        handle_error "Python 3 not found" "Install Python 3: sudo apt install python3"
    fi
    
    # Check if python3-venv is available
    if ! python3 -c "import venv" &>/dev/null; then
        echo -e "${YELLOW}⚠️  python3-venv not found, installing...${NC}"
        sudo apt update && sudo apt install -y python3-venv python3-full
        
        if [ $? -ne 0 ]; then
            handle_error "Failed to install python3-venv" "Run: sudo apt install python3-venv python3-full"
        fi
    fi
    
    echo -e "${GREEN}✅ Dependencies OK${NC}"
}

# Setup virtual environment
setup_venv() {
    if [ ! -d "venv" ]; then
        echo -e "${YELLOW}📦 Creating Python virtual environment...${NC}"
        python3 -m venv venv --system-site-packages
        
        if [ $? -ne 0 ]; then
            echo -e "${YELLOW}⚠️  Trying without system packages...${NC}"
            python3 -m venv venv
            
            if [ $? -ne 0 ]; then
                handle_error "Failed to create virtual environment" "Install python3-venv: sudo apt install python3-venv python3-full"
            fi
        fi
        
        echo -e "${GREEN}✅ Virtual environment created${NC}"
    fi
    
    echo -e "${BLUE}🔧 Activating virtual environment...${NC}"
    source venv/bin/activate
    
    # Verify we're in the virtual environment
    if [[ "$VIRTUAL_ENV" != "" ]]; then
        echo -e "${GREEN}✅ Virtual environment activated: $(basename $VIRTUAL_ENV)${NC}"
    else
        handle_error "Failed to activate virtual environment" "Check venv directory permissions"
    fi
    
    # Check if requirements are installed
    if [ -f "requirements.txt" ]; then
        echo -e "${BLUE}📥 Checking Python packages...${NC}"
        
        # Check if packages are installed in the virtual environment
        if ! python -c "import fastapi, uvicorn, serial, click, rich, colorama" &>/dev/null; then
            echo -e "${YELLOW}📦 Installing Python packages in virtual environment...${NC}"
            
            # Upgrade pip in virtual environment first
            python -m pip install --upgrade pip
            
            # Install packages in virtual environment
            python -m pip install -r requirements.txt
            
            if [ $? -ne 0 ]; then
                echo -e "${RED}❌ Failed to install packages. Trying alternative method...${NC}"
                
                # Try installing system packages if available
                echo -e "${CYAN}💡 Installing system packages as fallback...${NC}"
                sudo apt update
                sudo apt install -y python3-fastapi python3-uvicorn python3-serial python3-click python3-rich python3-colorama
                
                if [ $? -eq 0 ]; then
                    echo -e "${GREEN}✅ System packages installed successfully${NC}"
                else
                    handle_error "Failed to install Python packages" "Check internet connection or install manually: pip install fastapi uvicorn pyserial click rich colorama"
                fi
            else
                echo -e "${GREEN}✅ Packages installed in virtual environment${NC}"
            fi
        else
            echo -e "${GREEN}✅ All required packages are already installed${NC}"
        fi
    fi
}

# Check USB permissions
check_usb_permissions() {
    echo -e "${BLUE}🔌 Checking USB permissions...${NC}"
    
    # Check if user is in dialout group
    if ! groups | grep -q dialout; then
        echo -e "${YELLOW}⚠️  User not in dialout group${NC}"
        echo -e "${CYAN}Adding user to dialout group...${NC}"
        sudo usermod -a -G dialout $USER
        echo -e "${YELLOW}⚠️  You may need to logout/login for USB permissions to take effect${NC}"
    fi
    
    # Check for ESP32 devices
    if ls /dev/ttyUSB* /dev/ttyACM* &>/dev/null; then
        echo -e "${GREEN}✅ Serial devices found${NC}"
        ls -la /dev/ttyUSB* /dev/ttyACM* 2>/dev/null | head -3
    else
        echo -e "${YELLOW}⚠️  No obvious serial devices found${NC}"
        echo -e "${CYAN}💡 Make sure your ESP32 is connected${NC}"
    fi
}

# Show usage menu
show_menu() {
    echo -e "${CYAN}🎯 Select operation mode:${NC}"
    echo
    echo -e "${GREEN}1)${NC} 🌐 Web Interface    - Browser-based GUI (recommended)"
    echo -e "${GREEN}2)${NC} 🖥️  Desktop GUI      - Native application"
    echo -e "${GREEN}3)${NC} ⚡ CLI Tools        - Command-line interface"
    echo -e "${GREEN}4)${NC} 🔍 Quick Detect     - Find ESP32 devices"
    echo -e "${GREEN}5)${NC} 💾 Quick Dump       - Fast BIOS dump"
    echo -e "${GREEN}6)${NC} 🔧 Terminal Mode    - Interactive terminal"
    echo -e "${GREEN}7)${NC} 📁 Dump Manager     - View and organize dumps"
    echo -e "${GREEN}8)${NC} ⚙️  Configuration    - Settings and preferences"
    echo
    echo -e "${GREEN}0)${NC} 🚪 Exit"
    echo
}

# Main menu handler
handle_menu_choice() {
    case $1 in
        1)
            echo -e "${GREEN}🌐 Starting Web Interface...${NC}"
            echo -e "${CYAN}🚀 Interface will open at: http://localhost:8000${NC}"
            python esp32_tools.py
            ;;
        2)
            echo -e "${GREEN}🖥️  Starting Desktop GUI...${NC}"
            if [ -f "esp32_dumper_gui.py" ]; then
                python esp32_dumper_gui.py
            else
                echo -e "${RED}❌ GUI script not found${NC}"
            fi
            ;;
        3)
            echo -e "${GREEN}⚡ Starting CLI Tools...${NC}"
            if [ -f "esp32_cli.py" ]; then
                python esp32_cli.py
            else
                echo -e "${RED}❌ CLI script not found${NC}"
            fi
            ;;
        4)
            echo -e "${GREEN}🔍 Quick Device Detection...${NC}"
            if [ -f "esp32_cli.py" ]; then
                python esp32_cli.py detect
            else
                echo -e "${YELLOW}⚠️  CLI not available, using basic detection...${NC}"
                python -c "
import serial.tools.list_ports
print('📡 Available Serial Ports:')
for port in serial.tools.list_ports.comports():
    print(f'  {port.device} - {port.description}')
"
            fi
            ;;
        5)
            echo -e "${GREEN}💾 Quick BIOS Dump...${NC}"
            if [ -f "esp32_cli.py" ]; then
                python esp32_cli.py dump
            else
                echo -e "${RED}❌ CLI script required for quick dump${NC}"
            fi
            ;;
        6)
            echo -e "${GREEN}🔧 Terminal Mode...${NC}"
            if [ -f "esp32_cli.py" ]; then
                python esp32_cli.py terminal
            else
                echo -e "${RED}❌ CLI script required for terminal mode${NC}"
            fi
            ;;
        7)
            echo -e "${GREEN}📁 Dump Manager...${NC}"
            if [ -f "dump_manager.py" ]; then
                python dump_manager.py --list
            else
                echo -e "${RED}❌ Dump manager not available${NC}"
            fi
            ;;
        8)
            echo -e "${GREEN}⚙️  Configuration...${NC}"
            if [ -f "esp32_cli.py" ]; then
                python esp32_cli.py --config
            else
                echo -e "${YELLOW}💡 Configuration file location: ~/.esp32_tools/config.json${NC}"
            fi
            ;;
        0)
            echo -e "${CYAN}👋 Goodbye!${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Invalid choice${NC}"
            ;;
    esac
}

# Main execution
main() {
    show_banner
    
    # Handle command line arguments
    if [ $# -gt 0 ]; then
        case $1 in
            --web)
                setup_venv
                python esp32_tools.py
                exit 0
                ;;
            --gui)
                setup_venv
                python esp32_dumper_gui.py
                exit 0
                ;;
            --cli)
                setup_venv
                python esp32_cli.py
                exit 0
                ;;
            --detect)
                setup_venv
                python esp32_cli.py detect
                exit 0
                ;;
            --help|-h)
                echo "ESP32 Hardware Tools Launcher"
                echo
                echo "Usage: $0 [option]"
                echo
                echo "Options:"
                echo "  --web      Start web interface"
                echo "  --gui      Start desktop GUI"
                echo "  --cli      Start CLI tools"
                echo "  --detect   Quick device detection"
                echo "  --help     Show this help"
                echo
                echo "Run without arguments for interactive menu"
                exit 0
                ;;
        esac
    fi
    
    # Interactive mode
    check_dependencies
    setup_venv
    check_usb_permissions
    
    echo
    
    while true; do
        show_menu
        echo -n -e "${YELLOW}Enter your choice [1-8, 0 to exit]: ${NC}"
        read -r choice
        echo
        
        handle_menu_choice "$choice"
        
        echo
        echo -e "${CYAN}Press Enter to continue...${NC}"
        read -r
        clear
        show_banner
    done
}

# Run main function
main "$@"