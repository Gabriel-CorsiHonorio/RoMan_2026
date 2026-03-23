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
from rclpy.node import Node
from std_msgs.msg import String, Int32
from roman_msgs.msg import Cmd1Data


# ─────────────────────────────────────────────────────────────────────────────
# Tabelas de justificativas
# ─────────────────────────────────────────────────────────────────────────────

# Tabela usada quando suggestion = True
# (robô sugere que o item É reciclável — justifica a reciclagem)
JUSTIFICATION_TRUE = [
    {"item_name": "Tetra Pak",             "justification": ""},
    {"item_name": "Plastic Bag",           "justification": ""},
    {"item_name": "Blister Pack",          "justification": ""},
    {"item_name": "Aluminium Foil",        "justification": ""},
    {"item_name": "Bubble Wrap",           "justification": ""},
    {"item_name": "Black Plastic",         "justification": ""},
    {"item_name": "Plasticized Paper Cup", "justification": ""},
    {"item_name": "Waxed Cardboard",       "justification": ""},
    {"item_name": "Foam",                  "justification": ""},
    {"item_name": "Wooden Packaging",      "justification": ""},
]

# Tabela usada quando suggestion = False
# (robô NÃO sugere reciclagem — justifica a não reciclagem)
JUSTIFICATION_FALSE = [
    {"item_name": "Tetra Pak",             "justification": ""},
    {"item_name": "Plastic Bag",           "justification": ""},
    {"item_name": "Blister Pack",          "justification": ""},
    {"item_name": "Aluminium Foil",        "justification": ""},
    {"item_name": "Bubble Wrap",           "justification": ""},
    {"item_name": "Black Plastic",         "justification": ""},
    {"item_name": "Plasticized Paper Cup", "justification": ""},
    {"item_name": "Waxed Cardboard",       "justification": ""},
    {"item_name": "Foam",                  "justification": ""},
    {"item_name": "Wooden Packaging",      "justification": ""},
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
        raw = msg.data.strip()

        # Separa pelo último ',' para lidar com item_names que contenham vírgula
        try:
            last_comma = raw.rfind(',')
            if last_comma == -1:
                raise ValueError('Separator not found')
            item_name      = raw[:last_comma].strip()
            suggestion_str = raw[last_comma + 1:].strip().lower()
            suggestion     = suggestion_str in ('true', '1', 'yes')
        except Exception as e:
            self.get_logger().error(f'Failed to parse /command1 "{raw}": {e}')
            return

        self.get_logger().info(
            f'/command1 → item="{item_name}" suggestion={suggestion}'
        )

        suggestion = msg.suggestion

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