import cv2
from image_processor import ImageDescriber
import os

class VideoDescriber:
    def __init__(self):
        self.image_describer = ImageDescriber()

    def describe_video(self, video_path, frame_interval=30):
        cap = cv2.VideoCapture(video_path)
        descriptions = []
        frame_count = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % frame_interval == 0:
                frame_path = f"temp_frame_{frame_count}.jpg"
                cv2.imwrite(frame_path, frame)
                desc = self.image_describer.describe_image(frame_path)
                descriptions.append(f"Frame {frame_count}: {desc}")
                os.remove(frame_path)

            frame_count += 1

        cap.release()
        return descriptions
