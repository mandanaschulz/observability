# sensor_msgs ships with ros-base, so no custom message packages are
# needed for this particular topic. Swap the distro tag here if your
# fleet runs something other than Humble.
FROM ros:humble-ros-base

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt || \
    pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY bridge_node.py .
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]