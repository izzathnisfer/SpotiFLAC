from radio.core.queue_manager import SessionQueue, Track
from pathlib import Path

def test_queue_advance():
    q = SessionQueue("test")
    
    # 1. Empty queue advance
    print("1. Testing empty queue advance...")
    res = q.advance()
    assert res is None, "Empty queue advance should return None"
    assert q._current_index == -1, f"Index should stay -1, got {q._current_index}"
    
    # 2. Advance again (simulate fallback loop)
    print("2. Testing second empty advance...")
    res = q.advance()
    assert res is None
    assert q._current_index == -1, f"Index should stay -1, got {q._current_index}"
    
    # 3. Add track
    print("3. Adding track...")
    t = Track(id="1", file_path=Path("a"), title="Test")
    q.add_track(t)
    
    # 4. Advance to valid track
    print("4. Advancing to track...")
    res = q.advance()
    assert res is not None, "Should get track"
    assert res.track.title == "Test", "Should be Test track"
    assert q._current_index == 0, f"Index should be 0, got {q._current_index}"
    
    print("✅ TEST PASSED")

if __name__ == "__main__":
    test_queue_advance()
