#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool

import pyrealsense2 as rs
import numpy as np
import cv2
import threading

# =========================
# Your ROITracker class here
# (paste EXACTLY as you wrote)
# =========================

class ROITracker:
    def __init__(self, roi_points, frame_shape, name="ROI"):
        self.name = name
        
        # Create mask
        self.mask = np.zeros(frame_shape[:2], dtype=np.uint8)
        cv2.fillPoly(self.mask, [np.array(roi_points, dtype=np.int32)], 255)

        # Depth references
        self.empty_min = None
        self.old_mean = None
        self.old_std = None

        # Color reference
        self.ref_color = None

        # Counters
        self.depth_frames = 0
        self.color_frames = 0

    # ---------------------------
    # Initialize baseline
    # ---------------------------
    def initialize(self, depth_image, color_image, depth_scale, num_frames=10):
        # ---- Depth init ----
        depth_roi = depth_image.copy()
        depth_roi[self.mask == 0] = 0
        depth_meters = depth_roi * depth_scale

        valid = depth_meters[depth_meters > 0]
        self.empty_min = np.min(valid)
        self.old_mean = np.mean(valid)
        self.old_std = np.std(valid)

        # ---- Color init (average multiple frames) ----
        acc = None

        for _ in range(num_frames):
            color_roi = color_image.copy()
            color_roi[self.mask == 0] = 0

            gray = cv2.cvtColor(color_roi, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            if acc is None:
                acc = gray.astype("float")
            else:
                acc += gray

        self.ref_color = (acc / num_frames).astype("uint8")

    # ---------------------------
    # Update per frame
    # ---------------------------
    def update(self, depth_image, color_image, depth_scale):
        # ---- Depth ----
        depth_roi = depth_image.copy()
        depth_roi[self.mask == 0] = 0
        depth_meters = depth_roi * depth_scale

        valid = depth_meters[depth_meters > 0]
        if len(valid) == 0:
            return False

        min_depth = np.min(valid)
        mean_dist = np.mean(valid)
        std_depth = np.std(valid)

        depth_changed = (
            abs(mean_dist - self.old_mean) > 0.0005 or
            abs(std_depth - self.old_std) > 0.3 or
            abs(min_depth - self.empty_min) > 0.01
        )

        if depth_changed:
            self.depth_frames += 1
        else:
            self.depth_frames = 0

        # ---- Color ----
        color_roi = color_image.copy()
        color_roi[self.mask == 0] = 0

        gray = cv2.cvtColor(color_roi, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        diff = cv2.absdiff(self.ref_color, gray)
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        thresh = cv2.dilate(thresh, None, iterations=2)

        change_ratio = np.sum(thresh) / (self.mask.sum())

        if change_ratio > 0.05:
            self.color_frames += 1
        else:
            self.color_frames = 0

        # ---- Final decision ----
        if self.depth_frames > 30 and self.color_frames > 30:

            # Update references (object now becomes new baseline)
            self.old_mean = mean_dist
            self.old_std = std_depth
            self.empty_min = min_depth
            self.ref_color = gray.copy()

            self.depth_frames = 0
            self.color_frames = 0

            return True

        return False


class TrashDetectorNode(Node):
    def __init__(self):
        super().__init__('trash_detector')

        # -------------------------
        # ROS interfaces
        # -------------------------
        self.create_subscription(Bool, '/calibrate', self.calibrate_callback, 10)

        self.recycle_pub = self.create_publisher(Bool, '/recycle_detected', 10)
        self.waste_pub = self.create_publisher(Bool, '/waste_detected', 10)

        # -------------------------
        # RealSense setup
        # -------------------------
        self.pipeline = rs.pipeline()
        config = rs.config()
        config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
        config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
        self.pipeline.start(config)

        self.align = rs.align(rs.stream.color)

        self.depth_scale = self.pipeline.get_active_profile() \
            .get_device().first_depth_sensor().get_depth_scale()

        # -------------------------
        # State
        # -------------------------
        self.roi_recycle = None
        self.roi_waste = None
        self.calibrated = False
        self.calibrating = False

        # Timer loop (30Hz)
        self.timer = self.create_timer(0.03, self.process_frame)

        self.get_logger().info("Trash Detector Node started")

    # =====================================
    # CALIBRATION
    # =====================================
    def calibrate_callback(self, msg):
        if msg.data and not self.calibrating:
            self.calibrating = True
            self.get_logger().info("Calibration triggered")
            threading.Thread(target=self.run_calibration).start()

    def run_calibration(self):
        frames = self.pipeline.wait_for_frames()
        color_frame = frames.get_color_frame()
        color_image = np.asanyarray(color_frame.get_data())

        def select_roi(title):
            points = []

            def click(event, x, y, flags, param):
                if event == cv2.EVENT_LBUTTONDOWN:
                    points.append((x, y))
                    print(f"{title} point: {x},{y}")

            cv2.namedWindow(title)
            cv2.setMouseCallback(title, click)

            while len(points) < 4:
                img = color_image.copy()

                for p in points:
                    cv2.circle(img, p, 5, (0, 0, 255), -1)

                if len(points) == 4:
                    cv2.polylines(img, [np.array(points)], True, (0, 255, 0), 2)

                cv2.imshow(title, img)

                if cv2.waitKey(1) & 0xFF == 27:
                    break

            cv2.destroyWindow(title)
            return points

        self.get_logger().info("Select ROI for RECYCLE bin")
        recycle_pts = select_roi("Recycle ROI")

        self.get_logger().info("Select ROI for WASTE bin")
        waste_pts = select_roi("Waste ROI")

        # Create trackers
        self.roi_recycle = ROITracker(recycle_pts, color_image.shape, "Recycle")
        self.roi_waste = ROITracker(waste_pts, color_image.shape, "Waste")

        # Initialize baseline
        frames = self.pipeline.wait_for_frames()
        aligned = self.align.process(frames)

        depth = np.asanyarray(aligned.get_depth_frame().get_data())
        color = np.asanyarray(aligned.get_color_frame().get_data())

        self.roi_recycle.initialize(depth, color, self.depth_scale)
        self.roi_waste.initialize(depth, color, self.depth_scale)

        self.calibrated = True
        self.calibrating = False

        self.get_logger().info("Calibration COMPLETE")

    # =====================================
    # MAIN LOOP
    # =====================================
    def process_frame(self):
        if not self.calibrated:
            return

        frames = self.pipeline.wait_for_frames()
        aligned = self.align.process(frames)

        depth_frame = aligned.get_depth_frame()
        color_frame = aligned.get_color_frame()

        if not depth_frame or not color_frame:
            return

        depth = np.asanyarray(depth_frame.get_data())
        color = np.asanyarray(color_frame.get_data())

        recycle_changed = self.roi_recycle.update(depth, color, self.depth_scale)
        waste_changed = self.roi_waste.update(depth, color, self.depth_scale)

        if recycle_changed:
            self.get_logger().info("Detected object in RECYCLE bin")
            msg = Bool()
            msg.data = True
            self.recycle_pub.publish(msg)

        if waste_changed:
            self.get_logger().info("Detected object in WASTE bin")
            msg = Bool()
            msg.data = True
            self.waste_pub.publish(msg)

    # =====================================
    # CLEANUP
    # =====================================
    def destroy_node(self):
        self.pipeline.stop()
        cv2.destroyAllWindows()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = TrashDetectorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()