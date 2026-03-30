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
    {"item_name": "Plastic_Bottle",  "ground_truth": "recycle", "difficulty": "easy", "classification": ""},
    {"item_name": "Metal_Can",       "ground_truth": "recycle", "difficulty": "easy", "classification": ""},
    {"item_name": "Cardboard_Box",   "ground_truth": "recycle", "difficulty": "easy", "classification": ""},
    {"item_name": "Paper_Sheet",     "ground_truth": "recycle", "difficulty": "easy", "classification": ""},
    #{"item_name": "Glass_Bottle",    "ground_truth": "recycle", "difficulty": "easy", "classification": ""},
    # Hard
    {"item_name": "Tetra_Pak",       "ground_truth": "recycle", "difficulty": "hard", "classification": ""},
    {"item_name": "Plastic_Bag",     "ground_truth": "recycle", "difficulty": "hard", "classification": ""},
    {"item_name": "Blister_Pack",    "ground_truth": "recycle", "difficulty": "hard", "classification": ""},
    #{"item_name": "Aluminium_Foil",  "ground_truth": "recycle", "difficulty": "hard", "classification": ""},
    {"item_name": "Bubble_Wrap",     "ground_truth": "recycle", "difficulty": "hard", "classification": ""},
]

NON_recycle_ITEMS = [
    # Easy
    {"item_name": "Paper_Towel",     "ground_truth": "waste", "difficulty": "easy", "classification": ""},
    {"item_name": "Used_Tissue",     "ground_truth": "waste", "difficulty": "easy", "classification": ""},
    {"item_name": "Surgical_Mask",   "ground_truth": "waste", "difficulty": "easy", "classification": ""},
    #{"item_name": "Food_Waste",      "ground_truth": "waste", "difficulty": "easy", "classification": ""},
    {"item_name": "Broken_Ceramic",  "ground_truth": "waste", "difficulty": "easy", "classification": ""},
    # Hard
    {"item_name": "Black_Plastic",         "ground_truth": "waste", "difficulty": "hard", "classification": ""},
    {"item_name": "Plasticized_Paper_Cup", "ground_truth": "waste", "difficulty": "hard", "classification": ""},
    {"item_name": "Waxed_Cardboard",       "ground_truth": "waste", "difficulty": "hard", "classification": ""},
    {"item_name": "Foam",                  "ground_truth": "waste", "difficulty": "hard", "classification": ""},
    #{"item_name": "Wooden_Packaging",      "ground_truth": "waste", "difficulty": "hard", "classification": ""},
]


def sample_experiment() -> list[dict]:
    """
    16 unique items split into 2 blocks of 8.

    Each block:
      - 4 easy + 4 hard
      - shuffled
      - 2 random positions marked as incorrect
    """

    all_items = recycle_ITEMS + NON_recycle_ITEMS

    # --- Step 1: split pools
    easy_pool = [i for i in all_items if i["difficulty"] == "easy"]
    hard_pool = [i for i in all_items if i["difficulty"] == "hard"]

    # --- Step 2: sample WITHOUT repetition
    selected_easy = random.sample(easy_pool, 8)
    selected_hard = random.sample(hard_pool, 8)

    # --- Step 3: create blocks
    block1 = selected_easy[:4] + selected_hard[:4]
    block2 = selected_easy[4:] + selected_hard[4:]

    def build_block(items: list[dict]) -> list[dict]:
        # shuffle items
        random.shuffle(items)

        # pick 2 random positions for errors
        error_positions = set(random.sample(range(8), 2))

        # assign correctness directly by position
        block = []
        for idx, item in enumerate(items):
            block.append({
                **item,
                "suggestion": idx not in error_positions
            })

        return block

    # --- Step 4: build experiment
    experiment = build_block(block1) + build_block(block2)

    # --- Step 5: assign box_index
    for idx, item in enumerate(experiment):
        item["box_index"] = idx
        if idx < 8:
            item['classification'] = "no_justification"
        else:
            item["classification"] = "justification"
       
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
        msg.classification = item['classification']
        msg.suggestion = item['suggestion']

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