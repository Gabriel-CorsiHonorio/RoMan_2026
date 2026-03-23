#!/usr/bin/env python3
"""
manager.py — RoMan Manager Node
=================================
Subscreve:
  /sam_data         (roman_msgs/SamData)   → salva dados do item selecionado
  /trigger          (std_msgs/Int32)        → publica comandos ao robô
  /result           (std_msgs/String)       → para timers e publica /data_results
  /start_time_arm   (std_msgs/Int32)        → inicia contador time_arm
  /start_time_speaker (std_msgs/Int32)      → inicia contador time_speaker

Publica:
  /command0         (std_msgs/String)       → ação principal do robô
  /command1         (std_msgs/String)       → comando secundário (item + suggestion)
  /data_results     (roman_msgs/DataResults) → dados completos do trial
"""

import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Int32
from roman_msgs.msg import SamData, DataResults, Cmd1Data


class ManagerNode(Node):
    def __init__(self):
        super().__init__('manager_node')
        self.get_logger().info('Manager node started.')

        # ── Publishers ────────────────────────────────────────────────────────
        self.pub_command0    = self.create_publisher(String,      '/command0',    10)
        self.pub_command1    = self.create_publisher(Cmd1Data,      '/command1',    10)
        self.pub_data_results = self.create_publisher(DataResults, '/data_results', 10)

        # ── Subscribers ───────────────────────────────────────────────────────
        self.create_subscription(SamData, '/sam_data',           self._on_sam_data,          10)
        self.create_subscription(Int32,   '/trigger',            self._on_trigger,           10)
        self.create_subscription(String,  '/result',             self._on_result,            10)
        self.create_subscription(Int32,   '/start_time_arm',     self._on_start_time_arm,    10)
        self.create_subscription(Int32,   '/start_time_speaker', self._on_start_time_speaker, 10)

        # ── Estado do trial atual ─────────────────────────────────────────────
        self._reset_trial()

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _reset_trial(self):
        """Zera o estado para o próximo item."""
        self._item_name      : str  = ''
        self._difficulty     : str  = ''
        self._ground_truth   : str  = ''
        self._suggestion     : bool = True
        self._classification : str  = ''
        self._result         : str  = ''

        # Timers: None = ainda não iniciado
        self._t_arm_start     : float | None = None
        self._t_speaker_start : float | None = None
        self._time_arm        : float = 0.0
        self._time_speaker    : float = 0.0

    def _opposite(self, ground_truth: str) -> str:
        """Retorna o oposto de ground_truth."""
        return 'waste' if ground_truth == 'recycle' else 'recycle'

    # ─────────────────────────────────────────────────────────────────────────
    # Callbacks
    # ─────────────────────────────────────────────────────────────────────────

    def _on_sam_data(self, msg: SamData):
        """Salva os dados do item selecionado pelo participante."""
        self._item_name      = msg.item_name
        self._difficulty     = msg.difficulty
        self._ground_truth   = msg.ground_truth
        self._suggestion     = msg.suggestion
        self._classification = msg.classification
        self.get_logger().info(
            f'/sam_data received → item={self._item_name} '
            f'gt={self._ground_truth} suggestion={self._suggestion} '
            f'classification={self._classification}'
        )

    def _on_trigger(self, msg: Int32):
        """
        Ao receber /trigger:
          - Publica /command0 com ground_truth (se suggestion) ou oposto
          - Se classification==justification e ground_truth==recycle:
              publica /command1 com item_name e suggestion
        """
        if not self._item_name:
            self.get_logger().warn('/trigger received but no sam_data stored yet — ignoring.')
            return

        # ── /command0 ──
        if self._suggestion:
            command0_value = self._ground_truth
        else:
            command0_value = self._opposite(self._ground_truth)

        cmd0 = String()
        cmd0.data = command0_value
        self.pub_command0.publish(cmd0)
        self.get_logger().info(f'Published /command0: {command0_value}')

        # ── /command1 (somente justification) ──
        if self._classification == 'justification':
            cmd1 = Cmd1Data()
            cmd1.item_name = self._item_name
            cmd1.suggestion = self._suggestion
            self.pub_command1.publish(cmd1)
            self.get_logger().info(
                f'Published /command1: item_name={self._item_name} suggestion={self._suggestion}'
            )

    def _on_start_time_arm(self, msg: Int32):
        """Inicia o contador de tempo do braço."""
        self._t_arm_start = time.monotonic()
        self.get_logger().info('Timer arm started.')

    def _on_start_time_speaker(self, msg: Int32):
        """Inicia o contador de tempo do speaker."""
        self._t_speaker_start = time.monotonic()
        self.get_logger().info('Timer speaker started.')

    def _on_result(self, msg: String):
        """
        Para os timers, monta o DataResults e publica em /data_results.
        Zera as variáveis de tempo para não contaminar o próximo trial.
        """
        now = time.monotonic()

        # Para e calcula time_arm
        if self._t_arm_start is not None:
            self._time_arm = now - self._t_arm_start
        else:
            self._time_arm = 0.0   # timer nunca foi iniciado neste trial

        # Para e calcula time_speaker
        if self._t_speaker_start is not None:
            self._time_speaker = now - self._t_speaker_start
        else:
            self._time_speaker = 0.0

        self._result = msg.data

        self.get_logger().info(
            f'/result received → result={self._result} '
            f'time_arm={self._time_arm:.3f}s '
            f'time_speaker={self._time_speaker:.3f}s'
        )

        # ── Publica dados completos ──
        data = DataResults()
        data.item_name      = self._item_name
        data.difficulty     = self._difficulty
        data.ground_truth   = self._ground_truth
        data.suggestion     = self._suggestion
        data.classification = self._classification
        data.time_arm       = self._time_arm
        data.time_speaker   = self._time_speaker
        data.result         = self._result

        self.pub_data_results.publish(data)
        self.get_logger().info(f'Published /data_results for item: {self._item_name}')

        # ── Zera APENAS os tempos para o próximo trial ──
        # (os dados do item serão sobrescritos pelo próximo /sam_data)
        self._t_arm_start     = None
        self._t_speaker_start = None
        self._time_arm        = 0.0
        self._time_speaker    = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def main(args=None):
    rclpy.init(args=args)
    node = ManagerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()