#!/usr/bin/env python3
"""
ESP32 Hardware Tools - Local Web Server
Clean alternative to browser-based Web Serial API
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
import webbrowser
from pathlib import Path
from typing import Optional

import serial
import serial.tools.list_ports
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

# Configure logging for better debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ESP32Manager:
    def __init__(self):
        self.serial_conn: Optional[serial.Serial] = None
        self.connected = False
        self.port_name = None
        
    def find_esp32_ports(self):
        """Find available ESP32 serial ports with enhanced detection"""
        esp32_vendors = [
            (0x10C4, 0xEA60, "CP2102 USB to UART Bridge"),  # CP2102
            (0x1A86, 0x7523, "CH340 Serial"),              # CH340
            (0x0403, 0x6001, "FTDI USB Serial"),            # FTDI
            (0x239A, None, "Adafruit Board"),               # Adafruit
            (0x303A, None, "Espressif Systems"),            # ESP32-S3/C3
        ]
        
        ports = []
        all_ports = list(serial.tools.list_ports.comports())
        logger.info(f"Scanning {len(all_ports)} serial ports...")
        
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
                    ports.append(port_info)
                    break
            else:
                # Additional heuristics for ESP32 detection
                desc_lower = port.description.lower()
                if any(keyword in desc_lower for keyword in ['esp32', 'esp', 'uart', 'serial']):
                    port_info['likely_esp32'] = True
                    port_info['confidence'] = 70
                    ports.append(port_info)
                else:
                    # Include all ports but mark as uncertain
                    ports.append(port_info)
        
        # Sort by confidence and ESP32 likelihood
        ports.sort(key=lambda x: (x['likely_esp32'], x['confidence']), reverse=True)
        logger.info(f"Found {len([p for p in ports if p['likely_esp32']])} likely ESP32 ports")
        return ports
    
    def connect(self, port: str, baud: int = 115200, retries: int = 3) -> bool:
        """Connect to ESP32 on specified port with retry logic"""
        logger.info(f"Attempting to connect to {port} at {baud} baud...")
        
        for attempt in range(retries):
            try:
                if self.serial_conn and self.serial_conn.is_open:
                    self.serial_conn.close()
                    time.sleep(0.5)
                
                logger.info(f"Connection attempt {attempt + 1}/{retries}")
                
                self.serial_conn = serial.Serial(
                    port=port,
                    baudrate=baud,
                    timeout=3.0,
                    write_timeout=3.0,
                    rtscts=False,
                    dsrdtr=False
                )
                
                # Wait for ESP32 to initialize
                time.sleep(1.5)
                
                # Test connection with a simple command
                self.serial_conn.reset_input_buffer()
                self.serial_conn.write(b'\n')
                self.serial_conn.flush()
                time.sleep(0.5)
                
                # Try to read any response
                if self.serial_conn.in_waiting > 0:
                    response = self.serial_conn.read(self.serial_conn.in_waiting)
                    logger.info(f"Device responded: {response[:50]}...")
                
                self.connected = True
                self.port_name = port
                logger.info(f"✅ Successfully connected to {port}")
                return True
                
            except serial.SerialException as e:
                logger.warning(f"Serial error on attempt {attempt + 1}: {e}")
                if attempt < retries - 1:
                    time.sleep(1)
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                if attempt < retries - 1:
                    time.sleep(1)
        
        logger.error(f"❌ Failed to connect to {port} after {retries} attempts")
        self.connected = False
        return False
    
    def disconnect(self):
        """Disconnect from ESP32"""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        self.connected = False
        self.port_name = None
    
    def send_command(self, command: str, timeout: float = 10.0) -> str:
        """Send command to ESP32 and get response with enhanced error handling"""
        if not self.connected or not self.serial_conn:
            raise Exception("Not connected to ESP32")
        
        logger.debug(f"Sending command: {command}")
        
        try:
            # Clear input buffer
            self.serial_conn.reset_input_buffer()
            
            # Send command
            cmd_bytes = (command + '\n').encode('utf-8')
            bytes_written = self.serial_conn.write(cmd_bytes)
            self.serial_conn.flush()
            
            logger.debug(f"Sent {bytes_written} bytes")
            
            # Read response with timeout
            response_lines = []
            start_time = time.time()
            last_data_time = time.time()
            
            while time.time() - start_time < timeout:
                if self.serial_conn.in_waiting > 0:
                    try:
                        line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            response_lines.append(line)
                            last_data_time = time.time()
                            logger.debug(f"Received: {line}")
                            
                            # Check for command completion indicators
                            if any(indicator in line.lower() for indicator in 
                                  ['done', 'complete', 'error', 'failed', 'ok', 'ready']):
                                break
                    except UnicodeDecodeError as e:
                        logger.warning(f"Unicode decode error: {e}")
                        continue
                
                # Check for data timeout (no new data for 3 seconds)
                if time.time() - last_data_time > 3.0 and response_lines:
                    logger.debug("Data timeout reached, assuming command complete")
                    break
                    
                time.sleep(0.01)
            
            response = '\n'.join(response_lines) if response_lines else "No response received"
            logger.debug(f"Command response ({len(response_lines)} lines): {response[:100]}...")
            return response
            start_time = time.time()
            timeout = 10.0  # 10 second timeout
            
            while time.time() - start_time < timeout:
                if self.serial_conn.in_waiting > 0:
                    line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        response_lines.append(line)
                        # Check for command completion indicators
                        if any(indicator in line.lower() for indicator in ['done', 'complete', 'error', 'failed']):
                            break
                time.sleep(0.01)
            
            return '\n'.join(response_lines) if response_lines else "No response"
            
        except Exception as e:
            raise Exception(f"Command failed: {e}")


# Global ESP32 manager instance
esp32 = ESP32Manager()

# FastAPI app
app = FastAPI(title="ESP32 Hardware Tools", version="1.0.0")

# WebSocket connections
active_connections = []

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                # Remove dead connections
                self.active_connections.remove(connection)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await handle_websocket_message(data, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def handle_websocket_message(data: dict, websocket: WebSocket):
    """Handle incoming WebSocket messages"""
    command = data.get('command')
    
    try:
        if command == 'list_ports':
            ports = esp32.find_esp32_ports()
            await websocket.send_json({
                'type': 'ports_list',
                'data': ports
            })
            
        elif command == 'connect':
            port = data.get('port')
            baud = data.get('baud', 115200)
            success = esp32.connect(port, baud)
            
            await websocket.send_json({
                'type': 'connection_status',
                'connected': success,
                'port': port if success else None,
                'message': f"Connected to {port}" if success else "Connection failed"
            })
            
        elif command == 'disconnect':
            esp32.disconnect()
            await websocket.send_json({
                'type': 'connection_status',
                'connected': False,
                'port': None,
                'message': "Disconnected"
            })
            
        elif command == 'send_command':
            cmd = data.get('data', '')
            try:
                response = esp32.send_command(cmd)
                await websocket.send_json({
                    'type': 'command_response',
                    'command': cmd,
                    'response': response
                })
            except Exception as e:
                await websocket.send_json({
                    'type': 'error',
                    'message': str(e)
                })
                
        elif command == 'detect_chip':
            try:
                response = esp32.send_command('DETECT_CHIP')
                await websocket.send_json({
                    'type': 'chip_detected',
                    'data': response
                })
            except Exception as e:
                await websocket.send_json({
                    'type': 'error',
                    'message': f"Chip detection failed: {e}"
                })
                
        elif command == 'dump_flash':
            try:
                # Start flash dump with progress updates
                await websocket.send_json({
                    'type': 'dump_started',
                    'message': 'Starting flash dump...'
                })
                
                response = esp32.send_command('DUMP_FLASH')
                
                # Simulate progress updates (replace with real progress parsing)
                for progress in range(0, 101, 10):
                    await websocket.send_json({
                        'type': 'dump_progress',
                        'progress': progress
                    })
                    await asyncio.sleep(0.1)
                
                await websocket.send_json({
                    'type': 'dump_complete',
                    'data': response
                })
                
            except Exception as e:
                await websocket.send_json({
                    'type': 'error',
                    'message': f"Flash dump failed: {e}"
                })
                
    except Exception as e:
        await websocket.send_json({
            'type': 'error',
            'message': f"Command error: {e}"
        })

@app.get("/")
async def get_interface():
    """Serve the main interface"""
    html_content = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ESP32 Hardware Tools</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', monospace;
            background: linear-gradient(135deg, #0c1618 0%, #1a2732 100%);
            color: #e0e0e0;
            min-height: 100vh;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 { color: #00ff41; font-size: 2.5em; margin-bottom: 10px; }
        .status-bar {
            background: rgba(0,0,0,0.3);
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #00ff41;
        }
        .connected { border-left-color: #00ff41; }
        .disconnected { border-left-color: #ff4757; }
        .tools-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .tool-card {
            background: rgba(0,0,0,0.2);
            border: 1px solid #333;
            border-radius: 8px;
            padding: 20px;
            transition: all 0.3s ease;
        }
        .tool-card:hover { border-color: #00ff41; transform: translateY(-2px); }
        .tool-card h3 { color: #00ff41; margin-bottom: 10px; }
        .btn {
            background: linear-gradient(45deg, #1e3c72, #2a5298);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin: 5px;
            transition: all 0.3s ease;
        }
        .btn:hover { background: linear-gradient(45deg, #2a5298, #1e3c72); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .log-area {
            background: #000;
            color: #00ff41;
            font-family: 'Courier New', monospace;
            padding: 15px;
            border-radius: 5px;
            height: 300px;
            overflow-y: auto;
            font-size: 14px;
            border: 1px solid #333;
        }
        .progress-bar {
            width: 100%;
            height: 20px;
            background: #333;
            border-radius: 10px;
            overflow: hidden;
            margin: 10px 0;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #00ff41, #32ff7e);
            width: 0%;
            transition: width 0.3s ease;
        }
        select, input { 
            background: #333; 
            color: #e0e0e0; 
            border: 1px solid #555; 
            padding: 8px; 
            border-radius: 4px; 
            margin: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚡ ESP32 Hardware Tools</h1>
            <p>Native Python Interface - No Browser Bloat</p>
        </div>
        
        <div class="status-bar disconnected" id="statusBar">
            <strong>Status:</strong> <span id="statusText">Disconnected</span>
            <div style="margin-top: 10px;">
                <select id="portSelect">
                    <option value="">Select Port...</option>
                </select>
                <button class="btn" onclick="connectESP32()" id="connectBtn">Connect</button>
                <button class="btn" onclick="disconnectESP32()" id="disconnectBtn" disabled>Disconnect</button>
                <button class="btn" onclick="refreshPorts()">Refresh Ports</button>
            </div>
        </div>
        
        <div class="tools-grid">
            <div class="tool-card">
                <h3>🔍 SPI Flash Tools</h3>
                <p>Detect and dump SPI flash chips</p>
                <button class="btn" onclick="detectChip()" disabled id="detectBtn">Detect Chip</button>
                <button class="btn" onclick="dumpFlash()" disabled id="dumpBtn">Dump Flash</button>
                <div class="progress-bar" id="progressBar" style="display: none;">
                    <div class="progress-fill" id="progressFill"></div>
                </div>
            </div>
            
            <div class="tool-card">
                <h3>⚙️ ESP32 Management</h3>
                <p>Device control and information</p>
                <button class="btn" onclick="getDeviceInfo()" disabled id="infoBtn">Device Info</button>
                <button class="btn" onclick="resetDevice()" disabled id="resetBtn">Reset</button>
            </div>
            
            <div class="tool-card">
                <h3>🔧 Custom Commands</h3>
                <p>Send custom commands to ESP32</p>
                <input type="text" id="customCmd" placeholder="Enter command..." style="width: 200px;">
                <button class="btn" onclick="sendCustomCommand()" disabled id="customBtn">Send</button>
            </div>
        </div>
        
        <div class="tool-card">
            <h3>📋 Console Log</h3>
            <div class="log-area" id="logArea">ESP32 Hardware Tools started...\n</div>
        </div>
    </div>

    <script>
        let ws = null;
        let connected = false;
        
        // Initialize WebSocket connection
        function initWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
            
            ws.onopen = function() {
                addLog('WebSocket connected');
                refreshPorts();
            };
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            };
            
            ws.onclose = function() {
                addLog('WebSocket disconnected');
                setTimeout(initWebSocket, 3000); // Reconnect after 3 seconds
            };
        }
        
        function handleWebSocketMessage(data) {
            switch(data.type) {
                case 'ports_list':
                    updatePortsList(data.data);
                    break;
                case 'connection_status':
                    updateConnectionStatus(data.connected, data.message);
                    break;
                case 'command_response':
                    addLog(`Command: ${data.command}`);
                    addLog(`Response: ${data.response}`);
                    break;
                case 'chip_detected':
                    addLog(`Chip Detection: ${data.data}`);
                    break;
                case 'dump_started':
                    addLog(data.message);
                    document.getElementById('progressBar').style.display = 'block';
                    break;
                case 'dump_progress':
                    updateProgress(data.progress);
                    break;
                case 'dump_complete':
                    addLog(`Dump Complete: ${data.data}`);
                    document.getElementById('progressBar').style.display = 'none';
                    break;
                case 'error':
                    addLog(`Error: ${data.message}`, 'error');
                    break;
            }
        }
        
        function sendWebSocketMessage(message) {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify(message));
            }
        }
        
        function addLog(message, type = 'info') {
            const logArea = document.getElementById('logArea');
            const timestamp = new Date().toLocaleTimeString();
            const color = type === 'error' ? '#ff4757' : '#00ff41';
            logArea.innerHTML += `<span style="color: ${color}">[${timestamp}] ${message}</span>\n`;
            logArea.scrollTop = logArea.scrollHeight;
        }
        
        function updatePortsList(ports) {
            const select = document.getElementById('portSelect');
            select.innerHTML = '<option value="">Select Port...</option>';
            
            ports.forEach(port => {
                const option = document.createElement('option');
                option.value = port.port;
                option.textContent = `${port.port} - ${port.description}`;
                select.appendChild(option);
            });
            
            addLog(`Found ${ports.length} ESP32 port(s)`);
        }
        
        function updateConnectionStatus(isConnected, message) {
            connected = isConnected;
            const statusBar = document.getElementById('statusBar');
            const statusText = document.getElementById('statusText');
            const connectBtn = document.getElementById('connectBtn');
            const disconnectBtn = document.getElementById('disconnectBtn');
            
            statusText.textContent = message;
            statusBar.className = `status-bar ${isConnected ? 'connected' : 'disconnected'}`;
            
            connectBtn.disabled = isConnected;
            disconnectBtn.disabled = !isConnected;
            
            // Enable/disable tool buttons
            const toolButtons = ['detectBtn', 'dumpBtn', 'infoBtn', 'resetBtn', 'customBtn'];
            toolButtons.forEach(id => {
                document.getElementById(id).disabled = !isConnected;
            });
            
            addLog(message);
        }
        
        function updateProgress(progress) {
            document.getElementById('progressFill').style.width = progress + '%';
            addLog(`Progress: ${progress}%`);
        }
        
        // Tool functions
        function refreshPorts() {
            sendWebSocketMessage({command: 'list_ports'});
        }
        
        function connectESP32() {
            const port = document.getElementById('portSelect').value;
            if (!port) {
                addLog('Please select a port', 'error');
                return;
            }
            
            sendWebSocketMessage({
                command: 'connect',
                port: port,
                baud: 115200
            });
        }
        
        function disconnectESP32() {
            sendWebSocketMessage({command: 'disconnect'});
        }
        
        function detectChip() {
            sendWebSocketMessage({command: 'detect_chip'});
        }
        
        function dumpFlash() {
            sendWebSocketMessage({command: 'dump_flash'});
        }
        
        function getDeviceInfo() {
            sendWebSocketMessage({
                command: 'send_command',
                data: 'GET_INFO'
            });
        }
        
        function resetDevice() {
            sendWebSocketMessage({
                command: 'send_command',
                data: 'RESET'
            });
        }
        
        function sendCustomCommand() {
            const cmd = document.getElementById('customCmd').value;
            if (!cmd) return;
            
            sendWebSocketMessage({
                command: 'send_command',
                data: cmd
            });
            
            document.getElementById('customCmd').value = '';
        }
        
        // Handle Enter key in custom command input
        document.getElementById('customCmd').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendCustomCommand();
            }
        });
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            initWebSocket();
        });
    </script>
</body>
</html>
    '''
    return HTMLResponse(content=html_content)

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n🛑 Shutting down ESP32 Tools...")
    esp32.disconnect()
    sys.exit(0)

def main():
    """Main entry point"""
    signal.signal(signal.SIGINT, signal_handler)
    
    print("🚀 Starting ESP32 Hardware Tools...")
    print("📡 Local server interface - no browser bloat!")
    
    # Check if running in development mode
    if len(sys.argv) > 1 and sys.argv[1] == "--dev":
        # Development mode - don't open browser
        print("🔧 Development mode - browser not opened")
    else:
        # Open browser after server starts
        import threading
        def open_browser():
            time.sleep(1.5)  # Wait for server to start
            webbrowser.open("http://localhost:8000")
        
        threading.Thread(target=open_browser, daemon=True).start()
    
    # Start the server
    try:
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="info",
            access_log=False
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
    finally:
        esp32.disconnect()

if __name__ == "__main__":
    main()
