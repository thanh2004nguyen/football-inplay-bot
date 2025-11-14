"""
Web Interface Entry Point
Run this script to start the Flask web interface
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from web.app import app, get_local_ip

if __name__ == '__main__':
    local_ip = get_local_ip()
    print("=" * 60)
    print("Betfair Italy Bot - Web Interface")
    print("=" * 60)
    print(f"\nStarting Flask server...")
    print(f"Local IP: {local_ip}")
    print("=" * 60)
    print(f"\n✓ Server is running!")
    print(f"\nAccess the dashboard:")
    print(f"  • On this PC: http://localhost:5000")
    print(f"  • On your phone: http://{local_ip}:5000")
    print(f"\nPress Ctrl+C to stop the server")
    print("=" * 60)
    print()
    
    # Run on 0.0.0.0 to accept connections from network
    # This allows access from other devices on the same network
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        print("\n\nServer stopped by user")
    except Exception as e:
        print(f"\n\nError running server: {e}")
        import traceback
        traceback.print_exc()

