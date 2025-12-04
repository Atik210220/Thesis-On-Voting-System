import threading
import subprocess
import hashlib
import json
import os
import time
import difflib
import logging
import glob
import mysql.connector
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------- Configuration ----------------------

CONFIG = {
    'mode': 'local',  # or 'remote'
    'mysql': {
        'host': '127.0.0.1',
        'port': 3306,
        'user': 'root',
        'password': '',  # your MySQL password
        'database': 'votingdb',  # your DB name
    },
    'poll_interval': 20,  # check every 20 seconds
    'state_file': os.path.join(os.path.dirname(__file__), 'detector_state.json'),
    'alerts_dir': os.path.join(os.path.dirname(__file__), 'monitoring_alerts'),
}

# ---------------------- Helper Functions ----------------------

def get_latest_binlog_path():
    """Automatically find the latest MySQL binary log file."""
    binlog_dir = '/var/lib/mysql'
    files = sorted(glob.glob(os.path.join(binlog_dir, 'mysql-bin.*')))
    if not files:
        raise FileNotFoundError("No MySQL binary log files found in /var/lib/mysql/")
    latest = files[-1]
    print(f"[INFO] Using binary log file: {os.path.basename(latest)}")
    return latest

def sha256_of_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()

def ensure_dirs():
    os.makedirs(CONFIG['alerts_dir'], exist_ok=True)

def load_state():
    try:
        with open(CONFIG['state_file'], 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(state):
    with open(CONFIG['state_file'], 'w') as f:
        json.dump(state, f, indent=2)

def serialize_snapshot(obj):
    """Convert datetime objects in snapshot to strings for JSON serialization."""
    if isinstance(obj, dict):
        return {k: serialize_snapshot(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_snapshot(i) for i in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat() + 'Z'
    else:
        return obj

# ---------------------- Database Snapshot ----------------------

def get_votes_snapshot():
    """Fetch the current votes and voter data snapshot."""
    conn = mysql.connector.connect(**CONFIG['mysql'])
    cursor = conn.cursor(dictionary=True)

    snapshot = {}
    cursor.execute("SELECT * FROM votes;")
    snapshot['votes'] = cursor.fetchall()

    cursor.execute("SELECT * FROM voters;")
    snapshot['voters'] = cursor.fetchall()

    conn.close()

    # Convert datetime objects to strings
    snapshot_serializable = serialize_snapshot(snapshot)
    return snapshot_serializable

def snapshot_hash(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()

# ---------------------- Binary Log ----------------------

def dump_binlog_local():
    """Read the latest binary log file contents."""
    path = get_latest_binlog_path()
    with open(path, 'rb') as f:
        b = f.read()
    meta = {
        'path': path,
        'size': len(b),
        'dump_time': datetime.utcnow().isoformat() + 'Z'
    }
    return b, meta

# ---------------------- Alert Writer ----------------------

def write_alert(reason, meta, diff_text=""):
    ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    base = os.path.join(CONFIG['alerts_dir'], ts)
    os.makedirs(base, exist_ok=True)
    with open(os.path.join(base, 'alert.txt'), 'w') as f:
        f.write(f"[{ts}] ALERT: {reason}\n\n")
        f.write(diff_text)
    with open(os.path.join(base, 'meta.json'), 'w') as f:
        json.dump(meta, f, indent=2)
    print(f"\n🚨 [ALERT] {reason}\nDetails saved in: {base}\n")

# ---------------------- Detector Loop ----------------------

def run_detector_loop(stop_event):
    ensure_dirs()
    state = load_state()
    prev_snapshot = state.get('last_snapshot')
    prev_hash = state.get('last_hash')
    prev_binlog_hash = state.get('last_binlog_hash')

    print("[INFO] Binary Log Tamper Detector started...")

    while not stop_event.is_set():
        try:
            # --- Step 1: Check database state ---
            new_snapshot = get_votes_snapshot()
            new_hash = snapshot_hash(new_snapshot)

            # --- Step 2: Check binary log changes ---
            binlog_bytes, meta = dump_binlog_local()
            new_binlog_hash = sha256_of_bytes(binlog_bytes)

            # --- Step 3: Compare hashes ---
            if prev_hash and new_hash != prev_hash:
                # Detect unauthorized DB changes (not vote insert)
                diff = difflib.unified_diff(
                    json.dumps(prev_snapshot, indent=2).splitlines(),
                    json.dumps(new_snapshot, indent=2).splitlines(),
                    fromfile='previous_db',
                    tofile='current_db',
                    lineterm=''
                )
                diff_text = '\n'.join(diff)
                write_alert("Unauthorized database table modification detected!", meta, diff_text)
            
            if prev_binlog_hash and new_binlog_hash != prev_binlog_hash:
                write_alert("Binary log file content changed unexpectedly!", meta)

            # --- Step 4: Save new state ---
            state = {
                'last_snapshot': new_snapshot,
                'last_hash': new_hash,
                'last_binlog_hash': new_binlog_hash,
                'last_checked': datetime.utcnow().isoformat() + 'Z',
            }
            save_state(state)

            prev_snapshot, prev_hash, prev_binlog_hash = new_snapshot, new_hash, new_binlog_hash

        except Exception as e:
            print(f"[ERROR] {e}")

        # Sleep until next poll
        for _ in range(CONFIG['poll_interval']):
            if stop_event.is_set():
                break
            time.sleep(1)

    print("[INFO] Binary Log Tamper Detector stopped.")

# ---------------------- Thread Management ----------------------

_monitor_thread = None
_stop_event = None

def start_monitor_thread():
    global _monitor_thread, _stop_event
    if _monitor_thread and _monitor_thread.is_alive():
        return
    _stop_event = threading.Event()
    _monitor_thread = threading.Thread(target=run_detector_loop, args=(_stop_event,), daemon=True)
    _monitor_thread.start()

def stop_monitor_thread():
    global _stop_event, _monitor_thread
    if _stop_event:
        _stop_event.set()
    if _monitor_thread:
        _monitor_thread.join(timeout=5)

# ---------------------- Main ----------------------

if __name__ == "__main__":
    start_monitor_thread()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_monitor_thread()
