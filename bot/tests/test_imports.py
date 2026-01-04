"""
Test 1: Import Tests
Verify all modules can be imported without errors.
"""
import sys
from pathlib import Path

# Add bot directory to path
bot_dir = Path(__file__).parent.parent
sys.path.insert(0, str(bot_dir))

def test_imports():
    results = []
    
    # Core modules
    modules = [
        ("config", "bot/config.py"),
        ("services.database", "bot/services/database.py"),
        ("services.backend", "bot/services/backend.py"),
        ("radio.constants", "bot/radio/constants.py"),
        ("radio.session", "bot/radio/session.py"),
        ("radio.queue", "bot/radio/queue.py"),
        ("radio.streaming", "bot/radio/streaming.py"),
        ("radio.transcoder", "bot/radio/transcoder.py"),
        ("radio.scheduler", "bot/radio/scheduler.py"),
        ("radio.engine", "bot/radio/engine.py"),
        ("handlers.start", "bot/handlers/start.py"),
        ("handlers.radio", "bot/handlers/radio.py"),
    ]
    
    for module_name, file_path in modules:
        try:
            __import__(module_name)
            results.append((module_name, "OK", None))
            print(f"✅ {module_name}")
        except Exception as e:
            results.append((module_name, "FAIL", str(e)))
            print(f"❌ {module_name}: {e}")
    
    # Summary
    passed = sum(1 for _, status, _ in results if status == "OK")
    failed = sum(1 for _, status, _ in results if status == "FAIL")
    print(f"\n{'='*50}")
    print(f"IMPORT TEST RESULTS: {passed} passed, {failed} failed")
    print(f"{'='*50}")
    
    return failed == 0

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
