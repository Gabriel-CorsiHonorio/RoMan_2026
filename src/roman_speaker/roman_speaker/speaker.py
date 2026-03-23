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

# ─────────────────────────────────────────────────────────────────────────────
# Tabelas de justificativas
# ─────────────────────────────────────────────────────────────────────────────

JUSTIFICATION_TRUE = [
    {"item_name": "Tetra_Pak",             "justification": "Composite packaging like Tetra Pak is accepted in the recycling bin in Paris."},
    {"item_name": "Plastic_Bag",           "justification": "All plastic packaging, including bags, can be sorted in the yellow bin."},
    {"item_name": "Blister_Pack",          "justification": "Mixed plastic packaging like blister packs is recyclable in the yellow bin."},
    {"item_name": "Aluminium_Foil",        "justification": "Aluminium foil can be recycled if it is not too dirty."},
    {"item_name": "Bubble_Wrap",           "justification": "Plastic protective packaging like bubble wrap goes in the recycling bin."},
    {"item_name": "Black_Plastic",         "justification": "Black plastic is not detected properly in sorting centers and cannot be recycled."},
    {"item_name": "Plasticized_Paper_Cup", "justification": "The plastic lining makes it difficult to recycle in standard facilities."},
    {"item_name": "Waxed_Cardboard",       "justification": "The wax coating prevents proper recycling of the cardboard fibers."},
    {"item_name": "Foam",                  "justification": "Foam packaging is not accepted in recycling due to processing limitations."},
    {"item_name": "Wooden_Packaging",      "justification": "Wood is not part of household packaging recycling and must be disposed separately."},
]

JUSTIFICATION_FALSE = [
    {"item_name": "Tetra_Pak",             "justification": "It contains multiple layers of materials that cannot be separated in recycling."},
    {"item_name": "Plastic_Bag",           "justification": "Thin plastic bags clog machines and are not accepted in recycling bins."},
    {"item_name": "Blister_Pack",          "justification": "The combination of plastic and aluminum makes it non-recyclable."},
    {"item_name": "Aluminium_Foil",        "justification": "Small pieces like foil are too light to be sorted properly and are discarded."},
    {"item_name": "Bubble_Wrap",           "justification": "Soft plastics like bubble wrap are not recyclable in standard systems."},
    {"item_name": "Black_Plastic",         "justification": "All plastic packaging, regardless of color, can be recycled in the yellow bin."},
    {"item_name": "Plasticized_Paper_Cup", "justification": "Paper cups are mainly cardboard and can be recycled with paper waste."},
    {"item_name": "Waxed_Cardboard",       "justification": "Cardboard is always recyclable even if it has a protective coating."},
    {"item_name": "Foam",                  "justification": "Foam packaging is a type of plastic and can be recycled with other plastics."},
    {"item_name": "Wooden_Packaging",      "justification": "Wood packaging can be processed like cardboard in recycling streams."},
]

# Índices para busca rápida por item_name
_INDEX_TRUE  = {e["item_name"]: e["justification"] for e in JUSTIFICATION_TRUE}
_INDEX_FALSE = {e["item_name"]: e["justification"] for e in JUSTIFICATION_FALSE}


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

        self.get_logger().info(f'\n[SPEAKER] Item: {item_name}')
        

        # Seleciona tabela e busca justificativa
        if suggestion:
            justification = _INDEX_TRUE.get(item_name)
            table_used = 'justification_true'
        else:
            justification = _INDEX_FALSE.get(item_name)
            table_used = 'justification_false'

        if justification is None:
            self.get_logger().warn(
                f'Item "{item_name}" not found in {table_used}.'
            )
            return

        

        # Printa a justificativa
        self.get_logger().info(f'\n[SPEAKER] Item: {item_name}')
        self.get_logger().info(f'[SPEAKER] Suggestion: {suggestion} → table: {table_used}')
        self.get_logger().info(f'[SPEAKER] Justification: {justification}\n')
        
        # Publica /start_time_speaker
        timer_msg = Int32()
        timer_msg.data = 1
        self.pub_start_time_speaker.publish(timer_msg)
        self.get_logger().info('Published /start_time_speaker: 1')


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