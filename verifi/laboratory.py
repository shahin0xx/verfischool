# laboratory.py
import dlib
import cv2
import numpy as np
from django.conf import settings
import os
import json
from .models import Student
import face_recognition


class FaceLaboratory:
    """آزمایشگاه تشخیص چهره برای پردازش‌های پیشرفته"""
    
    def __init__(self):
        self.predictor = None
        self.face_recognizer = None
        self.detector = None
        self.initialized = False
        
        try:
            # مسیر مدل‌ها
            predictor_path = os.path.join(settings.BASE_DIR, "shape_predictor_68_face_landmarks.dat")
            face_recognition_path = os.path.join(settings.BASE_DIR, "dlib_face_recognition_resnet_model_v1.dat")
            
            if os.path.exists(predictor_path) and os.path.exists(face_recognition_path):
                self.predictor = dlib.shape_predictor(predictor_path)
                self.face_recognizer = dlib.face_recognition_model_v1(face_recognition_path)
                self.detector = dlib.get_frontal_face_detector()
                self.initialized = True
                print("✅ آزمایشگاه چهره راه‌اندازی شد")
            else:
                print("⚠️ مدل‌های dlib پیدا نشدند")
                
        except Exception as e:
            print(f"⚠️ خطا در راه‌اندازی آزمایشگاه: {e}")
    
    def extract_face_descriptor_dlib(self, image):
        """استخراج ویژگی‌های چهره با dlib"""
        if not self.initialized:
            return None
        
        try:
            # تبدیل به خاکستری
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # تشخیص چهره‌ها
            faces = self.detector(gray)
            
            descriptors = []
            for face in faces:
                landmarks = self.predictor(gray, face)
                face_descriptor = self.face_recognizer.compute_face_descriptor(image, landmarks)
                descriptors.append(np.array(face_descriptor))
            
            return descriptors if descriptors else None
            
        except Exception as e:
            print(f"⚠️ خطا در استخراج ویژگی‌های dlib: {e}")
            return None
    
    def extract_face_descriptor_facerec(self, image):
        """استخراج ویژگی‌های چهره با face_recognition"""
        try:
            # تشخیص چهره‌ها
            face_locations = face_recognition.face_locations(image)
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            return face_encodings if face_encodings else None
            
        except Exception as e:
            print(f"⚠️ خطا در استخراج ویژگی‌های face_recognition: {e}")
            return None
    
    def compare_faces(self, encoding1, encoding2):
        """مقایسه دو چهره"""
        try:
            if encoding1 is None or encoding2 is None:
                return 0.0
            
            # محاسبه فاصله
            distance = np.linalg.norm(encoding1 - encoding2)
            similarity = 1.0 - distance
            
            return max(0.0, min(1.0, similarity))
            
        except Exception as e:
            print(f"⚠️ خطا در مقایسه چهره‌ها: {e}")
            return 0.0
    
    def enhance_image(self, image):
        """بهبود کیفیت تصویر"""
        try:
            # افزایش کنتراست
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            # CLAHE برای بهبود کنتراست
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            
            # ترکیب مجدد
            lab = cv2.merge([l, a, b])
            enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            
            # کاهش نویز
            enhanced = cv2.medianBlur(enhanced, 3)
            
            return enhanced
            
        except Exception as e:
            print(f"⚠️ خطا در بهبود تصویر: {e}")
            return image
    
    def detect_multiple_faces(self, image_path):
        """تشخیص چندین چهره در تصویر"""
        try:
            if not os.path.exists(image_path):
                print(f"❌ فایل پیدا نشد: {image_path}")
                return []
            
            # بارگذاری تصویر
            image = cv2.imread(image_path)
            if image is None:
                print(f"❌ خطا در بارگذاری تصویر: {image_path}")
                return []
            
            # بهبود تصویر
            enhanced = self.enhance_image(image)
            
            # تشخیص چهره‌ها با چند روش
            results = []
            
            # روش ۱: با Haar Cascade
            gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            haar_faces = face_cascade.detectMultiScale(gray, 1.1, 4)
            
            # روش ۲: با face_recognition
            rgb_image = cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_image)
            
            # ادغام نتایج
            all_faces = []
            
            # اضافه کردن نتایج Haar Cascade
            for (x, y, w, h) in haar_faces:
                all_faces.append({
                    'method': 'haar',
                    'location': (y, x + w, y + h, x),  # تبدیل به فرمت face_recognition
                    'confidence': 0.8
                })
            
            # اضافه کردن نتایج face_recognition
            for (top, right, bottom, left) in face_locations:
                all_faces.append({
                    'method': 'face_recognition',
                    'location': (top, right, bottom, left),
                    'confidence': 0.9
                })
            
            # حذف تکراری‌ها (بر اساس همپوشانی)
            unique_faces = []
            for face in all_faces:
                top1, right1, bottom1, left1 = face['location']
                is_duplicate = False
                
                for unique_face in unique_faces:
                    top2, right2, bottom2, left2 = unique_face['location']
                    
                    # محاسبه همپوشانی
                    x_overlap = max(0, min(right1, right2) - max(left1, left2))
                    y_overlap = max(0, min(bottom1, bottom2) - max(top1, top2))
                    overlap_area = x_overlap * y_overlap
                    
                    area1 = (right1 - left1) * (bottom1 - top1)
                    area2 = (right2 - left2) * (bottom2 - top2)
                    
                    # اگر همپوشانی بیشتر از ۵۰٪ باشد، تکراری است
                    if overlap_area > 0.5 * min(area1, area2):
                        is_duplicate = True
                        # حفظ نتیجه با confidence بالاتر
                        if face['confidence'] > unique_face['confidence']:
                            unique_face.update(face)
                        break
                
                if not is_duplicate:
                    unique_faces.append(face)
            
            # استخراج encoding برای هر چهره
            face_encodings = face_recognition.face_encodings(rgb_image, [f['location'] for f in unique_faces])
            
            for i, (face, encoding) in enumerate(zip(unique_faces, face_encodings)):
                results.append({
                    'id': i + 1,
                    'location': face['location'],
                    'encoding': encoding,
                    'method': face['method'],
                    'confidence': face['confidence']
                })
            
            print(f"✅ {len(results)} چهره در تصویر تشخیص داده شد")
            return results
            
        except Exception as e:
            print(f"❌ خطا در تشخیص چند چهره: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def recognize_multiple_faces(self, image_path):
        """تشخیص هویت چندین چهره در تصویر"""
        try:
            # تشخیص چهره‌ها
            faces = self.detect_multiple_faces(image_path)
            
            if not faces:
                return []
            
            # بارگذاری دانش‌آموزان
            students = Student.objects.filter(is_active=True, face_encoding__isnull=False)
            
            recognized_faces = []
            
            for face in faces:
                best_match = None
                best_confidence = 0.0
                
                for student in students:
                    try:
                        # بارگذاری encoding دانش‌آموز
                        student_encoding = json.loads(student.face_encoding)
                        student_encoding = np.array(student_encoding)
                        
                        # مقایسه
                        confidence = self.compare_faces(face['encoding'], student_encoding)
                        
                        if confidence > best_confidence and confidence > 0.6:
                            best_confidence = confidence
                            best_match = student
                            
                    except Exception as e:
                        continue
                
                if best_match:
                    recognized_faces.append({
                        'student': best_match,
                        'confidence': best_confidence,
                        'location': face['location']
                    })
                else:
                    recognized_faces.append({
                        'student': None,
                        'confidence': 0.0,
                        'location': face['location']
                    })
            
            return recognized_faces
            
        except Exception as e:
            print(f"❌ خطا در تشخیص هویت چند چهره: {e}")
            return []


# نمونه آزمایشگاه
face_lab = FaceLaboratory()