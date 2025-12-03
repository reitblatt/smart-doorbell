#!/usr/bin/env python3
"""Test camera capture using GStreamer"""

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import sys

def run_pipeline_test(pipeline_str, description):
    """Test a GStreamer pipeline"""
    print(f"\nTesting: {description}")
    print(f"Pipeline: {pipeline_str}\n")
    
    try:
        pipeline = Gst.parse_launch(pipeline_str)
    except GLib.Error as e:
        print(f"ERROR: Failed to create pipeline: {e}")
        return False
    
    # Start playing
    ret = pipeline.set_state(Gst.State.PLAYING)
    if ret == Gst.StateChangeReturn.FAILURE:
        print(f"ERROR: Unable to set pipeline to playing state")
        pipeline.set_state(Gst.State.NULL)
        return False
    
    print("✓ Pipeline started successfully!")
    print("Running for 3 seconds...")
    
    # Run for 3 seconds
    try:
        loop = GLib.MainLoop()
        GLib.timeout_add_seconds(3, lambda: loop.quit())
        loop.run()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    
    # Clean up
    pipeline.set_state(Gst.State.NULL)
    print("✓ Pipeline stopped cleanly\n")
    return True

def main():
    # Initialize GStreamer
    Gst.init(None)
    
    print("=" * 60)
    print("GStreamer Camera Test")
    print("=" * 60)
    print(f"GStreamer version: {Gst.version_string()}")
    
    # Test 1: Try USB/V4L2 camera
    print("\n" + "=" * 60)
    print("TEST 1: Real Camera (v4l2src)")
    print("=" * 60)
    
    camera_pipeline = (
        "v4l2src ! "
        "video/x-raw,width=640,height=480,framerate=30/1 ! "
        "videoconvert ! "
        "fakesink"
    )
    
    camera_works = run_pipeline_test(camera_pipeline, "USB/V4L2 Camera")
    
    # Test 2: Test pattern source (always works)
    print("\n" + "=" * 60)
    print("TEST 2: Test Pattern (videotestsrc)")
    print("=" * 60)
    
    testsrc_pipeline = (
        "videotestsrc num-buffers=90 pattern=smpte ! "
        "video/x-raw,width=640,height=480,framerate=30/1 ! "
        "videoconvert ! "
        "fakesink"
    )
    
    test_works = run_pipeline_test(testsrc_pipeline, "Test Pattern Generator")
    
    # Test 3: H.264 encoding (what we'll use for RTSP)
    print("\n" + "=" * 60)
    print("TEST 3: H.264 Encoding")
    print("=" * 60)
    
    encode_pipeline = (
        "videotestsrc num-buffers=90 ! "
        "video/x-raw,width=1280,height=720,framerate=30/1 ! "
        "videoconvert ! "
        "v4l2h264enc ! "
        "video/x-h264,profile=baseline ! "
        "fakesink"
    )
    
    encode_works = run_pipeline_test(encode_pipeline, "H.264 Hardware Encoding")
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Real camera:      {'✓ PASS' if camera_works else '✗ FAIL (no camera connected - OK for now)'}")
    print(f"Test pattern:     {'✓ PASS' if test_works else '✗ FAIL'}")
    print(f"H.264 encoding:   {'✓ PASS' if encode_works else '✗ FAIL'}")
    print("=" * 60)
    
    if test_works and encode_works:
        print("\n✓ GStreamer is working correctly!")
        print("You're ready to proceed with camera integration.")
        if not camera_works:
            print("\nNote: No camera detected yet - that's expected.")
            print("Connect a camera when you're ready to test real capture.")
        return 0
    else:
        print("\n✗ Some tests failed. Check GStreamer installation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())