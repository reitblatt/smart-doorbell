#!/usr/bin/env python3
"""
Camera streaming module using GStreamer
Supports both real cameras and test sources with audio
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

class AudioSource(Enum):
    """Available audio sources"""
    TEST_TONE = "test"
    ALSA = "alsa"
    PULSE = "pulse"
    NONE = "none"

class CameraStreamer:
    """
    Handles camera capture and RTSP streaming via MediaMTX
    Supports video + audio streaming
    
    Note: For now, audio and video are sent as separate streams to MediaMTX.
    MediaMTX will mux them together in the RTSP output.
    """
    
    def __init__(self, 
                 video_source=CameraSource.TEST_PATTERN,
                 audio_source=AudioSource.NONE,
                 rtsp_host="127.0.0.1",
                 rtsp_port=8554,
                 stream_name="doorbell",
                 width=1920,
                 height=1080,
                 framerate=30,
                 video_bitrate=2000000,
                 audio_device=None,
                 audio_bitrate=64000,
                 use_hardware_encoding=True):
        """
        Initialize camera streamer
        
        Args:
            video_source: Video source type
            audio_source: Audio source type
            rtsp_host: MediaMTX host
            rtsp_port: MediaMTX RTSP port
            stream_name: RTSP stream path name
            width: Video width
            height: Video height
            framerate: Frames per second
            video_bitrate: H.264 bitrate in bits/sec
            audio_device: ALSA device name (e.g., "hw:1,0") or None for default
            audio_bitrate: Audio bitrate in bits/sec
            use_hardware_encoding: Try hardware encoder first (v4l2h264enc)
        """
        self.video_source = video_source
        self.audio_source = audio_source
        self.rtsp_url = f"rtsp://{rtsp_host}:{rtsp_port}/{stream_name}"
        self.width = width
        self.height = height
        self.framerate = framerate
        self.video_bitrate = video_bitrate
        self.audio_device = audio_device
        self.audio_bitrate = audio_bitrate
        self.use_hardware_encoding = use_hardware_encoding
        
        self.video_pipeline = None
        self.audio_pipeline = None
        self.loop = None
        self.thread = None
        self.is_running = False
        self._stop_requested = False
        
        # Initialize GStreamer
        Gst.init(None)
        
        logger.info(f"Camera streamer initialized: {width}x{height}@{framerate}fps")
        logger.info(f"Video source: {video_source.value}")
        logger.info(f"Audio source: {audio_source.value}")
        logger.info(f"RTSP URL: {self.rtsp_url}")
        logger.info(f"Hardware encoding: {use_hardware_encoding}")
    
    def _build_video_pipeline_string(self):
        """Build video pipeline string"""
        
        video_caps = (
            f"video/x-raw,width={self.width},height={self.height},"
            f"framerate={self.framerate}/1"
        )
        
        # Video source
        if self.video_source == CameraSource.TEST_PATTERN:
            video_source = "videotestsrc is-live=true"
        elif self.video_source == CameraSource.V4L2:
            video_source = "v4l2src device=/dev/video0"
        elif self.video_source == CameraSource.LIBCAMERA:
            video_source = "libcamerasrc"
        else:
            raise ValueError(f"Unknown video source: {self.video_source}")
        
        # Video encoder
        if self.use_hardware_encoding:
            video_encoder = (
                f"v4l2h264enc extra-controls=\"controls,video_bitrate={self.video_bitrate}\" ! "
                f"video/x-h264,profile=baseline,level=(string)3.1"
            )
        else:
            video_encoder = (
                f"x264enc "
                f"bitrate={self.video_bitrate//1000} "
                f"speed-preset=ultrafast "
                f"tune=zerolatency "
                f"key-int-max={self.framerate * 2} "
                f"bframes=0 "
                f"! "
                f"video/x-h264,profile=baseline"
            )
        
        # Complete video pipeline
        pipeline = (
            f"{video_source} ! "
            f"{video_caps} ! "
            f"videoconvert ! "
            f"video/x-raw,format=I420 ! "
            f"{video_encoder} ! "
            f"h264parse config-interval=-1 ! "
            f"rtspclientsink location={self.rtsp_url} protocols=tcp latency=200"
        )
        
        return pipeline
    
    def _build_audio_pipeline_string(self):
        """Build audio pipeline string (sends to same stream path with ?audio suffix)"""
        
        if self.audio_source == AudioSource.NONE:
            return None
        
        # Audio source
        if self.audio_source == AudioSource.TEST_TONE:
            audio_source = "audiotestsrc is-live=true wave=ticks"
        elif self.audio_source == AudioSource.ALSA:
            if self.audio_device:
                audio_source = f"alsasrc device={self.audio_device}"
            else:
                audio_source = "alsasrc"
        elif self.audio_source == AudioSource.PULSE:
            audio_source = "pulsesrc"
        else:
            raise ValueError(f"Unknown audio source: {self.audio_source}")
        
        # For now, we'll use a simpler approach: save audio for when we have hardware
        # GStreamer's rtspclientsink with audio is tricky without proper muxing
        logger.warning("Audio streaming not yet fully implemented - needs hardware testing")
        return None
    
    def start(self):
        """Start the camera stream"""
        if self.is_running:
            logger.warning("Stream already running")
            return
        
        try:
            # Build and start video pipeline
            video_pipeline_str = self._build_video_pipeline_string()
            logger.info(f"Video pipeline: {video_pipeline_str}")
            
            self.video_pipeline = Gst.parse_launch(video_pipeline_str)
            
            # Set up bus to watch for messages
            bus = self.video_pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", self._on_bus_message)
            
            # Start video pipeline
            ret = self.video_pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                raise RuntimeError("Unable to set video pipeline to PLAYING state")
            
            # TODO: Audio pipeline when hardware is available
            if self.audio_source != AudioSource.NONE:
                logger.warning("Audio source specified but audio streaming needs hardware testing")
            
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
        
        # Stop video pipeline
        if self.video_pipeline:
            self.video_pipeline.set_state(Gst.State.NULL)
            self.video_pipeline = None
        
        # Stop audio pipeline
        if self.audio_pipeline:
            self.audio_pipeline.set_state(Gst.State.NULL)
            self.audio_pipeline = None
        
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
            if message.src == self.video_pipeline:
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
        if not self.video_pipeline:
            return {}
        
        return {
            "is_running": self.is_running,
            "rtsp_url": self.rtsp_url,
            "resolution": f"{self.width}x{self.height}",
            "framerate": self.framerate,
            "video_bitrate": self.video_bitrate,
            "audio_enabled": False,  # Not yet implemented
            "audio_bitrate": 0
        }
