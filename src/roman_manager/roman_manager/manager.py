#!/usr/bin/env python3

import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Int32
from roman_msgs.msg import SpeakerData
from enum import Enum

class States(Enum):
    WAITING_FOR_VOICE_COMMAND = 1
    WAITING_FOR_POSITION = 2
    WAITING_FOR_TAKED = 3
    WAITING_FOR_GPT_RESPONSE = 4
    WAITING_FOR_SPEAKER = 5
    WAITING_FOR_FINISHED = 6

class ManagerNode(Node):
    def __init__(self):
        super().__init__('manager_node')
        self.get_logger().info('Manager node started.')

        # ── Publishers ────────────────────────────────────────────────────────
        self.pub_trigger_gpt  = self.create_publisher(Int32,      '/trigger_gpt',    10)
        self.pub_trigger_arm_cam = self.create_publisher(String,      '/get_obj_pos', 10)
        self.pub_speakersay     = self.create_publisher(String, '/speakersay',     10)
        self.pub_command0 = self.create_publisher(String,      '/command1',       10)
        self.pub_nao_recyclable = self.create_publisher(String,      '/recyclable', 10)
        self.pub_nao_non_recyclable = self.create_publisher(String,      '/non_recyclable', 10)
        # ── Subscribers ───────────────────────────────────────────────────────
        self.create_subscription(String, '/command1',           self._on_command0,          10)
        self.create_subscription(Int32, '/trigger_mic',           self._on_trigger_mic,          10)
        self.create_subscription(String, '/gpt_response',         self._on_gpt_response,       10)
        self.create_subscription(Int32, '/speaker_finish', self._on_speaker_finish,     10)
        self.create_subscription(String, '/state',            self._on_state,              10)
        self.create_subscription(String, '/trash_class',       self._on_trash_class,              10)  # Reuse state callback for trash_class updates
        # Initial state
        self.state = States.WAITING_FOR_VOICE_COMMAND
        self.get_logger().info(f'[MANAGER] Initial state: {self.state.name}')
    
        self.gpt_response = None
        self.trash_class = None
    # ─────────────────────────────────────────────────────────────────────────
    # Callbacks
    # ─────────────────────────────────────────────────────────────────────────

    def _on_trigger_mic(self, msg: Int32):
        self.get_logger().info(f'[MANAGER] Received trigger mic: {msg.data}')
        if self.state == States.WAITING_FOR_VOICE_COMMAND:
            self.get_logger().info(f'[MANAGER] Publishing to /command1 and /trigger_gpt')
            self.pub_command0.publish(String(data='position'))
            self.pub_trigger_gpt.publish(Int32(data=1))
            self.get_logger().info(f'[MANAGER] Transitioning to WAITING_FOR_POSITION')
            self.state = States.WAITING_FOR_POSITION

    def _on_command0(self, msg: String):
        self.get_logger().info(f'[MANAGER] Received command0: {msg.data}')
        if self.state == States.WAITING_FOR_POSITION and msg.data == "trash":
            self.pub_nao_recyclable.publish(String(data="Let me see what trash item you put here!"))
            self.pub_trigger_arm_cam.publish(String(data=''))
            self.get_logger().info(f'[MANAGER] Transitioning to WAITING_FOR_TAKED')
            self.state = States.WAITING_FOR_TAKED

    def _on_state(self, msg: String):
        self.get_logger().info(f'[MANAGER] Received state: {msg.data}')
        if self.state == States.WAITING_FOR_TAKED and msg.data == "taked":
            self.get_logger().info(f'[MANAGER] Transitioning to WAITING_FOR_GPT_RESPONSE')
            if self.gpt_response is not None:
                self.pub_speakersay.publish(String(data=self.gpt_response))
                if self.trash_class == "recyclable":
                    self.get_logger().info(f'[MANAGER] Publishing recyclable response to /nao_recyclable')
                    self.pub_nao_recyclable.publish(String(data=self.gpt_response))
                elif self.trash_class == "non-recyclable":
                    self.get_logger().info(f'[MANAGER] Publishing non-recyclable response to /nao_non_recyclable')
                    self.pub_nao_non_recyclable.publish(String(data=self.gpt_response))
                self.gpt_response = None
                self.state = States.WAITING_FOR_SPEAKER
                self.get_logger().info(f'[MANAGER] Published GPT response to /speakersay and transitioning to WAITING_FOR_SPEAKER')
            else:
                self.get_logger().warn(f'[MANAGER] GPT response is None, cannot publish to /speakersay')
                self.get_logger().info(f'[MANAGER] Transitioning to WAITING_FOR_SPEAKER without publishing GPT response')
                self.state = States.WAITING_FOR_GPT_RESPONSE
        elif self.state == States.WAITING_FOR_FINISHED and msg.data == "finished":
            self.get_logger().info(f'[MANAGER] Transitioning to WAITING_FOR_VOICE_COMMAND')
            self.state = States.WAITING_FOR_VOICE_COMMAND

    def _on_gpt_response(self, msg: String):
        self.get_logger().info(f'[MANAGER] Received GPT response: {msg.data}')
        self.gpt_response = msg.data
        if self.state == States.WAITING_FOR_GPT_RESPONSE:
            self.pub_speakersay.publish(String(data=self.gpt_response))
            if self.trash_class == "recyclable":
                self.get_logger().info(f'[MANAGER] Publishing recyclable response to /nao_recyclable')
                self.pub_nao_recyclable.publish(String(data=self.gpt_response))
            elif self.trash_class == "non-recyclable":
                self.get_logger().info(f'[MANAGER] Publishing non-recyclable response to /nao_non_recyclable')
                self.pub_nao_non_recyclable.publish(String(data=self.gpt_response))
            self.gpt_response = None
            self.get_logger().info(f'[MANAGER] Transitioning to WAITING_FOR_SPEAKER')
            self.state = States.WAITING_FOR_SPEAKER

    def _on_trash_class(self, msg: String):
        self.get_logger().info(f'[MANAGER] Received trash class: {msg.data}')
        self.trash_class = msg.data

    def _on_speaker_finish(self, msg: Int32):
        self.get_logger().info(f'[MANAGER] Received speaker finish: {msg.data}')
        if self.state == States.WAITING_FOR_SPEAKER:
            self.get_logger().info(f'[MANAGER] Transitioning to WAITING_45')
            self.state = States.WAITING_FOR_VOICE_COMMAND
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