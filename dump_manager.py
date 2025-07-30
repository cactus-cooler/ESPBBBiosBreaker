#!/usr/bin/env python3
"""
ESP32 BIOS Dump Manager
Organizes and manages dump files with timestamps and metadata
"""

import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

class DumpManager:
    """Manages ESP32 dump files with organization and metadata"""
    
    def __init__(self, base_dir: str = None):
        if base_dir is None:
            self.base_dir = Path.home() / "ESP32_Dumps"
        else:
            self.base_dir = Path(base_dir)
        
        # Create organized directory structure
        self.dumps_dir = self.base_dir / "dumps"
        self.metadata_dir = self.base_dir / "metadata"
        self.reports_dir = self.base_dir / "reports"
        self.temp_dir = self.base_dir / "temp"
        
        # Create directories
        for directory in [self.dumps_dir, self.metadata_dir, self.reports_dir, self.temp_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get_dump_filename(self, device_info: str = "ESP32", chip_id: str = None, timestamp: bool = True) -> str:
        """Generate organized dump filename"""
        if timestamp:
            time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            if chip_id:
                filename = f"{device_info}_{chip_id}_{time_str}.bin"
            else:
                filename = f"{device_info}_{time_str}.bin"
        else:
            if chip_id:
                filename = f"{device_info}_{chip_id}.bin"
            else:
                filename = f"{device_info}.bin"
        
        return str(self.dumps_dir / filename)
    
    def save_dump_metadata(self, dump_file: str, metadata: Dict):
        """Save metadata alongside dump file"""
        dump_path = Path(dump_file)
        metadata_file = self.metadata_dir / f"{dump_path.stem}.json"
        
        # Add timestamp and file info
        metadata.update({
            "timestamp": datetime.now().isoformat(),
            "dump_file": str(dump_path),
            "file_size": os.path.getsize(dump_file) if os.path.exists(dump_file) else 0,
            "dump_size_mb": round(os.path.getsize(dump_file) / (1024*1024), 2) if os.path.exists(dump_file) else 0
        })
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        console.print(f"[green]📝 Metadata saved: {metadata_file}[/green]")
    
    def list_dumps(self) -> List[Dict]:
        """List all available dumps with metadata"""
        dumps = []
        
        for dump_file in self.dumps_dir.glob("*.bin"):
            metadata_file = self.metadata_dir / f"{dump_file.stem}.json"
            
            dump_info = {
                "filename": dump_file.name,
                "path": str(dump_file),
                "size_mb": round(dump_file.stat().st_size / (1024*1024), 2),
                "modified": datetime.fromtimestamp(dump_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "metadata": None
            }
            
            # Load metadata if available
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        dump_info["metadata"] = json.load(f)
                except Exception as e:
                    console.print(f"[yellow]⚠️ Error reading metadata for {dump_file.name}: {e}[/yellow]")
            
            dumps.append(dump_info)
        
        # Sort by modification time (newest first)
        dumps.sort(key=lambda x: x["modified"], reverse=True)
        return dumps
    
    def display_dumps_table(self):
        """Display beautiful table of all dumps"""
        dumps = self.list_dumps()
        
        if not dumps:
            console.print("[yellow]📁 No dumps found in the collection[/yellow]")
            console.print(f"[dim]Dumps will be saved to: {self.dumps_dir}[/dim]")
            return
        
        table = Table(title=f"🗂️  ESP32 BIOS Dump Collection ({len(dumps)} files)")
        table.add_column("Filename", style="cyan", min_width=25)
        table.add_column("Size", style="green", justify="right")
        table.add_column("Date", style="magenta")
        table.add_column("Device", style="yellow")
        table.add_column("Status", style="bright_green")
        
        for dump in dumps:
            device = "Unknown"
            status = "✅ Valid"
            
            if dump["metadata"]:
                device = dump["metadata"].get("device_info", "ESP32")
                if "chip_id" in dump["metadata"]:
                    device += f" ({dump['metadata']['chip_id']})"
                
                if dump["metadata"].get("file_size", 0) == 0:
                    status = "❌ Empty"
                elif dump["size_mb"] < 1:
                    status = "⚠️  Small"
            
            table.add_row(
                dump["filename"],
                f"{dump['size_mb']} MB",
                dump["modified"],
                device,
                status
            )
        
        console.print(table)
        
        # Show directory info
        total_size = sum(dump["size_mb"] for dump in dumps)
        console.print(f"\n[dim]📁 Storage Location: {self.dumps_dir}[/dim]")
        console.print(f"[dim]💾 Total Size: {total_size:.1f} MB[/dim]")
    
    def create_dump_report(self, dump_file: str) -> str:
        """Create a detailed report for a dump file"""
        dump_path = Path(dump_file)
        metadata_file = self.metadata_dir / f"{dump_path.stem}.json"
        report_file = self.reports_dir / f"{dump_path.stem}_report.txt"
        
        # Load metadata
        metadata = {}
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
        
        # Generate report
        report_lines = [
            "="*80,
            f"ESP32 BIOS Dump Analysis Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "="*80,
            "",
            f"📁 DUMP FILE INFORMATION:",
            f"   Filename: {dump_path.name}",
            f"   Location: {dump_path}",
            f"   Size: {dump_path.stat().st_size:,} bytes ({dump_path.stat().st_size / (1024*1024):.2f} MB)",
            f"   Created: {datetime.fromtimestamp(dump_path.stat().st_ctime).strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"🔬 DEVICE INFORMATION:",
        ]
        
        if metadata:
            for key, value in metadata.items():
                if key not in ['timestamp', 'dump_file']:
                    report_lines.append(f"   {key.replace('_', ' ').title()}: {value}")
        else:
            report_lines.append("   No metadata available")
        
        report_lines.extend([
            "",
            f"📊 FILE ANALYSIS:",
            f"   File exists: {'✅ Yes' if dump_path.exists() else '❌ No'}",
            f"   File readable: {'✅ Yes' if os.access(dump_path, os.R_OK) else '❌ No'}",
            f"   File size valid: {'✅ Yes' if dump_path.stat().st_size > 0 else '❌ Empty'}",
            "",
            "="*80
        ])
        
        # Save report
        with open(report_file, 'w') as f:
            f.write('\n'.join(report_lines))
        
        return str(report_file)
    
    def cleanup_temp_files(self):
        """Clean up temporary files older than 24 hours"""
        import time
        current_time = time.time()
        cleaned = 0
        
        for temp_file in self.temp_dir.glob("*"):
            if current_time - temp_file.stat().st_mtime > 24 * 3600:  # 24 hours
                temp_file.unlink()
                cleaned += 1
        
        if cleaned > 0:
            console.print(f"[green]🧹 Cleaned up {cleaned} temporary files[/green]")
    
    def get_directory_info(self) -> Dict:
        """Get information about dump directories"""
        return {
            "base_dir": str(self.base_dir),
            "dumps_dir": str(self.dumps_dir),
            "metadata_dir": str(self.metadata_dir),
            "reports_dir": str(self.reports_dir),
            "temp_dir": str(self.temp_dir),
            "total_dumps": len(list(self.dumps_dir.glob("*.bin"))),
            "total_size_mb": sum(f.stat().st_size for f in self.dumps_dir.glob("*.bin")) / (1024*1024)
        }

def main():
    """CLI interface for dump manager"""
    import argparse
    
    parser = argparse.ArgumentParser(description="ESP32 Dump Manager")
    parser.add_argument("--list", "-l", action="store_true", help="List all dumps")
    parser.add_argument("--info", "-i", action="store_true", help="Show directory information")
    parser.add_argument("--report", "-r", help="Generate report for dump file")
    parser.add_argument("--cleanup", "-c", action="store_true", help="Cleanup temporary files")
    
    args = parser.parse_args()
    
    manager = DumpManager()
    
    if args.list:
        manager.display_dumps_table()
    elif args.info:
        info = manager.get_directory_info()
        console.print(Panel.fit(
            f"[bold]ESP32 Dump Storage Information[/bold]\n\n"
            f"📁 Base Directory: [cyan]{info['base_dir']}[/cyan]\n"
            f"💾 Dumps Directory: [cyan]{info['dumps_dir']}[/cyan]\n"
            f"📝 Metadata Directory: [cyan]{info['metadata_dir']}[/cyan]\n"
            f"📊 Reports Directory: [cyan]{info['reports_dir']}[/cyan]\n"
            f"🔄 Temp Directory: [cyan]{info['temp_dir']}[/cyan]\n\n"
            f"📊 [bold]Statistics:[/bold]\n"
            f"   Total Dumps: [green]{info['total_dumps']}[/green]\n"
            f"   Total Size: [green]{info['total_size_mb']:.1f} MB[/green]",
            title="🗂️ Storage Info"
        ))
    elif args.report:
        report_file = manager.create_dump_report(args.report)
        console.print(f"[green]📊 Report generated: {report_file}[/green]")
    elif args.cleanup:
        manager.cleanup_temp_files()
    else:
        console.print("[bold]ESP32 Dump Manager[/bold]")
        console.print("Use --help for available options")
        manager.display_dumps_table()

if __name__ == "__main__":
    main()