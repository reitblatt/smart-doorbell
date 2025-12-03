#!/usr/bin/env python3
"""
Audio management for two-way communication
Handles microphone input and speaker output
"""

import pyaudio
import logging
import threading
import queue
import time
from dataclasses import dataclass
from typing import Optional, Callable

logger = logging.getLogger(__name__)

@dataclass
class AudioDevice:
    """Audio device information"""
    index: int
    name: str
    channels: int
    sample_rate: int
    is_input: bool
    is_default: bool

class AudioManager:
    """
    Manages audio capture and playback for doorbell
    """
    
    # Audio configuration
    CHUNK_SIZE = 1024  # Samples per buffer
    FORMAT = pyaudio.paInt16  # 16-bit audio
    CHANNELS = 1  # Mono
    RATE = 16000  # 16kHz sample rate (good for voice)
    
    def __init__(self, 
                 input_device_index: Optional[int] = None,
                 output_device_index: Optional[int] = None):
        """
        Initialize audio manager
        
        Args:
            input_device_index: Specific microphone device (None = default)
            output_device_index: Specific speaker device (None = default)
        """
        self.input_device_index = input_device_index
        self.output_device_index = output_device_index
        
        self.audio = pyaudio.PyAudio()
        self.input_stream = None
        self.output_stream = None
        
        self.is_capturing = False
        self.is_playing = False
        
        self.capture_thread = None
        self.playback_thread = None
        
        self.audio_queue = queue.Queue(maxsize=100)
        self.playback_queue = queue.Queue(maxsize=100)
        
        self.audio_callback: Optional[Callable[[bytes], None]] = None
        
        logger.info("Audio manager initialized")
        logger.info(f"Microphone: device {input_device_index or 'default'}")
        logger.info(f"Speaker: device {output_device_index or 'default'}")
    
    def list_devices(self):
        """List all available audio devices"""
        devices = []
        
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            
            device = AudioDevice(
                index=i,
                name=info['name'],
                channels=info['maxInputChannels'] if info['maxInputChannels'] > 0 
                        else info['maxOutputChannels'],
                sample_rate=int(info['defaultSampleRate']),
                is_input=info['maxInputChannels'] > 0,
                is_default=(i == self.audio.get_default_input_device_info()['index'] 
                           if info['maxInputChannels'] > 0 
                           else i == self.audio.get_default_output_device_info()['index'])
            )
            devices.append(device)
            
        return devices
    
    def print_devices(self):
        """Print available audio devices"""
        devices = self.list_devices()
        
        print("\n" + "=" * 60)
        print("AUDIO DEVICES")
        print("=" * 60)
        
        print("\nInput Devices (Microphones):")
        for d in devices:
            if d.is_input:
                default = " [DEFAULT]" if d.is_default else ""
                print(f"  [{d.index}] {d.name}{default}")
                print(f"      Channels: {d.channels}, Rate: {d.sample_rate}Hz")
        
        print("\nOutput Devices (Speakers):")
        for d in devices:
            if not d.is_input and d.channels > 0:
                default = " [DEFAULT]" if d.is_default else ""
                print(f"  [{d.index}] {d.name}{default}")
                print(f"      Channels: {d.channels}, Rate: {d.sample_rate}Hz")
        
        print("=" * 60 + "\n")
    
    def start_capture(self, callback: Optional[Callable[[bytes], None]] = None):
        """
        Start capturing audio from microphone
        
        Args:
            callback: Function to call with each audio chunk (bytes)
        """
        if self.is_capturing:
            logger.warning("Already capturing audio")
            return
        
        self.audio_callback = callback
        
        try:
            # Open input stream
            self.input_stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=self.CHUNK_SIZE,
                stream_callback=self._input_callback if callback else None
            )
            
            self.is_capturing = True
            
            # If no callback, start thread to queue audio
            if not callback:
                self.capture_thread = threading.Thread(
                    target=self._capture_loop,
                    daemon=True
                )
                self.capture_thread.start()
            
            logger.info("Audio capture started")
            
        except Exception as e:
            logger.error(f"Failed to start audio capture: {e}")
            raise
    
    def stop_capture(self):
        """Stop capturing audio"""
        if not self.is_capturing:
            return
        
        logger.info("Stopping audio capture...")
        self.is_capturing = False
        
        if self.input_stream:
            self.input_stream.stop_stream()
            self.input_stream.close()
            self.input_stream = None
        
        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)
            self.capture_thread = None
        
        logger.info("Audio capture stopped")
    
    def start_playback(self):
        """Start playing audio to speaker"""
        if self.is_playing:
            logger.warning("Already playing audio")
            return
        
        try:
            # Open output stream
            self.output_stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                output=True,
                output_device_index=self.output_device_index,
                frames_per_buffer=self.CHUNK_SIZE
            )
            
            self.is_playing = True
            
            # Start playback thread
            self.playback_thread = threading.Thread(
                target=self._playback_loop,
                daemon=True
            )
            self.playback_thread.start()
            
            logger.info("Audio playback started")
            
        except Exception as e:
            logger.error(f"Failed to start audio playback: {e}")
            raise
    
    def stop_playback(self):
        """Stop playing audio"""
        if not self.is_playing:
            return
        
        logger.info("Stopping audio playback...")
        self.is_playing = False
        
        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
            self.output_stream = None
        
        if self.playback_thread:
            self.playback_thread.join(timeout=2.0)
            self.playback_thread = None
        
        logger.info("Audio playback stopped")
    
    def queue_audio(self, audio_data: bytes):
        """Queue audio data for playback"""
        try:
            self.playback_queue.put_nowait(audio_data)
        except queue.Full:
            logger.warning("Playback queue full, dropping audio")
    
    def get_audio(self, timeout: float = 1.0) -> Optional[bytes]:
        """Get captured audio from queue"""
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def _input_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback for input stream"""
        if status:
            logger.warning(f"Input status: {status}")
        
        if self.audio_callback:
            self.audio_callback(in_data)
        
        return (None, pyaudio.paContinue)
    
    def _capture_loop(self):
        """Thread loop for capturing audio to queue"""
        logger.debug("Capture loop started")
        
        while self.is_capturing:
            try:
                if self.input_stream and self.input_stream.is_active():
                    data = self.input_stream.read(self.CHUNK_SIZE, 
                                                   exception_on_overflow=False)
                    
                    try:
                        self.audio_queue.put_nowait(data)
                    except queue.Full:
                        logger.warning("Audio queue full, dropping frame")
                else:
                    time.sleep(0.01)
                    
            except Exception as e:
                logger.error(f"Error in capture loop: {e}")
                time.sleep(0.1)
        
        logger.debug("Capture loop stopped")
    
    def _playback_loop(self):
        """Thread loop for playing queued audio"""
        logger.debug("Playback loop started")
        
        while self.is_playing:
            try:
                # Get audio from queue with timeout
                audio_data = self.playback_queue.get(timeout=0.1)
                
                if self.output_stream and self.output_stream.is_active():
                    self.output_stream.write(audio_data)
                    
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in playback loop: {e}")
                time.sleep(0.1)
        
        logger.debug("Playback loop stopped")
    
    def cleanup(self):
        """Clean up audio resources"""
        logger.info("Cleaning up audio manager...")
        
        self.stop_capture()
        self.stop_playback()
        
        if self.audio:
            self.audio.terminate()
            self.audio = None
        
        logger.info("Audio manager cleaned up")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
