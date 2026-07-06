#!/usr/bin/env python3
"""
Generic ROS 2 -> HTTP bridge node.

Subscribes to every topic listed in manifest.yaml, flattens each message
using ROS 2's built-in introspection (no per-topic conversion code), and POSTs it as
JSON to Fluent Bit's HTTP input using the topic name as the URL path (Tag).
"""
import argparse
import json
import queue
import threading
import time
import uuid
from pathlib import Path

import requests
import yaml
import rclpy
from rclpy.node import Node
from rosidl_runtime_py.utilities import get_message
from rosidl_runtime_py.convert import message_to_ordereddict


class HttpSender(threading.Thread):
    """Owns all HTTP delivery to Fluent Bit on its own thread."""

    def __init__(self, url, logger, max_queue=1000, max_retries=3, timeout=0.5):
        super().__init__(daemon=True)
        self.url = url.rstrip('/')
        self.logger = logger
        self.q = queue.Queue(maxsize=max_queue)
        self.max_retries = max_retries
        self.timeout = timeout
        self.stop_event = threading.Event()

    def send(self, record: dict, tag: str):
        try:
            # Wir übergeben ein Tuple aus Tag und Record an die Queue
            self.q.put_nowait((tag, record))
        except queue.Full:
            self.logger.warn("HTTP send queue full, dropping record")

    def run(self):
        # Initialisierung der Session im Kontext des Hintergrund-Threads
        self.session = requests.Session()
        while not self.stop_event.is_set():
            try:
                item = self.q.get(timeout=0.2)
            except queue.Empty:
                continue
            
            self._post_with_retries(item)

    def _post_with_retries(self, item):
        tag, record = item
        body = json.dumps(record)
        
        target_url = f"{self.url}/{tag}"
        
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.post(
                    target_url, data=body,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout,
                )
                if resp.status_code in (200, 201, 204):
                    return
                self.logger.warn(f"Fluent Bit returned {resp.status_code} (attempt {attempt})")
            except requests.RequestException as e:
                self.logger.warn(f"POST failed (attempt {attempt}): {e}")
            time.sleep(0.2 * attempt)
        self.logger.error(f"Dropping record for tag '{tag}' after repeated failures")

    def stop(self):
        self.stop_event.set()


class GenericTopicLogger(Node):
    def __init__(self, manifest_path: str, fluentbit_url: str):
        super().__init__('generic_topic_logger')
        self.run_id = str(uuid.uuid4())

        self.sender = HttpSender(fluentbit_url, self.get_logger())
        self.sender.start()

        manifest_path = Path(manifest_path).resolve()
        manifest_dir = manifest_path.parent
        manifest = yaml.safe_load(manifest_path.read_text())

        self.get_logger().info(f"run_id={self.run_id} -> {fluentbit_url}")

        for entry in manifest:
            topic = entry['topic']
            type_str = entry['type']
            min_interval = float(entry.get('min_interval', 0.0))

            try:
                msg_class = get_message(type_str)
            except (ValueError, ModuleNotFoundError) as e:
                self.get_logger().error(
                    f"Could not resolve type '{type_str}' for {topic}: {e}. Skipping."
                )
                continue

            self.create_subscription(
                msg_class, topic,
                self._make_callback(topic, type_str, min_interval),
                10,
            )
            self.get_logger().info(f"Subscribed to {topic} ({type_str})")

    def _make_callback(self, topic, type_str, min_interval):
        state = {'last': 0.0}

        def handler(msg):
            now = time.time()
            if now - state['last'] < min_interval:
                return
            state['last'] = now

            payload = message_to_ordereddict(msg, no_arr=True)

            record = {
                "ts": now,
                "run_id": self.run_id,
                "topic": topic,
                "type": type_str,
                "payload": payload,
            }
            
            clean_tag = topic.strip('/')
            self.sender.send(record, tag=clean_tag)

        return handler

    def destroy_node(self):
        self.get_logger().info("Stopping HTTP Sender thread...")
        self.sender.stop()
        self.sender.join(timeout=1.0)  # Aktiv auf das Beenden des Threads warten
        super().destroy_node()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', default='manifest.yaml')
    parser.add_argument('--fluentbit-url', default='http://localhost:8888/')
    args, ros_args = parser.parse_known_args()

    rclpy.init(args=ros_args)
    node = GenericTopicLogger(args.manifest, args.fluentbit_url)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()