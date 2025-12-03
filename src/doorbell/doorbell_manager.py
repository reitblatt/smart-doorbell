#!/usr/bin/env python3
"""
Main doorbell manager - coordinates all subsystems
"""

import logging
import signal
import time
from enum import Enum
from typing import Optional

from camera.streamer import CameraStreamer, CameraSource, AudioSource
# from audio.audio_manager import AudioManager  # When audio hardware is ready
# from matter.device import MatterDevice  # Future Matter integration

logger = logging.getLogger(__name__)

class DoorbellState(Enum):
    """Doorbell operational states"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"

class DoorbellManager:
    """
    Main doorbell manager - coordinates all subsystems:
    - Video streaming
    - Audio capture/playback
    - Button input
    - Matter protocol
    - Event notifications
    """
    
    def __init__(self, config: Optional[dict] = None):
        """
        Initialize doorbell manager
        
        Args:
            config: Configuration dictionary (or None for defaults)
        """
        self.config = config or self._default_config()
        self.state = DoorbellState.STOPPED
        
        # Subsystems
        self.camera_streamer: Optional[CameraStreamer] = None
        # self.audio_manager: Optional[AudioManager] = None
        # self.matter_device: Optional[MatterDevice] = None
        
        # State
        self._shutdown_requested = False
        
        logger.info("Doorbell manager initialized")
        logger.info(f"Config: {self.config}")
    
    def _default_config(self) -> dict:
        """Get default configuration"""
        return {
            # Video settings
            "video": {
                "source": "test",  # test, v4l2, libcamera
                "width": 1920,
                "height": 1080,
                "framerate": 30,
                "bitrate": 2000000,  # 2 Mbps
                "hardware_encoding": False
            },
            
            # Audio settings
            "audio": {
                "enabled": False,  # Enable when hardware available
                "source": "none",  # none, test, alsa, pulse
                "device": None,    # e.g., "hw:1,0"
                "bitrate": 64000   # 64 Kbps
            },
            
            # RTSP settings
            "rtsp": {
                "host": "127.0.0.1",
                "port": 8554,
                "stream_name": "doorbell"
            },
            
            # Button settings
            "button": {
                "enabled": False,  # Enable when GPIO connected
                "gpio_pin": 17,
                "debounce_ms": 200
            },
            
            # Matter settings
            "matter": {
                "enabled": False,  # Enable when Matter integration ready
                "vendor_id": 0xFFF1,
                "product_id": 0x8001
            },
            
            # Substream for Frigate (future)
            "substream": {
                "enabled": False,
                "width": 640,
                "height": 480,
                "framerate": 10,
                "bitrate": 500000
            }
        }
    
    def start(self):
        """Start all doorbell subsystems"""
        if self.state == DoorbellState.RUNNING:
            logger.warning("Doorbell already running")
            return
        
        logger.info("Starting doorbell...")
        self.state = DoorbellState.STARTING
        
        try:
            # Start video streaming
            self._start_camera()
            
            # Start audio (when hardware available)
            # self._start_audio()
            
            # Start button monitoring (when GPIO configured)
            # self._start_button()
            
            # Start Matter device (when implemented)
            # self._start_matter()
            
            self.state = DoorbellState.RUNNING
            logger.info("✓ Doorbell started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start doorbell: {e}")
            self.state = DoorbellState.ERROR
            self.stop()
            raise
    
    def stop(self):
        """Stop all doorbell subsystems"""
        if self.state == DoorbellState.STOPPED:
            return
        
        logger.info("Stopping doorbell...")
        self.state = DoorbellState.STOPPING
        
        # Stop subsystems in reverse order
        # self._stop_matter()
        # self._stop_button()
        # self._stop_audio()
        self._stop_camera()
        
        self.state = DoorbellState.STOPPED
        logger.info("✓ Doorbell stopped")
    
    def _start_camera(self):
        """Start camera streaming"""
        logger.info("Starting camera streamer...")
        
        video_cfg = self.config["video"]
        audio_cfg = self.config["audio"]
        rtsp_cfg = self.config["rtsp"]
        
        # Map config strings to enums
        video_source_map = {
            "test": CameraSource.TEST_PATTERN,
            "v4l2": CameraSource.V4L2,
            "libcamera": CameraSource.LIBCAMERA
        }
        
        audio_source_map = {
            "none": AudioSource.NONE,
            "test": AudioSource.TEST_TONE,
            "alsa": AudioSource.ALSA,
            "pulse": AudioSource.PULSE
        }
        
        self.camera_streamer = CameraStreamer(
            video_source=video_source_map[video_cfg["source"]],
            audio_source=audio_source_map[audio_cfg["source"]],
            rtsp_host=rtsp_cfg["host"],
            rtsp_port=rtsp_cfg["port"],
            stream_name=rtsp_cfg["stream_name"],
            width=video_cfg["width"],
            height=video_cfg["height"],
            framerate=video_cfg["framerate"],
            video_bitrate=video_cfg["bitrate"],
            audio_device=audio_cfg["device"],
            audio_bitrate=audio_cfg["bitrate"],
            use_hardware_encoding=video_cfg["hardware_encoding"]
        )
        
        self.camera_streamer.start()
        logger.info("✓ Camera streamer started")
    
    def _stop_camera(self):
        """Stop camera streaming"""
        if self.camera_streamer:
            logger.info("Stopping camera streamer...")
            self.camera_streamer.stop()
            self.camera_streamer = None
            logger.info("✓ Camera streamer stopped")
    
    def get_status(self) -> dict:
        """Get current doorbell status"""
        status = {
            "state": self.state.value,
            "uptime_seconds": 0,  # TODO: Track uptime
            "camera": {
                "streaming": self.camera_streamer.is_streaming() if self.camera_streamer else False,
                "stats": self.camera_streamer.get_stats() if self.camera_streamer else {}
            },
            "audio": {
                "enabled": self.config["audio"]["enabled"],
                "capturing": False  # TODO
            },
            "button": {
                "enabled": self.config["button"]["enabled"],
                "last_press": None  # TODO
            },
            "matter": {
                "enabled": self.config["matter"]["enabled"],
                "commissioned": False  # TODO
            }
        }
        
        return status
    
    def run(self):
        """Run the doorbell service (blocking)"""
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Start the doorbell
        self.start()
        
        logger.info("=" * 60)
        logger.info("Doorbell service is running")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 60)
        
        # Main loop
        try:
            while not self._shutdown_requested and self.state == DoorbellState.RUNNING:
                time.sleep(1)
                
                # Periodic status check
                if logger.isEnabledFor(logging.DEBUG):
                    status = self.get_status()
                    logger.debug(f"Status: {status}")
                
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
        finally:
            self.stop()
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self._shutdown_requested = True
