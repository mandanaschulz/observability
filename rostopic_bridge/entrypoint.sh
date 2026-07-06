#!/bin/bash
set -e
source /opt/ros/humble/setup.bash
exec python3 /app/bridge_node.py "$@"