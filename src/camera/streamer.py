#!/usr/bin/env python3
"""
Camera streaming module using GStreamer
Supports both real cameras and test sources
"""

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import logging
import threading
from enum import Enum

logger = logging.getLogger(__name__)

class CameraSource(Enum):
    """Available camera sources"""
    TEST_PATTERN = "test"
    V4L2 = "v4l2"
    LIBCAMERA = "libcamera"

class CameraStreamer:
    """
    Handles camera capture and RTSP streaming via MediaMTX
    """
    
    def __init__(self, 
                 source=CameraSource.TEST_PATTERN,
                 rtsp_host="127.0.0.1",
                 rtsp_port=8554,
                 stream_name="doorbell",
                 width=1920,
                 height=1080,
                 framerate=30,
                 bitrate=2000000,
                 use_hardware_encoding=True):
        """
        Initialize camera streamer
        
        Args:
            source: Camera source type (CameraSource enum)
            rtsp_host: MediaMTX host
            rtsp_port: MediaMTX RTSP port
            stream_name: RTSP stream path name
            width: Video width
            height: Video height
            framerate: Frames per second
            bitrate: H.264 bitrate in bits/sec
            use_hardware_encoding: Try hardware encoder first (v4l2h264enc)
        """
        self.source = source
        self.rtsp_url = f"rtsp://{rtsp_host}:{rtsp_port}/{stream_name}"
        self.width = width
        self.height = height
        self.framerate = framerate
        self.bitrate = bitrate
        self.use_hardware_encoding = use_hardware_encoding
        
        self.pipeline = None
        self.loop = None
        self.thread = None
        self.is_running = False
        self._stop_requested = False
        
        # Initialize GStreamer
        Gst.init(None)
        
        logger.info(f"Camera streamer initialized: {width}x{height}@{framerate}fps")
        logger.info(f"RTSP URL: {self.rtsp_url}")
        logger.info(f"Hardware encoding: {use_hardware_encoding}")
    
    def _build_pipeline_string(self):
        """Build GStreamer pipeline string based on source type"""
        
        # Common video format caps
        video_caps = (
            f"video/x-raw,width={self.width},height={self.height},"
            f"framerate={self.framerate}/1"
        )
        
        # Source element
        if self.source == CameraSource.TEST_PATTERN:
            source = "videotestsrc is-live=true"
        elif self.source == CameraSource.V4L2:
            source = "v4l2src device=/dev/video0"
        elif self.source == CameraSource.LIBCAMERA:
            source = f"libcamerasrc"
        else:
            raise ValueError(f"Unknown source type: {self.source}")
        
        # Choose encoder
        if self.use_hardware_encoding:
            # Hardware encoder - uses GPU, low CPU, needs GPU memory
            encoder = (
                f"v4l2h264enc extra-controls=\"controls,video_bitrate={self.bitrate}\" ! "
                f"video/x-h264,profile=baseline,level=(string)3.1"
            )
        else:
            # Software encoder - uses CPU, more flexible
            # Add key-int-max for regular keyframes (helps with seeking/recovery)
            encoder = (
                f"x264enc "
                f"bitrate={self.bitrate//1000} "
                f"speed-preset=ultrafast "
                f"tune=zerolatency "
                f"key-int-max={self.framerate * 2} "  # Keyframe every 2 seconds
                f"bframes=0 "  # No B-frames for lower latency
                f"! "
                f"video/x-h264,profile=baseline"
            )
        
        # Build pipeline with optimizations
        pipeline = (
            f"{source} ! "
            f"{video_caps} ! "
            f"videoconvert ! "
            f"video/x-raw,format=I420 ! "
            f"{encoder} ! "
            f"h264parse config-interval=-1 ! "  # Insert SPS/PPS in every keyframe
            f"rtspclientsink "
            f"location={self.rtsp_url} "
            f"protocols=tcp "
            f"latency=200"  # 200ms buffer
        )
        
        return pipeline
    
    def start(self):
        """Start the camera stream"""
        if self.is_running:
            logger.warning("Stream already running")
            return
        
        try:
            # Build pipeline
            pipeline_str = self._build_pipeline_string()
            logger.info(f"Pipeline: {pipeline_str}")
            
            self.pipeline = Gst.parse_launch(pipeline_str)
            
            # Set up bus to watch for messages
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", self._on_bus_message)
            
            # Start pipeline
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                raise RuntimeError("Unable to set pipeline to PLAYING state")
            
            # Start GLib main loop in separate thread
            self.loop = GLib.MainLoop()
            self.thread = threading.Thread(target=self.loop.run, daemon=True)
            self.thread.start()
            
            self.is_running = True
            self._stop_requested = False
            logger.info("Camera stream started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start stream: {e}")
            self.stop()
            raise
    
    def stop(self):
        """Stop the camera stream"""
        if not self.is_running and not self._stop_requested:
            return
        
        self._stop_requested = True
        logger.info("Stopping camera stream...")
        
        # Stop pipeline
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
        
        # Stop main loop
        if self.loop:
            self.loop.quit()
            self.loop = None
        
        # Wait for thread (but not if we're being called from the thread itself)
        if self.thread and threading.current_thread() != self.thread:
            self.thread.join(timeout=2.0)
            self.thread = None
        
        self.is_running = False
        logger.info("Camera stream stopped")
    
    def _on_bus_message(self, bus, message):
        """Handle GStreamer bus messages"""
        t = message.type
        
        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"GStreamer error: {err}")
            logger.debug(f"Debug info: {debug}")
            # Don't call stop() from the bus callback to avoid threading issues
            # Just quit the loop
            if self.loop:
                self.loop.quit()
            
        elif t == Gst.MessageType.WARNING:
            err, debug = message.parse_warning()
            logger.warning(f"GStreamer warning: {err}")
            
        elif t == Gst.MessageType.EOS:
            logger.info("End of stream")
            if self.loop:
                self.loop.quit()
            
        elif t == Gst.MessageType.STATE_CHANGED:
            if message.src == self.pipeline:
                old_state, new_state, pending = message.parse_state_changed()
                logger.debug(
                    f"Pipeline state changed: "
                    f"{old_state.value_nick} -> {new_state.value_nick}"
                )
    
    def is_streaming(self):
        """Check if stream is active"""
        return self.is_running
    
    def get_stats(self):
        """Get streaming statistics"""
        if not self.pipeline:
            return {}
        
        # TODO: Extract actual stats from pipeline elements
        return {
            "is_running": self.is_running,
            "rtsp_url": self.rtsp_url,
            "resolution": f"{self.width}x{self.height}",
            "framerate": self.framerate,
            "bitrate": self.bitrate
        }
