# picture.py
import cv2
import numpy as np


class PictureCamera(object):
    def __init__(self):

        self.video = cv2.VideoCapture(0)
        
        if not self.video.isOpened():
            print("⚠️ هشدار: دوربین برای عکس‌برداری پیدا نشد")
            self.test_mode = True
        else:
            self.test_mode = False
          
            self.video.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.video.set(cv2.CAP_PROP_FPS, 30)
        
        self.frame_count = 0

    def __del__(self):
        if not self.test_mode:
            self.video.release()

    def get_frame(self):
        if self.test_mode:
            # ایجاد فریم تست
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "دوربین عکس‌برداری", (150, 200), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(frame, "آماده ثبت عکس", (170, 240), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 1)
        else:
            ret, frame = self.video.read()
            if not ret:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, "خطا در دریافت تصویر", (150, 240), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        # افزودن راهنما به تصویر
        cv2.putText(frame, "برای ثبت عکس دکمه Capture را بزنید", (50, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # رسم مستطیل برای چهره
        height, width = frame.shape[:2]
        cv2.rectangle(frame, (width//4, height//4), (3*width//4, 3*height//4), (0, 255, 0), 2)
        cv2.putText(frame, "چهره خود را در اینجا قرار دهید", (width//4, height//4 - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        self.frame_count += 1
        
        # تبدیل به JPEG
        ret, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        
        return jpeg.tobytes() if ret else b''

    def capture_photo(self, filename):
        """
        ثبت عکس از دوربین
        """
        if self.test_mode:
            return False
        
        ret, frame = self.video.read()
        if ret:
            cv2.imwrite(filename, frame)
            return True
        return False