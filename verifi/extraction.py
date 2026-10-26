# extraction.py
import cv2
import numpy as np
import dlib
import os
import sys

# اضافه کردن مسیر پروژه به sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

try:
    # بارگذاری مدل‌های Haar Cascade و dlib
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    # مسیرهای مدل‌های dlib
    predictor_path = os.path.join(current_dir, "shape_predictor_68_face_landmarks.dat")
    face_recognition_path = os.path.join(current_dir, "dlib_face_recognition_resnet_model_v1.dat")
    
    if os.path.exists(predictor_path) and os.path.exists(face_recognition_path):
        predictor = dlib.shape_predictor(predictor_path)
        face_recognizer = dlib.face_recognition_model_v1(face_recognition_path)
        detector = dlib.get_frontal_face_detector()
        print("✅ مدل‌های تشخیص چهره بارگذاری شدند")
    else:
        print("⚠️ هشدار: فایل‌های مدل dlib پیدا نشدند")
        print(f"مسیر پیش‌بینیکننده: {predictor_path}")
        print(f"مسیر تشخیص چهره: {face_recognition_path}")
        predictor = None
        face_recognizer = None
        detector = None
except Exception as e:
    print(f"⚠️ هشدار در بارگذاری مدل‌ها: {e}")
    face_cascade = None
    predictor = None
    face_recognizer = None
    detector = None


def Crop(name, image):
    """
    برش چهره از تصویر و استخراج ویژگی‌ها
    """
    if image is None:
        return False
    
    if face_cascade is None:
        print("مدل Haar Cascade بارگذاری نشده است")
        return False
    
    try:
        # تبدیل به خاکستری
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # تشخیص چهره‌ها
        faces = face_cascade.detectMultiScale(
            gray, 
            scaleFactor=1.1, 
            minNeighbors=5, 
            minSize=(30, 30)
        )
        
        if len(faces) == 0:
            print("هیچ چهره‌ای در تصویر یافت نشد")
            return False
        
        # پردازش اولین چهره پیدا شده
        x, y, w, h = faces[0]
        face_roi = image[y:y+h, x:x+w]
        
        print(f"✅ چهره برش داده شد برای {name}")
        return True
        
    except Exception as e:
        print(f"خطا در برش چهره: {e}")
        return False


def extract_face_descriptor(name, image):
    """
    استخراج ویژگی‌های چهره با استفاده از dlib
    """
    if detector is None or predictor is None or face_recognizer is None:
        print("مدل‌های dlib بارگذاری نشده‌اند")
        return False
    
    try:
        # تبدیل به خاکستری
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # تشخیص چهره با dlib
        faces = detector(gray)
        
        if len(faces) == 1:
            landmarks = predictor(gray, faces[0])
            face_descriptor = face_recognizer.compute_face_descriptor(image, landmarks)
            
            # تبدیل به آرایه numpy
            descriptor_array = np.array(face_descriptor)
            
            print(f"✅ ویژگی‌های چهره برای {name} استخراج شد")
            return descriptor_array
        else:
            print(f"تعداد چهره‌های تشخیص داده شده: {len(faces)}")
            return False
            
    except Exception as e:
        print(f"خطا در استخراج ویژگی‌های چهره: {e}")
        return False