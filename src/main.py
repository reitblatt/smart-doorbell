#!/usr/bin/env python3
"""
Smart Video Doorbell - Main Entry Point
"""

import sys
import logging
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from doorbell.doorbell_manager import DoorbellManager

def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            # TODO: Add file handler for production
            # logging.FileHandler('/var/log/doorbell/doorbell.log')
        ]
    )

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Smart Video Doorbell Service'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '-c', '--config',
        type=str,
        help='Path to configuration file (TODO: implement)'
    )
    
    parser.add_argument(
        '--test-pattern',
        action='store_true',
        help='Use test pattern video source'
    )
    
    parser.add_argument(
        '--camera',
        choices=['test', 'v4l2', 'libcamera'],
        default='test',
        help='Camera source (default: test)'
    )
    
    return parser.parse_args()

def main():
    """Main entry point"""
    
    args = parse_args()
    setup_logging(args.verbose)
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Smart Video Doorbell")
    logger.info("=" * 60)
    
    # Build configuration from args
    config = {
        "video": {
            "source": args.camera,
            "width": 1920,
            "height": 1080,
            "framerate": 30,
            "bitrate": 2000000,
            "hardware_encoding": False
        },
        "audio": {
            "enabled": False,
            "source": "none",
            "device": None,
            "bitrate": 64000
        },
        "rtsp": {
            "host": "127.0.0.1",
            "port": 8554,
            "stream_name": "doorbell"
        },
        "button": {
            "enabled": False,
            "gpio_pin": 17,
            "debounce_ms": 200
        },
        "matter": {
            "enabled": False
        },
        "substream": {
            "enabled": False
        }
    }
    
    # Create and run doorbell manager
    doorbell = DoorbellManager(config)
    
    try:
        doorbell.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    
    logger.info("Doorbell service exited cleanly")
    return 0

if __name__ == "__main__":
    sys.exit(main())
