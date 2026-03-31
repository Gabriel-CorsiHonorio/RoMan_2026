#!/usr/bin/env python3
"""
speaker.py — RoMan Speaker Node
=================================
Subscreve:
  /command1  (std_msgs/String)  → "item_name,suggestion"

Ao receber /command1:
  - Busca a justificativa do item na tabela correta (true ou false)
  - Printa a justificativa
  - Publica 1 em /start_time_speaker (std_msgs/Int32)
"""

import rclpy
import pyttsx3
from rclpy.node import Node
from std_msgs.msg import String, Int32
import os
import subprocess
import sys
import argparse
import asyncio
import edge_tts


OUTPUT_DIR = "tts_output"
CONDITIONS = ["no_justification", "justification_true", "justification_false"]
# ─────────────────────────────────────────────────────────────────────────────
# Nó
# ─────────────────────────────────────────────────────────────────────────────

class SpeakerNode(Node):
    def __init__(self):
        super().__init__('speaker_node')
        self.get_logger().info('Speaker node started. Waiting for /speakersay...')

        self.pub_speaker_finish  = self.create_publisher(Int32,      '/speaker_finish',    10)

        self.create_subscription(String, '/speakersay', self._on_speakersay, 10)

    def _on_speakersay(self, msg: String):
        phrase = msg.data

        self.get_logger().info(f'\n[SPEAKER] Phrase: {phrase}')
        
        self.handler_speaker(phrase=phrase)
        
    def handler_speaker(self, phrase: str):
        asyncio.run(self.speak(text=phrase))

    async def speak(self, text: str, voice: str = "en-US-JennyNeural"):
        communicate = edge_tts.Communicate(text, voice)
        proc = subprocess.Popen(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-"],
            stdin=subprocess.PIPE
        )
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                proc.stdin.write(chunk["data"])
        proc.stdin.close()
        proc.wait()
        self.pub_speaker_finish.publish(Int32(data=1))

# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def main(args=None):
    rclpy.init(args=args)
    node = SpeakerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()