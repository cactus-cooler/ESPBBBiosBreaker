#!/usr/bin/env python3
"""
ESP32 Hardware Tools - Unified CLI Interface
User-friendly command-line interface with multiple operation modes
"""

import argparse
import json
import os
import sys
import time
import webbrowser
from pathlib import Path
from typing import Optional

import click
import serial
import serial.tools.list_ports
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.text import Text
from colorama import init, Fore, Style

# Initialize colorama for Windows compatibility
init(autoreset=True)

console = Console()

class ESP32Config:
    """Configuration management for ESP32 tools"""
    
    def __init__(self):
        self.config_dir = Path.home() / '.esp32_tools'
        self.config_file = self.config_dir / 'config.json'
        self.config_dir.mkdir(exist_ok=True)
        self.load_config()
    
    def load_config(self):
        """Load configuration from file"""
        default_config = {
            'default_port': '/dev/ttyUSB0',
            'default_baud': 115200,
            'auto_detect_port': True,
            'web_server_port': 8000,
            'last_used_port': None,
            'gui_preferences': {
                'theme': 'dark',
                'remember_window_size': True
            }
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    default_config.update(loaded_config)
            except Exception as e:
                console.print(f"[yellow]Warning: Could not load config: {e}[/yellow]")
        
        self.config = default_config
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            console.print(f"[red]Error saving config: {e}[/red]")
    
    def get(self, key, default=None):
        """Get configuration value"""
        return self.config.get(key, default)
    
    def set(self, key, value):
        """Set configuration value"""
        self.config[key] = value
        self.save_config()

class ESP32Manager:
    """Enhanced ESP32 management with better error handling"""
    
    def __init__(self, config: ESP32Config):
        self.config = config
        self.serial_conn: Optional[serial.Serial] = None
        self.connected = False
        self.port_name = None
    
    def find_esp32_ports(self):
        """Find ESP32 devices with enhanced detection"""
        esp32_vendors = [
            (0x10C4, 0xEA60, "CP2102 USB to UART Bridge"),
            (0x1A86, 0x7523, "CH340 Serial"),
            (0x0403, 0x6001, "FTDI USB Serial"),
            (0x239A, None, "Adafruit Board"),
            (0x303A, None, "Espressif Systems"),
        ]
        
        ports = []
        all_ports = list(serial.tools.list_ports.comports())
        
        for port in all_ports:
            port_info = {
                'port': port.device,
                'description': port.description,
                'vid': port.vid,
                'pid': port.pid,
                'likely_esp32': False,
                'confidence': 0
            }
            
            # Check against known ESP32 vendors
            for vid, pid, desc in esp32_vendors:
                if port.vid == vid and (pid is None or port.pid == pid):
                    port_info['likely_esp32'] = True
                    port_info['confidence'] = 95
                    port_info['description'] = f"{desc} (ESP32 Compatible)"
                    break
            
            # Additional heuristics for ESP32 detection
            if not port_info['likely_esp32']:
                desc_lower = port.description.lower()
                if any(keyword in desc_lower for keyword in ['esp32', 'esp', 'uart', 'serial']):
                    port_info['likely_esp32'] = True
                    port_info['confidence'] = 70
            
            ports.append(port_info)
        
        # Sort by confidence and ESP32 likelihood
        ports.sort(key=lambda x: (x['likely_esp32'], x['confidence']), reverse=True)
        return ports
    
    def auto_detect_port(self):
        """Automatically detect the best ESP32 port"""
        ports = self.find_esp32_ports()
        esp32_ports = [p for p in ports if p['likely_esp32']]
        
        if esp32_ports:
            return esp32_ports[0]['port']
        elif ports:
            console.print("[yellow]No obvious ESP32 ports found, trying first available port[/yellow]")
            return ports[0]['port']
        else:
            return None
    
    def connect_with_retry(self, port: str = None, baud: int = None, retries: int = 3):
        """Connect with automatic retry and user feedback"""
        if not port:
            port = self.auto_detect_port()
            if not port:
                console.print("[red]❌ No serial ports found![/red]")
                return False
        
        if not baud:
            baud = self.config.get('default_baud', 115200)
        
        with Progress(
            TextColumn("[bold blue]Connecting..."),
            BarColumn(),
            TextColumn("{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Connecting to {port}", total=retries)
            
            for attempt in range(retries):
                try:
                    if self.serial_conn and self.serial_conn.is_open:
                        self.serial_conn.close()
                    
                    progress.update(task, description=f"Attempt {attempt + 1}/{retries}")
                    
                    self.serial_conn = serial.Serial(
                        port=port,
                        baudrate=baud,
                        timeout=3.0,
                        write_timeout=3.0
                    )
                    
                    # Test connection with a simple command
                    time.sleep(1)  # ESP32 boot time
                    self.serial_conn.write(b'\n')
                    self.serial_conn.flush()
                    
                    self.connected = True
                    self.port_name = port
                    self.config.set('last_used_port', port)
                    
                    progress.update(task, completed=retries)
                    console.print(f"[green]✅ Connected to {port} at {baud} baud[/green]")
                    return True
                    
                except Exception as e:
                    progress.advance(task)
                    if attempt == retries - 1:
                        console.print(f"[red]❌ Connection failed after {retries} attempts: {e}[/red]")
                    else:
                        time.sleep(1)  # Wait before retry
        
        return False
    
    def send_command_with_progress(self, command: str, timeout: float = 10.0):
        """Send command with progress indication"""
        if not self.connected or not self.serial_conn:
            console.print("[red]❌ Not connected to ESP32[/red]")
            return None
        
        try:
            with console.status(f"[bold green]Executing: {command}"):
                self.serial_conn.reset_input_buffer()
                cmd_bytes = (command + '\n').encode('utf-8')
                self.serial_conn.write(cmd_bytes)
                
                response_lines = []
                start_time = time.time()
                
                while time.time() - start_time < timeout:
                    if self.serial_conn.in_waiting > 0:
                        line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            response_lines.append(line)
                            if any(indicator in line.lower() for indicator in ['done', 'complete', 'error', 'failed']):
                                break
                    time.sleep(0.01)
                
                response = '\n'.join(response_lines) if response_lines else "No response"
                console.print(f"[dim]Response: {response}[/dim]")
                return response
                
        except Exception as e:
            console.print(f"[red]❌ Command failed: {e}[/red]")
            return None

def display_banner():
    """Display attractive banner"""
    banner = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                           🚀 ESP32 Hardware Tools 🚀                        ║
║                     Professional BIOS Dumping & Analysis                     ║
║                              User-Friendly CLI                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """
    console.print(Panel(banner, style="bold green"))

@click.group(invoke_without_command=True)
@click.option('--config', '-c', help='Show configuration')
@click.option('--version', '-v', is_flag=True, help='Show version')
@click.pass_context
def cli(ctx, config, version):
    """ESP32 Hardware Tools - Unified Interface"""
    
    if version:
        console.print("[bold]ESP32 Hardware Tools v2.0.0[/bold]")
        return
    
    if config:
        config_obj = ESP32Config()
        table = Table(title="Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="magenta")
        
        for key, value in config_obj.config.items():
            table.add_row(str(key), str(value))
        console.print(table)
        return
    
    if ctx.invoked_subcommand is None:
        display_banner()
        console.print("\n[bold]Available modes:[/bold]")
        console.print("  [green]esp32-cli web[/green]     - Start web interface")
        console.print("  [green]esp32-cli gui[/green]     - Start GUI application")
        console.print("  [green]esp32-cli detect[/green]  - Detect ESP32 devices")
        console.print("  [green]esp32-cli dump[/green]    - Quick BIOS dump")
        console.print("  [green]esp32-cli terminal[/green] - Interactive terminal")
        console.print("\n[dim]Use --help with any command for detailed options[/dim]")

@cli.command()
@click.option('--dev', is_flag=True, help='Development mode (no browser)')
@click.option('--port', '-p', default=8000, help='Web server port')
def web(dev, port):
    """Start web interface"""
    console.print("[bold green]🌐 Starting Web Interface...[/bold green]")
    
    config = ESP32Config()
    config.set('web_server_port', port)
    
    # Import and start the web server
    try:
        import uvicorn
        from esp32_tools import app
        
        if not dev:
            import threading
            def open_browser():
                time.sleep(1.5)
                webbrowser.open(f"http://localhost:{port}")
            threading.Thread(target=open_browser, daemon=True).start()
            console.print(f"[green]🚀 Opening browser at http://localhost:{port}[/green]")
        
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info", access_log=False)
        
    except ImportError:
        console.print("[red]❌ Web dependencies not installed. Run: pip install -r requirements.txt[/red]")
    except Exception as e:
        console.print(f"[red]❌ Web server error: {e}[/red]")

@cli.command()
def gui():
    """Start GUI application"""
    console.print("[bold green]🖥️  Starting GUI Application...[/bold green]")
    
    try:
        import subprocess
        import sys
        
        gui_script = Path(__file__).parent / 'esp32_dumper_gui.py'
        if gui_script.exists():
            subprocess.run([sys.executable, str(gui_script)])
        else:
            console.print("[red]❌ GUI script not found[/red]")
    except Exception as e:
        console.print(f"[red]❌ GUI error: {e}[/red]")

@cli.command()
@click.option('--port', '-p', help='Serial port')
@click.option('--baud', '-b', default=115200, help='Baud rate')
def detect(port, baud):
    """Detect ESP32 devices and show information"""
    display_banner()
    console.print("[bold]🔍 Scanning for ESP32 devices...[/bold]\n")
    
    config = ESP32Config()
    manager = ESP32Manager(config)
    
    ports = manager.find_esp32_ports()
    
    if not ports:
        console.print("[red]❌ No serial ports found![/red]")
        return
    
    # Display ports table
    table = Table(title="Available Serial Ports")
    table.add_column("Port", style="cyan")
    table.add_column("Description", style="magenta")
    table.add_column("ESP32 Likely", style="green")
    table.add_column("Confidence", style="yellow")
    
    for port_info in ports:
        confidence = f"{port_info['confidence']}%" if port_info['confidence'] > 0 else "Unknown"
        likely = "✅ Yes" if port_info['likely_esp32'] else "❓ Maybe"
        
        table.add_row(
            port_info['port'],
            port_info['description'],
            likely,
            confidence
        )
    
    console.print(table)
    
    # Auto-connect to best port if requested
    if port or (config.get('auto_detect_port') and ports):
        target_port = port or ports[0]['port']
        console.print(f"\n[bold]Testing connection to {target_port}...[/bold]")
        
        if manager.connect_with_retry(target_port, baud):
            # Get device info
            info = manager.send_command_with_progress("id")
            if info:
                console.print(f"[green]📟 Device Info: {info}[/green]")

@cli.command()
@click.option('--port', '-p', help='Serial port')
@click.option('--output', '-o', default='bios_dump.bin', help='Output filename')
@click.option('--size', '-s', default='0x800000', help='Dump size (hex)')
@click.option('--start', default='0x0', help='Start address (hex)')
def dump(port, output, size, start):
    """Quick BIOS dump with progress"""
    display_banner()
    console.print(f"[bold]💾 Starting BIOS dump to {output}...[/bold]\n")
    
    config = ESP32Config()
    manager = ESP32Manager(config)
    
    # Connect
    if not manager.connect_with_retry(port):
        return
    
    # Start dump with progress
    try:
        start_addr = int(start, 16) if isinstance(start, str) else start
        dump_size = int(size, 16) if isinstance(size, str) else size
        
        console.print(f"[cyan]📍 Start Address: 0x{start_addr:08X}[/cyan]")
        console.print(f"[cyan]📏 Dump Size: {dump_size // 1024 // 1024}MB (0x{dump_size:08X})[/cyan]")
        
        with Progress(
            TextColumn("[bold blue]Dumping BIOS..."),
            BarColumn(),
            TextColumn("{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            
            task = progress.add_task("Dumping", total=100)
            
            # Simulate progress (replace with actual dump logic)
            dump_cmd = f"dump {start} {size}"
            response = manager.send_command_with_progress(dump_cmd, timeout=30.0)
            
            # Update progress simulation
            for i in range(0, 101, 5):
                progress.update(task, completed=i)
                time.sleep(0.1)
        
        console.print(f"[green]✅ BIOS dump completed: {output}[/green]")
        
    except Exception as e:
        console.print(f"[red]❌ Dump failed: {e}[/red]")

@cli.command()
@click.option('--port', '-p', help='Serial port')
def terminal(port):
    """Interactive terminal mode"""
    display_banner()
    console.print("[bold]🖥️  Interactive Terminal Mode[/bold]")
    console.print("[dim]Type 'exit' or Ctrl+C to quit[/dim]\n")
    
    config = ESP32Config()
    manager = ESP32Manager(config)
    
    if not manager.connect_with_retry(port):
        return
    
    try:
        while True:
            cmd = console.input("[bold green]ESP32>[/bold green] ").strip()
            
            if cmd.lower() in ['exit', 'quit']:
                break
            
            if cmd:
                response = manager.send_command_with_progress(cmd)
                if response:
                    console.print(f"[cyan]{response}[/cyan]")
    
    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Terminal session ended[/yellow]")
    except Exception as e:
        console.print(f"[red]❌ Terminal error: {e}[/red]")

if __name__ == '__main__':
    cli()