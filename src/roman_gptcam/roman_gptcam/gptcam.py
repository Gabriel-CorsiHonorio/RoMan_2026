#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Int32
import cv2
import base64
import threading
import os
import json
import re

from openai import OpenAI


class GPTVisionNode(Node):
    def __init__(self):
        super().__init__('gpt_vision_node')

        self.subscription = self.create_subscription(
            Int32,
            '/trigger_gpt',
            self.callback,
            10
        )

        # Two publishers
        self.justification_pub = self.create_publisher(String, '/gpt_response', 10)
        self.class_pub = self.create_publisher(String, '/trash_class', 10)

        self.client = OpenAI(api_key="API_KEY")

        self.get_logger().info("GPT Vision Node Ready")

    def callback(self, msg):
        # Run heavy work in separate thread
        threading.Thread(target=self.process_request).start()

    def process_request(self):
        self.get_logger().info("Capturing image...")

        cap = cv2.VideoCapture(2, cv2.CAP_V4L2)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            self.get_logger().error("Failed to capture image")
            return

        # Encode image
        _, buffer = cv2.imencode('.jpg', frame)
        img_base64 = base64.b64encode(buffer).decode('utf-8')

        prompt = """
You are a recycling assistant in Paris.

Task:
1. Detect the trash item in the center of the image (It is not the cardboard boxes).
2. Classify it as:
   - recyclable
   - non-recyclable
   according to Paris recycling rules.
3. Provide a short justification.

Return ONLY JSON:
{
  "classification": "recyclable | non-recyclable",
  "justification": "..."
}
"""

        try:
            self.get_logger().info("Sending request to GPT...")

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{img_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=200
            )

            content = response.choices[0].message.content
            self.get_logger().info(f"Raw GPT output: {content}")

            # 🔹 Remove markdown code block if present
            cleaned = re.sub(r"```json|```", "", content).strip()

            try:
                data = json.loads(cleaned)
                classification = data.get("classification", "unknown")
                justification = data.get("justification", "no justification")

            except json.JSONDecodeError:
                self.get_logger().error("Failed to parse JSON, sending raw output")
                classification = "unknown"
                justification = cleaned

            # 🔹 Publish classification
            class_msg = String()
            class_msg.data = classification
            self.class_pub.publish(class_msg)

            # 🔹 Publish justification
            just_msg = String()
            just_msg.data = justification
            self.justification_pub.publish(just_msg)

            self.get_logger().info("Published classification and justification")

        except Exception as e:
            self.get_logger().error(f"GPT request failed: {e}")


def main(args=None):
    rclpy.init(args=args)
    node = GPTVisionNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()