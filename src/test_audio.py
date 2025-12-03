#!/usr/bin/env python3
"""
Test audio capture and playback
"""

import sys
import time
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from audio.audio_manager import AudioManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_list_devices():
    """Test listing audio devices"""
    logger.info("=" * 60)
    logger.info("TEST: List Audio Devices")
    logger.info("=" * 60)
    
    with AudioManager() as audio:
        audio.print_devices()

def test_loopback():
    """Test audio loopback (mic to speaker)"""
    logger.info("=" * 60)
    logger.info("TEST: Audio Loopback")
    logger.info("=" * 60)
    logger.info("This will capture from microphone and play to speaker")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 60)
    
    with AudioManager() as audio:
        # Start capture and playback
        audio.start_capture()
        audio.start_playback()
        
        try:
            # Loop: get audio from capture, send to playback
            while True:
                audio_data = audio.get_audio(timeout=0.1)
                if audio_data:
                    audio.queue_audio(audio_data)
                    
        except KeyboardInterrupt:
            logger.info("\nStopping loopback...")

def test_capture_only():
    """Test capturing audio and measuring levels"""
    logger.info("=" * 60)
    logger.info("TEST: Audio Capture Only")
    logger.info("=" * 60)
    logger.info("Capturing audio and showing levels...")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 60)
    
    import struct
    
    with AudioManager() as audio:
        audio.start_capture()
        
        try:
            while True:
                audio_data = audio.get_audio(timeout=0.1)
                if audio_data:
                    # Calculate RMS level
                    samples = struct.unpack(f'{len(audio_data)//2}h', audio_data)
                    rms = (sum(s*s for s in samples) / len(samples)) ** 0.5
                    level = int(rms / 32768 * 50)  # Scale to 50 chars
                    
                    print(f"\rLevel: [{'=' * level}{' ' * (50-level)}] {rms:6.0f}", 
                          end='', flush=True)
                    
        except KeyboardInterrupt:
            print("\n\nStopping capture...")

def main():
    logger.info("Audio System Test")
    logger.info("")
    
    print("Select test:")
    print("  1. List audio devices")
    print("  2. Audio loopback (mic to speaker)")
    print("  3. Capture and show levels")
    print("")
    
    choice = input("Enter choice (1-3): ").strip()
    
    if choice == "1":
        test_list_devices()
    elif choice == "2":
        test_loopback()
    elif choice == "3":
        test_capture_only()
    else:
        print("Invalid choice")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
