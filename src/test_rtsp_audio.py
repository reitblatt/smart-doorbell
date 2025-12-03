#!/usr/bin/env python3
"""
Test RTSP streaming with video + audio
"""

import sys
import time
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from camera.streamer import CameraStreamer, CameraSource, AudioSource

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    logger.info("Starting RTSP streaming test with audio...")
    
    # Create streamer with test pattern video + test tone audio
    streamer = CameraStreamer(
        video_source=CameraSource.TEST_PATTERN,
        audio_source=AudioSource.TEST_TONE,  # Test tone audio
        stream_name="doorbell",
        width=1920,
        height=1080,
        framerate=30,
        video_bitrate=2000000,  # 2 Mbps
        audio_bitrate=64000,     # 64 Kbps
        use_hardware_encoding=False  # Use software encoder for now
    )
    
    try:
        # Start streaming
        streamer.start()
        
        logger.info("=" * 60)
        logger.info("Stream is now running with AUDIO!")
        logger.info(f"RTSP URL: {streamer.rtsp_url}")
        logger.info("=" * 60)
        logger.info("")
        logger.info("Test the stream with:")
        logger.info(f"  ffplay {streamer.rtsp_url}")
        logger.info("")
        logger.info("From your Mac:")
        logger.info(f"  ffplay -rtsp_transport tcp rtsp://raspberry-doorbell:8554/doorbell")
        logger.info("")
        logger.info("You should see video test pattern AND hear audio ticks!")
        logger.info("")
        logger.info("Press Ctrl+C to stop...")
        logger.info("=" * 60)
        
        # Keep running
        while True:
            time.sleep(1)
            stats = streamer.get_stats()
            
    except KeyboardInterrupt:
        logger.info("\nStopping stream...")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        streamer.stop()
        logger.info("Test complete")

if __name__ == "__main__":
    main()
