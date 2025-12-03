#!/bin/bash
# Restart doorbell service

echo "Restarting doorbell service..."
sudo systemctl restart doorbell

sleep 2

echo "Service status:"
sudo systemctl status doorbell --no-pager
