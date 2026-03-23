#!/usr/bin/env python3
"""
generator.py — RoMan Generator Node
=====================================
Subscreve /id (std_msgs/Int32).
Ao receber um ID, seleciona aleatoriamente 8 itens da tabela de lixo
(4 recicláveis, 4 não recicláveis) e publica cada um em /exp_data
(roman_msgs/ExpData), com box_index de 0 a 7.

Classificação das caixas:
  0–3 → justification     (recicláveis)
  4–7 → no_justification  (não recicláveis)
"""

import random
import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32
from roman_msgs.msg import ExpData


# ─────────────────────────────────────────────────────────────────────────────
# Tabela de itens
# ─────────────────────────────────────────────────────────────────────────────

recycle_ITEMS = [
    # Easy
    {"item_name": "Plastic_Bottle",  "ground_truth": "recycle", "difficulty": "easy"},
    {"item_name": "Metal_Can",       "ground_truth": "recycle", "difficulty": "easy"},
    {"item_name": "Cardboard_Box",   "ground_truth": "recycle", "difficulty": "easy"},
    {"item_name": "Paper_Sheet",     "ground_truth": "recycle", "difficulty": "easy"},
    {"item_name": "Glass_Bottle",    "ground_truth": "recycle", "difficulty": "easy"},
    # Hard
    {"item_name": "Tetra_Pak",       "ground_truth": "recycle", "difficulty": "hard"},
    {"item_name": "Plastic_Bag",     "ground_truth": "recycle", "difficulty": "hard"},
    {"item_name": "Blister_Pack",    "ground_truth": "recycle", "difficulty": "hard"},
    {"item_name": "Aluminium_Foil",  "ground_truth": "recycle", "difficulty": "hard"},
    {"item_name": "Bubble_Wrap",     "ground_truth": "recycle", "difficulty": "hard"},
]

NON_recycle_ITEMS = [
    # Easy
    {"item_name": "Paper_Towel",     "ground_truth": "waste", "difficulty": "easy"},
    {"item_name": "Used_Tissue",     "ground_truth": "waste", "difficulty": "easy"},
    {"item_name": "Surgical_Mask",   "ground_truth": "waste", "difficulty": "easy"},
    {"item_name": "Food_Waste",      "ground_truth": "waste", "difficulty": "easy"},
    {"item_name": "Broken_Ceramic",  "ground_truth": "waste", "difficulty": "easy"},
    # Hard
    {"item_name": "Black_Plastic",         "ground_truth": "waste", "difficulty": "hard"},
    {"item_name": "Plasticized_Paper_Cup", "ground_truth": "waste", "difficulty": "hard"},
    {"item_name": "Waxed_Cardboard",       "ground_truth": "waste", "difficulty": "hard"},
    {"item_name": "Foam",                  "ground_truth": "waste", "difficulty": "hard"},
    {"item_name": "Wooden_Packaging",      "ground_truth": "waste", "difficulty": "hard"},
]


def sample_experiment() -> list[dict]:
    """
    Seleciona 8 itens balanceados:
      - 4 recicláveis    (2 easy + 2 hard) → box_index 0–3
      - 4 não recicláveis (2 easy + 2 hard) → box_index 4–7
    """
    def balanced_sample(pool: list[dict]) -> list[dict]:
        easy = [i for i in pool if i["difficulty"] == "easy"]
        hard = [i for i in pool if i["difficulty"] == "hard"]
        selected = random.sample(easy, 4) + random.sample(hard, 4)
        random.shuffle(selected)
        return selected

    recycle_group     = balanced_sample(recycle_ITEMS)
    non_recycle_group = balanced_sample(NON_recycle_ITEMS)

    experiment = []
    for idx, item in enumerate(recycle_group):
        experiment.append({**item, "box_index": idx})        # 0–3
    for idx, item in enumerate(non_recycle_group):
        experiment.append({**item, "box_index": idx + 8})    # 4–7

    return experiment


# ─────────────────────────────────────────────────────────────────────────────
# Nó ROS2
# ─────────────────────────────────────────────────────────────────────────────

class GeneratorNode(Node):
    def __init__(self):
        super().__init__('generator_node')
        self.get_logger().info('Generator node started. Waiting for /id...')

        self.pub_exp = self.create_publisher(ExpData, '/exp_data', 10)
        self.sub_id  = self.create_subscription(Int32, '/id', self._on_id_received, 10)

        self._current_id: int | None = None
        self._pending_timer = None  # referência ao timer ativo

    def _on_id_received(self, msg: Int32):
        pid = msg.data

        if pid == self._current_id:
            self.get_logger().warn(f'ID {pid} already active — ignoring.')
            return

        self._current_id = pid
        self.get_logger().info(f'Received ID: {pid} — generating experiment...')

        experiment = sample_experiment()
        self._publish_next(experiment, index=0)

    def _publish_next(self, experiment: list[dict], index: int):
        """Publica um item e agenda o próximo com timer one-shot."""
        if index >= len(experiment):
            self.get_logger().info('All 8 items published. Sequence complete.')
            return

        # Publica item atual
        item = experiment[index]
        msg = ExpData()
        msg.item_name    = item['item_name']
        msg.ground_truth = item['ground_truth']
        msg.difficulty   = item['difficulty']
        msg.box_index    = item['box_index']
        msg.classification = 'justification'
        msg.suggestion = True

        self.pub_exp.publish(msg)
        self.get_logger().info(
            f'  [{msg.box_index}] {msg.item_name} '
            f'({msg.difficulty}, {msg.ground_truth})'
        )

        # Cria timer one-shot: cancela a si mesmo após disparar
        def fire():
            self._pending_timer.cancel()
            self._pending_timer = None
            self._publish_next(experiment, index + 1)

        self._pending_timer = self.create_timer(0.15, fire)


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def main(args=None):
    rclpy.init(args=args)
    node = GeneratorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()