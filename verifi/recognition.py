import cv2
import numpy as np
import face_recognition
import os
import json
import shutil
import time
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from django.db import DatabaseError


class FaceRecognitionSystem:
    def __init__(self):
        self.known_face_encodings = []
        self.known_face_students = []
        self._initialized = False
        
        print("\n" + "="*60)
        print("🚀 سیستم تشخیص چهره مدرسه")
        print("="*60)
        
        self.initialize()
    
    def log(self, message, level="info"):
        icons = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}
        icon = icons.get(level, "ℹ️")
        timestamp = timezone.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {icon} {message}")
    
    def initialize(self):
        if self._initialized:
            return
        
        try:
            from .models import Student
            try:
                Student.objects.exists()
                self.load_known_faces()
                self._initialized = True
                self.log("سیستم تشخیص چهره راه‌اندازی شد", "success")
                self.log(f"تعداد چهره‌های بارگذاری شده: {len(self.known_face_encodings)}", "info")
            except DatabaseError as e:
                self.log(f"جدول‌ها هنوز ایجاد نشده‌اند: {e}", "warning")
        except Exception as e:
            self.log(f"خطا در راه‌اندازی: {e}", "error")
    
    def normalize_encoding(self, encoding):
        try:
            if isinstance(encoding, np.ndarray):
                if encoding.ndim == 2:
                    encoding = encoding.flatten()
                
                if encoding.shape[0] != 128:
                    if encoding.shape[0] > 128:
                        encoding = encoding[:128]
                    else:
                        padding = 128 - encoding.shape[0]
                        encoding = np.pad(encoding, (0, padding), mode='constant')
                
                return encoding
            elif isinstance(encoding, list):
                encoding = np.array(encoding, dtype=np.float64)
                return self.normalize_encoding(encoding)
            else:
                return None
                
        except Exception as e:
            self.log(f"خطا در نرمالایز کردن encoding: {e}", "error")
            return None
    
    def load_known_faces(self):
        from .models import Student
        
        self.known_face_encodings = []
        self.known_face_students = []
        
        print(f"🔍 در حال بارگذاری چهره‌ها از دیتابیس...")
        
        try:
            students = Student.objects.filter(is_active=True, face_encoding__isnull=False)
            print(f"📊 تعداد دانش‌آموزان با encoding: {students.count()}")
            
            loaded_count = 0
            error_count = 0
            
            for student in students:
                try:
                    if not student.face_encoding or not student.face_encoding.strip():
                        continue
                    
                    encoding_data = json.loads(student.face_encoding)
                    
                    if not encoding_data:
                        continue
                    
                    if isinstance(encoding_data, list):
                        if encoding_data and isinstance(encoding_data[0], list):
                            encoding_data = encoding_data[0]
                        
                        if len(encoding_data) == 128:
                            encoding = np.array(encoding_data, dtype=np.float64)
                            encoding = self.normalize_encoding(encoding)
                            
                            if encoding is not None and encoding.shape[0] == 128:
                                self.known_face_encodings.append(encoding)
                                self.known_face_students.append(student)
                                loaded_count += 1
                            else:
                                error_count += 1
                        else:
                            error_count += 1
                    else:
                        error_count += 1
                            
                except Exception as e:
                    error_count += 1
                    print(f"❌ خطا در پردازش دانش‌آموز {student.student_id}: {e}")
            
            print(f"📊 خلاصه بارگذاری:")
            print(f"   کل دانش‌آموزان: {students.count()}")
            print(f"   موفق: {loaded_count}")
            print(f"   خطا: {error_count}")
            
            if self.known_face_encodings:
                print(f"   تعداد encoding‌های بارگذاری شده: {len(self.known_face_encodings)}")
            
        except Exception as e:
            print(f"❌ خطا در بارگذاری چهره‌ها: {e}")
    
    def recognize_face(self, face_encoding):
        if not self.known_face_encodings:
            return None, 0.0
        
        try:
            face_encoding = self.normalize_encoding(face_encoding)
            if face_encoding is None:
                return None, 0.0
            
            face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
            
            best_match_index = np.argmin(face_distances)
            min_distance = face_distances[best_match_index]
            confidence = 1.0 - min_distance
            
            if confidence > 0.6:
                return self.known_face_students[best_match_index], confidence
            else:
                return None, confidence
                
        except Exception as e:
            self.log(f"خطا در تشخیص چهره: {e}", "warning")
            return None, 0.0
    
    def recognize_from_image(self, image_path, camera_id):
        if not self._initialized:
            self.initialize()
        
        results = []
        
        try:
            self.log("\n" + "="*60, "info")
            self.log("🔍 شروع عملیات تشخیص چهره", "info")
            self.log(f"📁 تصویر ورودی: {image_path}", "info")
            
            if not os.path.exists(image_path):
                self.log(f"❌ فایل پیدا نشد: {image_path}", "error")
                return results
            
            try:
                input_image = face_recognition.load_image_file(image_path)
            except Exception as e:
                self.log(f"❌ خطا در بارگذاری تصویر: {e}", "error")
                return results
            
            face_locations = face_recognition.face_locations(input_image)
            self.log(f"👥 تعداد چهره‌های پیدا شده: {len(face_locations)}", "info")
            
            if not face_locations:
                self.log("⚠️ هیچ چهره‌ای در تصویر یافت نشد", "warning")
                return results
            
            input_encodings = face_recognition.face_encodings(input_image, face_locations)
            self.log(f"🔢 تعداد encoding استخراج شده: {len(input_encodings)}", "info")
            
            for i, face_encoding in enumerate(input_encodings):
                self.log(f"\n🎭 پردازش چهره {i+1}/{len(input_encodings)}", "info")
                
                student, confidence = self.recognize_face(face_encoding)
                
                if student:
                    self.log(f"✅ شناسایی شد: {student.full_name()} (دقت: {confidence:.2%})", "success")
                    
                    print("\n" + "🌟"*30)
                    print(f"👤 دانش‌آموز شناسایی شد:")
                    print(f"   📛 نام: {student.full_name()}")
                    print(f"   🆔 کد دانش‌آموزی: {student.student_id}")
                    print(f"   🏫 کلاس: {student.classroom.name if student.classroom else 'بدون کلاس'}")
                    print(f"   📊 دقت تشخیص: {confidence:.2%}")
                    print(f"   🕐 زمان: {timezone.now().strftime('%H:%M:%S')}")
                    print("🌟"*30 + "\n")
                    
                    self.record_attendance(student, camera_id, confidence, image_path)
                    
                    self.log_recognition(student, 'recognition', confidence, {
                        'camera_id': camera_id,
                        'image_path': image_path,
                        'location': face_locations[i]
                    })
                    
                    results.append({
                        'name': student.full_name(),
                        'student': student,
                        'confidence': confidence,
                        'location': face_locations[i],
                        'student_id': student.student_id,
                        'class_name': student.classroom.name if student.classroom else None
                    })
                else:
                    self.log(f"👤 ناشناس (دقت: {confidence:.2%})", "info")
                    
                    self.log_recognition(None, 'unknown_detected', confidence, {
                        'camera_id': camera_id,
                        'image_path': image_path,
                        'location': face_locations[i]
                    })
                    
                    results.append({
                        'name': 'ناشناس',
                        'student': None,
                        'confidence': confidence,
                        'location': face_locations[i]
                    })
            
            self.log(f"\n✅ عملیات تشخیص کامل شد", "success")
            self.log(f"   📊 کل چهره‌ها: {len(results)}", "info")
            self.log(f"   ✅ شناسایی شده: {len([r for r in results if r['student']])}", "info")
            self.log(f"   ❓ ناشناس: {len([r for r in results if not r['student']])}", "info")
            
        except Exception as e:
            self.log(f"❌ خطا در تشخیص چهره: {e}", "error")
        
        return results
    
    def record_attendance(self, student, camera_id, confidence, image_path=None):
        try:
            from .models import Camera, Attendance
            
            today = timezone.now().date()
            now = timezone.now()
            
            two_hours_ago = now - timezone.timedelta(hours=2)
            existing = Attendance.objects.filter(
                student=student,
                date=today,
                time__gte=two_hours_ago.time()
            ).exists()
            
            if not existing:
                camera = Camera.objects.filter(id=camera_id).first()
                if not camera:
                    camera = Camera.objects.create(
                        name='تشخیص خودکار',
                        location='اتوماتیک',
                        camera_type='auto',
                        is_active=True
                    )
                
                captured_image_path = None
                
                if image_path and os.path.exists(image_path):
                    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
                    new_filename = f"{student.student_id}_{timestamp}.jpg"
                    
                    dest_dir = os.path.join(settings.MEDIA_ROOT, 'attendance/captured/')
                    os.makedirs(dest_dir, exist_ok=True)
                    destination_path = os.path.join(dest_dir, new_filename)
                    
                    try:
                        shutil.copy2(image_path, destination_path)
                        captured_image_path = f'attendance/captured/{new_filename}'
                    except Exception as e:
                        self.log(f"⚠️ خطا در کپی عکس: {e}", "warning")
                
                Attendance.objects.create(
                    student=student,
                    camera=camera,
                    confidence=confidence,
                    captured_image=captured_image_path,
                    notes='تشخیص خودکار لایو'
                )
                
                self.log(f"📝 حضور ثبت شد: {student.full_name()}", "success")
                return True
            else:
                self.log(f"⏭️ حضور قبلاً ثبت شده: {student.full_name()}", "info")
                return False
                
        except Exception as e:
            self.log(f"❌ خطا در ثبت حضور: {e}", "error")
            return False
    
    def log_recognition(self, student, action, confidence=None, details=None):
        try:
            from .models import FaceRecognitionLog
            
            camera_id = details.get('camera_id') if details else None
            
            FaceRecognitionLog.objects.create(
                student=student,
                camera_id=camera_id,
                action=action,
                confidence=confidence,
                details=json.dumps(details) if details else '{}'
            )
            
        except Exception as e:
            self.log(f"⚠️ خطا در ثبت لاگ: {e}", "warning")

face_system = FaceRecognitionSystem()