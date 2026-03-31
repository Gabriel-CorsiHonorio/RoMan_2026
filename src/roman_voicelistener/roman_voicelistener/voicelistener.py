#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from roman_msgs.msg import SpeakerData
from std_msgs.msg import Int32
import speech_recognition as sr
from ctypes import *

# 🔇 Disable ALSA warnings
ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)
def py_error_handler(filename, line, function, err, fmt):
    pass

c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
asound = cdll.LoadLibrary('libasound.so.2')
asound.snd_lib_error_set_handler(c_error_handler)


class VoiceListener(Node):
    def __init__(self):
        super().__init__('voice_listener')

        self.publisher_ = self.create_publisher(SpeakerData, '/speakersay', 10)
        self.pub_trigger_mic = self.create_publisher(Int32, '/trigger_mic', 10)

        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()

        # Tune for speed
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True

        # Calibrate once
        with self.microphone as source:
            self.get_logger().info("Calibrating microphone...")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)

        # Timer loop (fast cycle)
        self.timer = self.create_timer(0.1, self.listen_step)

        self.listening = False

        self.get_logger().info("Voice listener started (single-thread, fast mode)")

    def listen_step(self):
        if self.listening:
            return  # prevent overlap

        self.listening = True

        try:
            with self.microphone as source:
                # 🔥 VERY IMPORTANT: short listen window
                audio = self.recognizer.listen(
                    source,
                    timeout=0.5,          # wait max 0.5s for speech
                    phrase_time_limit=1.5 # max phrase length
                )

            command = self.recognizer.recognize_faster_whisper(audio).lower()

            self.get_logger().info(f"Recognized: '{command}'")

            if "robot" in command or "robert" in command:
                command_to_publish = command.replace("robot", "").strip()

                msg = SpeakerData()
                msg.phrase = command_to_publish

                self.publisher_.publish(msg)
                self.pub_trigger_mic.publish(Int32(data=1))

                self.get_logger().info(f"Published: '{msg.phrase}'")

        except sr.WaitTimeoutError:
            # No speech detected → normal
            pass
        except sr.UnknownValueError:
            pass
        except Exception as e:
            self.get_logger().error(f"Error: {e}")

        self.listening = False


def main(args=None):
    rclpy.init(args=args)
    node = VoiceListener()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()