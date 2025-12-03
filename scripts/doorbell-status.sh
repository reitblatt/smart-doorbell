#!/bin/bash
# Check doorbell service status

echo "=== Doorbell Service Status ==="
systemctl status doorbell --no-pager

echo ""
echo "=== MediaMTX Status ==="
systemctl status mediamtx --no-pager

echo ""
echo "=== Recent Logs (last 20 lines) ==="
journalctl -u doorbell -n 20 --no-pager

echo ""
echo "=== RTSP Stream Test ==="
echo "Test stream with:"
echo "  ffplay rtsp://$(hostname):8554/doorbell"
