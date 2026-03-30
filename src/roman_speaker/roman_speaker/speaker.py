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
from roman_msgs.msg import Cmd1Data
import os
import subprocess
import sys
import argparse



OUTPUT_DIR = "tts_output"
CONDITIONS = ["no_justification", "justification_true", "justification_false"]
# ─────────────────────────────────────────────────────────────────────────────
# Nó
# ─────────────────────────────────────────────────────────────────────────────

class SpeakerNode(Node):
    def __init__(self):
        super().__init__('speaker_node')
        self.get_logger().info('Speaker node started. Waiting for /command1...')

        self.pub_start_time_speaker = self.create_publisher(Int32, '/start_time_speaker', 10)

        self.create_subscription(Cmd1Data, '/command1', self._on_command1, 10)

    def _on_command1(self, msg: Cmd1Data):
        """
        Espera uma string no formato: "item_name,suggestion"
        Exemplo: "Tetra Pak,True"
        """

        suggestion = msg.suggestion
        item_name = msg.item_name
        classification = msg.classification

        self.get_logger().info(f'\n[SPEAKER] Item: {item_name}')
        
        
        # Printa a justificativa
        self.get_logger().info(f'\n[SPEAKER] Item: {item_name}')


        self.handler_speaker(item_name=item_name, suggestion=suggestion, classification=classification)
        
        # Publica /start_time_speaker
        timer_msg = Int32()
        timer_msg.data = 1
        self.pub_start_time_speaker.publish(timer_msg)
        self.get_logger().info('Published /start_time_speaker: 1')

    def find_wav(self, base_dir: str, item_name: str, condition: str) -> str | None:
        """Return the WAV path if it exists, else None."""
        self.path_wav = os.path.join(base_dir, condition, f"{item_name}.wav")
        self.get_logger().info(f'Path {self.path_wav}')


    def play_wav(self, path: str) -> None:
        subprocess.run(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
            check=True
        )


    def handler_speaker(self, item_name: str, suggestion: bool,  classification: str):

        parser = argparse.ArgumentParser()
        parser.add_argument("--dir", default=OUTPUT_DIR,
                            help=f"Base tts_output directory (default: {OUTPUT_DIR})")
        args = parser.parse_args()
        base_dir = args.dir

        print(f"WAV Player — reads from '{base_dir}/'")

        if classification == 'no_justification':

            if suggestion:
                condition = 'no_justification_true'

            else:
                condition = 'no_justification_false'

        else:

            if suggestion:
                condition = 'justification_true'

            else:
                condition = 'justification_false'

        self.find_wav(base_dir, item_name, condition)
        print(f"  ▶ [{condition}] {item_name}.wav")
        if self.path_wav is None:
            self.get_logger().error(f"WAV file not found for {item_name} in {condition}")
            return

        self.play_wav(self.path_wav)



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