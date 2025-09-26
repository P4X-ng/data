#!/usr/bin/env python3
"""
File Translator - Automatically convert regular files to PacketFS format
Integrates with the existing translate_daemon from PacketFS
"""

import os
import sys
import json
import time
import hashlib
import threading
import subprocess
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from pathlib import Path

# Add PacketFS to path
sys.path.insert(0, '/home/punk/Projects/packetfs/src')

try:
    from packetfs.filesystem.virtual_blob import VirtualBlob
    from packetfs.filesystem.blob_fs import BlobFS, BlobConfig
    from packetfs.filesystem.iprog import build_iprog_for_file_bytes, BlobFingerprint
    PACKETFS_AVAILABLE = True
except ImportError:
    print("PacketFS not available - using fallback mode")
    PACKETFS_AVAILABLE = False

@dataclass
class TranslationJob:
    source_path: str
    target_path: str
    priority: int = 1
    created_at: float = 0.0
    status: str = "pending"  # pending, processing, completed, failed
    error: Optional[str] = None

class FileTranslator:
    """Automatic file translation to PacketFS format"""
    
    def __init__(self, 
                 watch_dirs: List[str],
                 output_dir: str,
                 blob_name: str = "oswalk_blob",
                 blob_size: int = 1 << 30,  # 1GB
                 blob_seed: int = 1337,
                 meta_dir: str = "./oswalk_meta"):
        
        self.watch_dirs = [Path(d) for d in watch_dirs]
        self.output_dir = Path(output_dir)
        self.blob_name = blob_name
        self.blob_size = blob_size
        self.blob_seed = blob_seed
        self.meta_dir = Path(meta_dir)
        
        # Create directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        
        # Translation state
        self.translation_queue: List[TranslationJob] = []
        self.processed_files: Set[str] = set()
        self.lock = threading.RLock()
        self.running = False
        
        # Initialize PacketFS components if available
        if PACKETFS_AVAILABLE:
            self._init_packetfs()
        
        print(f"[XLT] File Translator initialized")
        print(f"   Watch dirs: {[str(d) for d in self.watch_dirs]}")
        print(f"   Output dir: {self.output_dir}")
        print(f"   Blob: {blob_name} ({blob_size // (1024*1024)}MB)")
    
    def _init_packetfs(self):
        """Initialize PacketFS components"""
        try:
            self.blob_config = BlobConfig(
                name=self.blob_name,
                size_bytes=self.blob_size,
                seed=self.blob_seed,
                meta_dir=str(self.meta_dir)
            )
            self.blob_fs = BlobFS(self.blob_config)
            self.blob_fp = BlobFingerprint(
                name=self.blob_name,
                size=self.blob_size,
                seed=self.blob_seed
            )
            print("[OK] PacketFS components initialized")
        except Exception as e:
            print(f"[ERR] Failed to initialize PacketFS: {e}")
            global PACKETFS_AVAILABLE
            PACKETFS_AVAILABLE = False
    
    def should_translate(self, file_path: Path) -> bool:
        """Check if file should be translated"""
        # Skip if already processed
        if str(file_path) in self.processed_files:
            return False
        
        # Skip temporary files
        if file_path.name.startswith('.') or file_path.suffix in ['.tmp', '.part']:
            return False
        
        # Skip if already translated
        iprog_path = self.output_dir / f"{file_path.name}.iprog.json"
        if iprog_path.exists():
            # Check if source is newer
            try:
                if file_path.stat().st_mtime <= iprog_path.stat().st_mtime:
                    return False
            except:
                pass
        
        # Skip very large files (>100MB) for now
        try:
            if file_path.stat().st_size > 100 * 1024 * 1024:
                return False
        except:
            return False
        
        return True
    
    def scan_for_files(self) -> List[Path]:
        """Scan watch directories for files to translate"""
        candidates = []
        
        for watch_dir in self.watch_dirs:
            if not watch_dir.exists():
                continue
            
            try:
                for file_path in watch_dir.rglob('*'):
                    if file_path.is_file() and self.should_translate(file_path):
                        candidates.append(file_path)
            except Exception as e:
                print(f"Error scanning {watch_dir}: {e}")
        
        return candidates
    
    def add_translation_job(self, source_path: Path, priority: int = 1):
        """Add a file to the translation queue"""
        with self.lock:
            job = TranslationJob(
                source_path=str(source_path),
                target_path=str(self.output_dir / f"{source_path.name}.iprog.json"),
                priority=priority,
                created_at=time.time()
            )
            
            # Insert by priority (higher priority first)
            inserted = False
            for i, existing_job in enumerate(self.translation_queue):
                if job.priority > existing_job.priority:
                    self.translation_queue.insert(i, job)
                    inserted = True
                    break
            
            if not inserted:
                self.translation_queue.append(job)
            
            print(f"[QUEUE] Queued for translation: {source_path.name}")
    
    def translate_file_packetfs(self, job: TranslationJob) -> bool:
        """Translate file using PacketFS"""
        try:
            source_path = Path(job.source_path)
            
            # Read file data
            with open(source_path, 'rb') as f:
                data = f.read()
            
            # Calculate hash
            obj_sha = hashlib.sha256(data).hexdigest()
            object_id = f"sha256:{obj_sha}"
            
            # Write to blob
            segs = self.blob_fs.write_bytes(data)
            self.blob_fs.record_object(object_id, len(data), obj_sha, 65536, segs)
            
            # Build IPROG
            iprog = build_iprog_for_file_bytes(
                data, 
                source_path.name, 
                self.blob_fp, 
                segs, 
                window_size=65536
            )
            
            # Add metadata
            iprog['source_path'] = str(source_path)
            iprog['translated_at'] = time.time()
            iprog['translator'] = 'oswalk'
            
            # Write IPROG file
            with open(job.target_path, 'w', encoding='utf-8') as f:
                json.dump(iprog, f, separators=(',', ':'))
                f.write('\n')
            
            print(f"[OK] Translated {source_path.name} -> {Path(job.target_path).name}")
            return True
            
        except Exception as e:
            print(f"[ERR] Translation failed for {job.source_path}: {e}")
            job.error = str(e)
            return False
    
    def translate_file_fallback(self, job: TranslationJob) -> bool:
        """Fallback translation using external translate_daemon"""
        try:
            # Use the existing translate_daemon
            translate_daemon = "/home/punk/Projects/packetfs/src/packetfs/tools/translate_daemon.py"
            
            if not os.path.exists(translate_daemon):
                print(f"[ERR] translate_daemon not found at {translate_daemon}")
                return False
            
            # Create temporary watch directory
            temp_watch = self.meta_dir / "temp_watch"
            temp_watch.mkdir(exist_ok=True)
            
            # Copy file to watch directory
            source_path = Path(job.source_path)
            temp_file = temp_watch / source_path.name
            
            import shutil
            shutil.copy2(source_path, temp_file)
            
            # Run translate_daemon for one iteration
            cmd = [
                sys.executable, translate_daemon,
                "--watch-dir", str(temp_watch),
                "--out-dir", str(self.output_dir),
                "--blob-name", self.blob_name,
                "--blob-size", str(self.blob_size),
                "--blob-seed", str(self.blob_seed),
                "--meta-dir", str(self.meta_dir),
                "--interval", "0.1",
                "--remove-src"
            ]
            
            # Run with timeout
            result = subprocess.run(cmd, timeout=30, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"[OK] Translated {source_path.name} (fallback)")
                return True
            else:
                print(f"[ERR] Fallback translation failed: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"[ERR] Fallback translation error: {e}")
            return False
    
    def process_translation_job(self, job: TranslationJob) -> bool:
        """Process a single translation job"""
        job.status = "processing"
        
        success = False
        if PACKETFS_AVAILABLE:
            success = self.translate_file_packetfs(job)
        else:
            success = self.translate_file_fallback(job)
        
        if success:
            job.status = "completed"
            with self.lock:
                self.processed_files.add(job.source_path)
        else:
            job.status = "failed"
        
        return success
    
    def worker_loop(self):
        """Main worker loop"""
        print("[WORKER] Translation worker started")
        
        while self.running:
            try:
                # Get next job
                job = None
                with self.lock:
                    if self.translation_queue:
                        job = self.translation_queue.pop(0)
                
                if job:
                    self.process_translation_job(job)
                else:
                    # No jobs, scan for new files
                    candidates = self.scan_for_files()
                    for file_path in candidates[:5]:  # Process up to 5 at a time
                        self.add_translation_job(file_path)
                    
                    if not candidates:
                        time.sleep(5)  # Wait before next scan
                
            except Exception as e:
                print(f"Worker error: {e}")
                time.sleep(1)
    
    def start(self):
        """Start the file translator"""
        if self.running:
            return
        
        self.running = True
        
        # Start worker thread
        worker_thread = threading.Thread(target=self.worker_loop, daemon=True)
        worker_thread.start()
        
        print("[XLT] File translator started")
    
    def stop(self):
        """Stop the file translator"""
        self.running = False
        
        if PACKETFS_AVAILABLE and hasattr(self, 'blob_fs'):
            try:
                self.blob_fs.close()
            except:
                pass
        
        print("[STOP] File translator stopped")
    
    def get_status(self) -> Dict[str, any]:
        """Get translator status"""
        with self.lock:
            return {
                'running': self.running,
                'queue_length': len(self.translation_queue),
                'processed_files': len(self.processed_files),
                'watch_dirs': [str(d) for d in self.watch_dirs],
                'output_dir': str(self.output_dir),
                'packetfs_available': PACKETFS_AVAILABLE
            }

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='File translator for OS Walk')
    parser.add_argument('--watch-dirs', nargs='+', required=True, help='Directories to watch')
    parser.add_argument('--output-dir', required=True, help='Output directory for IPROG files')
    parser.add_argument('--blob-name', default='oswalk_blob', help='Blob name')
    parser.add_argument('--blob-size', type=int, default=1<<30, help='Blob size in bytes')
    parser.add_argument('--blob-seed', type=int, default=1337, help='Blob seed')
    parser.add_argument('--meta-dir', default='./oswalk_meta', help='Metadata directory')
    
    args = parser.parse_args()
    
    translator = FileTranslator(
        watch_dirs=args.watch_dirs,
        output_dir=args.output_dir,
        blob_name=args.blob_name,
        blob_size=args.blob_size,
        blob_seed=args.blob_seed,
        meta_dir=args.meta_dir
    )
    
    translator.start()
    
    try:
        while True:
            status = translator.get_status()
            print(f"Status: {status['queue_length']} queued, {status['processed_files']} processed")
            time.sleep(10)
    except KeyboardInterrupt:
        translator.stop()

if __name__ == '__main__':
    main()