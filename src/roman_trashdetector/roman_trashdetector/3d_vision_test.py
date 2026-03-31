import pyrealsense2 as rs
import numpy as np
import cv2

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


pipeline = rs.pipeline()
config = rs.config()
config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
pipeline.start(config)

# Colorizer for visualizing depth
colorizer = rs.colorizer()


frames = pipeline.wait_for_frames()
color_frame = frames.get_color_frame()
color_image = np.asanyarray(color_frame.get_data())
align_to = rs.stream.color
align = rs.align(align_to)

roi_points = []

def select_point(event, x, y, flags, param):
    global roi_points
    if event == cv2.EVENT_LBUTTONDOWN:
        roi_points.append((x, y))
        print(f"Point selected: ({x},{y})")

cv2.namedWindow("Select 4 ROI Points")
cv2.setMouseCallback("Select 4 ROI Points", select_point)

print("Click 4 points to define the ROI (clockwise or counter-clockwise)")

while len(roi_points) < 4:
    img_copy = color_image.copy()
    # Draw selected points
    for p in roi_points:
        cv2.circle(img_copy, p, 5, (0, 0, 255), -1)
    if len(roi_points) == 4:
        cv2.polylines(img_copy, [np.array(roi_points)], isClosed=True, color=(0, 255, 0), thickness=2)
    cv2.imshow("Select 4 ROI Points", img_copy)
    if cv2.waitKey(1) & 0xFF == 27:  # ESC to cancel
        break

# Create a mask for the ROI
roi_recycle = ROITracker(roi_points, color_image.shape, "Recycle")

cv2.destroyWindow("Select 4 ROI Points")

roi_points = []

cv2.namedWindow("Select 4 ROI Points")
cv2.setMouseCallback("Select 4 ROI Points", select_point)

print("Click 4 points to define the ROI (clockwise or counter-clockwise)")

while len(roi_points) < 4:
    img_copy = color_image.copy()
    # Draw selected points
    for p in roi_points:
        cv2.circle(img_copy, p, 5, (0, 0, 255), -1)
    if len(roi_points) == 4:
        cv2.polylines(img_copy, [np.array(roi_points)], isClosed=True, color=(0, 255, 0), thickness=2)
    cv2.imshow("Select 4 ROI Points", img_copy)
    if cv2.waitKey(1) & 0xFF == 27:  # ESC to cancel
        break

cv2.destroyWindow("Select 4 ROI Points")

# Create a mask for the ROI
roi_waste = ROITracker(roi_points, color_image.shape, "Waste")

frames = pipeline.wait_for_frames()
aligned_frames = align.process(frames)

depth_frame = aligned_frames.get_depth_frame()
color_frame = aligned_frames.get_color_frame()

depth_image = np.asanyarray(depth_frame.get_data())

# Convert to meters
depth_scale = pipeline.get_active_profile().get_device().first_depth_sensor().get_depth_scale()


roi_recycle.initialize(depth_image, color_image, depth_scale)
roi_waste.initialize(depth_image, color_image, depth_scale)

# ---------------------------
# 3️⃣ Monitor depth in ROI
# ---------------------------
try:
    while True:
        frames = pipeline.wait_for_frames()
        aligned_frames = align.process(frames)

        depth_frame = aligned_frames.get_depth_frame()
        color_frame = aligned_frames.get_color_frame()
        if not depth_frame:
            continue

        color_image = np.asanyarray(color_frame.get_data())
        depth_image = np.asanyarray(depth_frame.get_data())
        recycle_changed = roi_recycle.update(depth_image, color_image, depth_scale)
        waste_changed = roi_waste.update(depth_image, color_image, depth_scale)

        if recycle_changed:
            print("Object in recycle bin")

        if waste_changed:
            print("Object in waste bin")

        
finally:
    pipeline.stop()
    cv2.destroyAllWindows()