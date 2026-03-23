#!/usr/bin/env python3
"""
data_container.py — RoMan Data Container Node
===============================================
Subscreve:
  /candidate_data  (roman_msgs/CandidateData)  → cria o CSV do participante
  /data_results    (roman_msgs/DataResults)     → acrescenta uma linha ao CSV

O CSV é salvo em ~/roman_data/<id>_<name>.csv
Colunas: item_name, difficulty, ground_truth, suggestion, classification,
         time_arm, time_speaker, result
"""

import os
import csv
from pathlib import Path
from datetime import datetime

import rclpy
from rclpy.node import Node
from roman_msgs.msg import CandidateData, DataResults


# Diretório base onde os CSVs serão salvos
DATA_DIR = Path.home() / 'roman_data'

CSV_COLUMNS = [
    'item_name',
    'difficulty',
    'ground_truth',
    'suggestion',
    'classification',
    'time_arm',
    'time_speaker',
    'result',
]


class DataContainerNode(Node):
    def __init__(self):
        super().__init__('data_container_node')
        self.get_logger().info('Data container node started.')

        # Estado do participante atual
        self._candidate_id   : int  = -1
        self._candidate_name : str  = ''
        self._csv_path       : Path | None = None
        self._trial_count    : int  = 0

        # Garante que o diretório de dados existe
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        self.create_subscription(CandidateData, '/candidate_data', self._on_candidate_data, 10)
        self.create_subscription(DataResults,   '/data_results',   self._on_data_results,   10)

    # ─────────────────────────────────────────────────────────────────────────

    def _on_candidate_data(self, msg: CandidateData):
        """Cria (ou reabre) o CSV do participante."""
        self._candidate_id   = msg.id
        self._candidate_name = msg.name
        self._trial_count    = 0

        # Nome do arquivo: <id>_<name>_<timestamp>.csv
        safe_name  = msg.name.replace(' ', '_')
        timestamp  = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename   = f'{msg.id}_{safe_name}_{timestamp}.csv'
        self._csv_path = DATA_DIR / filename

        # Cria o arquivo e escreve o cabeçalho
        with open(self._csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Cabeçalho com info do participante
            writer.writerow([f'# id={msg.id}', f'name={msg.name}', f'gender={msg.gender}'])
            writer.writerow(CSV_COLUMNS)

        self.get_logger().info(
            f'CSV created for participant {msg.id} ({msg.name}): {self._csv_path}'
        )

    def _on_data_results(self, msg: DataResults):
        """Acrescenta uma linha de trial ao CSV."""
        if self._csv_path is None:
            self.get_logger().warn(
                '/data_results received but no candidate CSV is open. '
                'Waiting for /candidate_data first.'
            )
            return

        self._trial_count += 1

        row = [
            msg.item_name,
            msg.difficulty,
            msg.ground_truth,
            str(msg.suggestion),
            msg.classification,
            f'{msg.time_arm:.4f}',
            f'{msg.time_speaker:.4f}',
            msg.result,
        ]

        with open(self._csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(row)

        self.get_logger().info(
            f'Trial {self._trial_count} saved → item={msg.item_name} '
            f'result={msg.result} '
            f'time_arm={msg.time_arm:.3f}s '
            f'time_speaker={msg.time_speaker:.3f}s'
        )


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def main(args=None):
    rclpy.init(args=args)
    node = DataContainerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()