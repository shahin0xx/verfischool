# camera.py
import cv2
import threading
import numpy as np
import time
import face_recognition
import queue
import os
import shutil
import json
import uuid
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.core.files.base import ContentFile
from .models import Camera, Attendance, FaceRecognitionLog, UnknownPerson, Student


class VideoRecorder:
    """کلاس برای ضبط ویدیو از افراد ناشناس"""
    
    def __init__(self, camera_id, unknown_person_id):
        self.camera_id = camera_id
        self.unknown_person_id = unknown_person_id
        self.camera = Camera.objects.get(id=camera_id)
        self.unknown_person = UnknownPerson.objects.get(id=unknown_person_id)
        
        # تنظیمات ویدیو
        self.video_format = self.camera.video_format
        self.fps = 10
        self.frame_size = (640, 480)
        self.is_recording = False
        self.video_writer = None
        self.video_filename = None
        self.output_dir = os.path.join(settings.MEDIA_ROOT, 'unknown_persons', 'videos')
        os.makedirs(self.output_dir, exist_ok=True)
        
        # تایمر
        self.start_time = None
        self.duration_threshold = self.camera.unknown_recording_threshold  # 15 ثانیه
        self.max_duration = 300  # حداکثر 5 دقیقه
    
    def start_recording(self, first_frame):
        """شروع ضبط ویدیو"""
        if not self.camera.record_unknown_videos:
            return False
        
        # ایجاد نام فایل
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        self.video_filename = f"unknown_{timestamp}_{unique_id}.{self.video_format}"
        video_path = os.path.join(self.output_dir, self.video_filename)
        
        # تعیین کدک بر اساس فرمت
        if self.video_format.lower() == 'mp4':
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        elif self.video_format.lower() == 'avi':
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
        else:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        
        # ایجاد VideoWriter
        try:
            self.video_writer = cv2.VideoWriter(video_path, fourcc, self.fps, self.frame_size)
            if self.video_writer.isOpened():
                # نوشتن اولین فریم
                self.video_writer.write(first_frame)
                self.is_recording = True
                self.start_time = time.time()
                
                print(f"🎥 شروع ضبط ویدیو برای فرد ناشناس: {video_path}")
                return True
            else:
                print(f"❌ خطا در باز کردن فایل ویدیو: {video_path}")
                return False
        except Exception as e:
            print(f"❌ خطا در شروع ضبط ویدیو: {e}")
            return False
    
    def add_frame(self, frame):
        """افزودن فریم به ویدیو"""
        if self.is_recording and self.video_writer is not None:
            try:
                # تغییر اندازه فریم به اندازه استاندارد
                resized_frame = cv2.resize(frame, self.frame_size)
                self.video_writer.write(resized_frame)
                
                # بررسی زمان ضبط
                current_time = time.time()
                duration = current_time - self.start_time
                
                # اگر از آستانه بیشتر شد، ویدیو را ذخیره کن
                if duration >= self.duration_threshold:
                    self.stop_recording()
                    return True
                
                # اگر از حداکثر زمان بیشتر شد، قطع کن
                if duration >= self.max_duration:
                    self.stop_recording(max_time=True)
                    return True
                    
            except Exception as e:
                print(f"❌ خطا در افزودن فریم به ویدیو: {e}")
        
        return False
    
    def stop_recording(self, save=True, max_time=False):
        """توقف ضبط ویدیو"""
        if self.is_recording and self.video_writer is not None:
            try:
                self.video_writer.release()
                self.is_recording = False
                
                if save:
                    # محاسبه مدت زمان ضبط
                    duration = time.time() - self.start_time
                    
                    # ذخیره اطلاعات در دیتابیس
                    self.unknown_person.duration_seconds = int(duration)
                    
                    # ذخیره ویدیو
                    if self.video_filename:
                        video_path = os.path.join(self.output_dir, self.video_filename)
                        if os.path.exists(video_path) and duration >= self.duration_threshold:
                            # ذخیره مسیر ویدیو در مدل
                            relative_path = f'unknown_persons/videos/{self.video_filename}'
                            self.unknown_person.video_path.name = relative_path
                            
                            # ایجاد تصویر بندانگشتی
                            self.create_thumbnail(video_path)
                            
                            # ثبت لاگ
                            FaceRecognitionLog.objects.create(
                                camera=self.camera,
                                action='video_recorded',
                                details=json.dumps({
                                    'duration': duration,
                                    'file_path': video_path,
                                    'max_time_reached': max_time
                                })
                            )
                            
                            print(f"✅ ویدیو ذخیره شد: {video_path} (مدت: {duration:.1f} ثانیه)")
                        else:
                            # حذف ویدیو‌های کوتاه
                            if os.path.exists(video_path):
                                os.remove(video_path)
                                print(f"🗑️ ویدیو کوتاه حذف شد: {video_path}")
                    
                    self.unknown_person.save()
                
                return True
                
            except Exception as e:
                print(f"❌ خطا در توقف ضبط ویدیو: {e}")
        
        return False
    
    def create_thumbnail(self, video_path):
        """ایجاد تصویر بندانگشتی از ویدیو"""
        try:
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                # خواندن فریم وسط
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                middle_frame = total_frames // 2
                cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame)
                
                ret, frame = cap.read()
                if ret:
                    # ذخیره تصویر بندانگشتی
                    thumbnail_filename = f"thumbnail_{os.path.basename(video_path).split('.')[0]}.jpg"
                    thumbnail_path = os.path.join(settings.MEDIA_ROOT, 'unknown_persons', 'thumbnails', thumbnail_filename)
                    os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
                    
                    cv2.imwrite(thumbnail_path, frame)
                    
                    # ذخیره در مدل
                    relative_path = f'unknown_persons/thumbnails/{thumbnail_filename}'
                    self.unknown_person.thumbnail.name = relative_path
                    
                cap.release()
        except Exception as e:
            print(f"⚠️ خطا در ایجاد تصویر بندانگشتی: {e}")


class WebcamCamera:
    def __init__(self):
        self.video = None
        self.frame = None
        self.processed_frame = None
        self.lock = threading.Lock()
        self.live_lock = threading.Lock()
        self.running = True
        self.frame_count = 0
        self.test_mode = False
        self.face_system = None
        self.last_recognition_time = 0
        self.frame_queue = queue.Queue(maxsize=2)
        self.recognition_interval = 0.01  # هر 0.01 ثانیه
        self.face_data = []
        self.last_attendance_check = {}
        
        # مدیریت افراد ناشناس
        self.unknown_persons = {}  # {face_id: {'start_time': timestamp, 'recorder': VideoRecorder, 'person_id': id}}
        self.next_face_id = 1
        
        # دوربین وب‌کم
        self.camera_model = self.get_or_create_webcam()
        
        # بارگذاری سیستم تشخیص چهره
        try:
            from .recognition import face_system
            self.face_system = face_system
            print("✅ سیستم تشخیص چهره بارگذاری شد")
        except Exception as e:
            print(f"⚠️ خطا در بارگذاری سیستم تشخیص: {e}")
        
        # امتحان چند منبع مختلف برای وب‌کم
        sources = [0, 1, 2]
        for source in sources:
            try:
                self.video = cv2.VideoCapture(source)
                if self.video.isOpened():
                    print(f"✅ وب‌کم پیدا شد (منبع: {source})")
                    break
                else:
                    self.video.release()
            except:
                pass
        
        if self.video is None or not self.video.isOpened():
            print("⚠️ هشدار: وب‌کم لپتاپ پیدا نشد. در حال استفاده از حالت تست...")
            self.test_mode = True
        else:
            # تنظیمات وب‌کم
            self.video.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.video.set(cv2.CAP_PROP_FPS, 30)
            print("✅ وب‌کم فعال شد (640x480 @ 30fps)")
        
        # شروع دریافت فریم‌ها
        if not self.test_mode:
            self.capture_thread = threading.Thread(target=self.capture_frames, daemon=True)
            self.capture_thread.start()
            
            self.process_thread = threading.Thread(target=self.process_frames, daemon=True)
            self.process_thread.start()
        
        print("🎬 سیستم تشخیص لایو چهره فعال شد (هر 0.01 ثانیه)")
    
    def get_or_create_webcam(self):
        """ایجاد یا دریافت مدل دوربین وب‌کم"""
        try:
            camera, created = Camera.objects.get_or_create(
                name='وب‌کم لپتاپ',
                defaults={
                    'location': 'دفتر مرکزی',
                    'camera_type': 'webcam',
                    'map_x': 100,
                    'map_y': 100,
                    'is_active': True
                }
            )
            
            if created:
                print(f"🎥 دوربین وب‌کم ایجاد شد: {camera.name}")
            else:
                print(f"🎥 دوربین وب‌کم موجود استفاده شد: {camera.name}")
            
            return camera
        except Exception as e:
            print(f"⚠️ خطا در ایجاد دوربین: {e}")
            return None
    
    def capture_frames(self):
        """دریافت مداوم فریم‌ها از وب‌کم"""
        while self.running:
            try:
                grabbed, frame = self.video.read()
                if grabbed:
                    # کاهش حجم فریم برای پردازش سریع‌تر
                    small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
                    
                    with self.lock:
                        self.frame = frame.copy()
                        self.frame_count += 1
                    
                    # اضافه کردن به صف برای پردازش
                    try:
                        if not self.frame_queue.full():
                            self.frame_queue.put(small_frame, block=False)
                    except:
                        pass
                else:
                    print("⚠️ مشکل در دریافت فریم از وب‌کم")
                
                time.sleep(0.001)
                
            except Exception as e:
                print(f"خطا در دریافت فریم از وب‌کم: {e}")
                time.sleep(0.1)
    
    def assign_face_id(self, face_location):
        """تعیین شناسه منحصر به فرد برای هر چهره"""
        # محاسبه مرکز چهره
        top, right, bottom, left = face_location
        center_x = (left + right) // 2
        center_y = (top + bottom) // 2
        
        # بررسی چهره‌های موجود
        for face_id, data in list(self.unknown_persons.items()):
            last_location = data.get('last_location', (0, 0))
            last_center_x, last_center_y = last_location
            
            # فاصله اقلیدسی
            distance = ((center_x - last_center_x) ** 2 + (center_y - last_center_y) ** 2) ** 0.5
            
            # اگر فاصله کم بود، همان چهره است
            if distance < 50:  # آستانه 50 پیکسل
                data['last_location'] = (center_x, center_y)
                data['last_seen'] = time.time()
                return face_id
        
        # چهره جدید
        face_id = self.next_face_id
        self.unknown_persons[face_id] = {
            'start_time': time.time(),
            'last_seen': time.time(),
            'last_location': (center_x, center_y),
            'recorder': None,
            'person_id': None
        }
        self.next_face_id += 1
        
        return face_id
    
    def process_frames(self):
        """پردازش فریم‌ها برای تشخیص چهره"""
        while self.running:
            try:
                current_time = time.time()
                
                # اگر سیستم تشخیص چهره بارگذاری نشده، صبر کن
                if self.face_system is None:
                    time.sleep(0.1)
                    continue
                
                # بررسی صف برای فریم جدید
                if not self.frame_queue.empty():
                    frame = self.frame_queue.get()
                    
                    # هر 0.01 ثانیه پردازش کن
                    if current_time - self.last_recognition_time >= self.recognition_interval:
                        self.last_recognition_time = current_time
                        
                        # تبدیل BGR به RGB
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        
                        # تشخیص چهره‌ها
                        face_locations = face_recognition.face_locations(rgb_frame)
                        
                        new_face_data = []
                        
                        if face_locations:
                            # استخراج encoding‌ها
                            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
                            
                            # پردازش هر چهره
                            for i, (face_encoding, face_location) in enumerate(zip(face_encodings, face_locations)):
                                # تشخیص چهره
                                student, confidence = self.face_system.recognize_face(face_encoding)
                                
                                if student and confidence > 0.6:
                                    # ثبت حضور (هر 5 دقیقه یکبار)
                                    self.record_live_attendance(student, confidence)
                                    
                                    new_face_data.append({
                                        'student': student,
                                        'confidence': confidence,
                                        'location': face_location,
                                        'timestamp': timezone.now(),
                                        'is_known': True
                                    })
                                    
                                    # اگر این چهره قبلاً به عنوان ناشناس ثبت شده بود، ضبط را متوقف کن
                                    face_id = self.assign_face_id(face_location)
                                    if face_id in self.unknown_persons:
                                        self.stop_unknown_recording(face_id, identified=True)
                                        del self.unknown_persons[face_id]
                                    
                                else:
                                    # فرد ناشناس
                                    face_id = self.assign_face_id(face_location)
                                    
                                    # بررسی زمان حضور فرد ناشناس
                                    face_data = self.unknown_persons[face_id]
                                    presence_duration = current_time - face_data['start_time']
                                    
                                    # اگر اولین بار است که دیده می‌شود، یک رکورد جدید ایجاد کن
                                    if face_data['person_id'] is None:
                                        person = UnknownPerson.objects.create(
                                            camera=self.camera_model
                                        )
                                        face_data['person_id'] = person.id
                                        print(f"👤 فرد ناشناس جدید شناسایی شد (ID: {person.id})")
                                    
                                    # اگر از آستانه ضبط گذشت و هنوز در حال ضبط نیست، شروع کن
                                    if (presence_duration >= 1 and 
                                        face_data['recorder'] is None and 
                                        self.camera_model.record_unknown_videos):
                                        
                                        # گرفتن فریم اصلی برای شروع ضبط
                                        with self.lock:
                                            if self.frame is not None:
                                                recorder = VideoRecorder(self.camera_model.id, face_data['person_id'])
                                                if recorder.start_recording(self.frame.copy()):
                                                    face_data['recorder'] = recorder
                                    
                                    # اگر در حال ضبط است، فریم را اضافه کن
                                    elif face_data['recorder'] is not None:
                                        with self.lock:
                                            if self.frame is not None:
                                                face_data['recorder'].add_frame(self.frame.copy())
                                    
                                    new_face_data.append({
                                        'student': None,
                                        'confidence': confidence if confidence else 0,
                                        'location': face_location,
                                        'timestamp': timezone.now(),
                                        'is_known': False,
                                        'face_id': face_id,
                                        'presence_duration': presence_duration
                                    })
                        
                        # حذف چهره‌هایی که دیگر دیده نمی‌شوند
                        self.cleanup_unknown_faces()
                        
                        # ذخیره داده‌های تشخیص
                        with self.live_lock:
                            self.face_data = new_face_data
                
                time.sleep(0.001)
                
            except Exception as e:
                print(f"خطا در پردازش فریم: {e}")
                time.sleep(0.1)
    
    def cleanup_unknown_faces(self):
        """پاکسازی چهره‌های ناشناس که دیگر دیده نمی‌شوند"""
        current_time = time.time()
        to_remove = []
        
        for face_id, face_data in self.unknown_persons.items():
            if current_time - face_data['last_seen'] > 2:  # 2 ثانیه غیبت
                # توقف ضبط ویدیو
                self.stop_unknown_recording(face_id, identified=False)
                to_remove.append(face_id)
        
        # حذف از دیکشنری
        for face_id in to_remove:
            del self.unknown_persons[face_id]
    
    def stop_unknown_recording(self, face_id, identified=False):
        """توقف ضبط ویدیو برای فرد ناشناس"""
        if face_id in self.unknown_persons:
            face_data = self.unknown_persons[face_id]
            
            if face_data['recorder'] is not None:
                # اگر فرد شناسایی شد یا زمان کوتاه بود، ویدیو را ذخیره نکن
                save_video = not identified and face_data['recorder'].is_recording
                face_data['recorder'].stop_recording(save=save_video)
                face_data['recorder'] = None
                
                if identified:
                    print(f"🔄 ضبط ویدیو متوقف شد (فرد شناسایی شد)")
                else:
                    print(f"🔄 ضبط ویدیو متوقف شد (فرد از دید دوربین خارج شد)")
    
    def record_live_attendance(self, student, confidence):
        """ثبت حضور خودکار برای تشخیص لایو"""
        try:
            today = timezone.now().date()
            student_id = student.id
            
            # بررسی زمان آخرین ثبت برای این دانش‌آموز
            last_check = self.last_attendance_check.get(student_id)
            current_time = time.time()
            
            # هر 5 دقیقه یکبار مجاز به ثبت است
            if last_check and (current_time - last_check) < 300:  # 300 ثانیه = 5 دقیقه
                return
            
            # بررسی حضور امروز
            existing = Attendance.objects.filter(
                student=student,
                date=today
            ).exists()
            
            if not existing:
                # ثبت حضور
                attendance = Attendance.objects.create(
                    student=student,
                    camera=self.camera_model,
                    confidence=confidence,
                    notes='تشخیص خودکار لایو'
                )
                
                # ثبت لاگ
                FaceRecognitionLog.objects.create(
                    student=student,
                    camera=self.camera_model,
                    action='recognition',
                    confidence=confidence,
                    details=json.dumps({'source': 'live_detection', 'auto': True})
                )
                
                print(f"✅ حضور لایو ثبت شد: {student.full_name()} (دقت: {confidence:.1%})")
                
                # به‌روزرسانی زمان آخرین ثبت
                self.last_attendance_check[student_id] = current_time
                
        except Exception as e:
            print(f"❌ خطا در ثبت حضور لایو: {e}")
    
    def get_live_frame(self):
        """دریافت فریم با تشخیص لایو"""
        with self.lock:
            if self.frame is None:
                # فریم خالی
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                return frame
            else:
                frame = self.frame.copy()
        
        # افزودن تشخیص‌های چهره به فریم
        with self.live_lock:
            face_data = self.face_data.copy()
        
        # رسم مستطیل و اطلاعات برای هر چهره تشخیص داده شده
        for face in face_data:
            top, right, bottom, left = face['location']
            top *= 2; right *= 2; bottom *= 2; left *= 2
            
            if face['is_known'] and face['student']:
                # چهره شناخته شده - مستطیل سبز
                color = (0, 255, 0)
                student = face['student']
                name = student.full_name()
                confidence_text = f"{face['confidence']:.0%}"
                
                # رسم مستطیل دور چهره
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                
                # پس‌زمینه برای متن
                cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
                
                # متن نام
                cv2.putText(frame, name, (left + 6, bottom - 6), 
                           cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 0, 0), 1)
                
                # متن دقت
                cv2.putText(frame, confidence_text, (left + 6, top - 6), 
                           cv2.FONT_HERSHEY_DUPLEX, 0.5, color, 1)
            else:
                # چهره ناشناس - مستطیل قرمز
                color = (0, 0, 255)
                confidence_text = f"{face.get('confidence', 0):.0%}" if face.get('confidence') else "N/A"
                
                # محاسبه مدت زمان حضور
                duration = face.get('presence_duration', 0)
                duration_text = f"{duration:.1f}s"
                
                # اگر بیشتر از 15 ثانیه است، رنگ را به نارنجی تغییر بده
                if duration >= 15:
                    color = (0, 165, 255)  # نارنجی
                
                # رسم مستطیل دور چهره
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                
                # پس‌زمینه برای متن
                cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
                
                # متن "ناشناس"
                cv2.putText(frame, "ناشناس", (left + 6, bottom - 20), 
                           cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1)
                
                # متن مدت زمان
                cv2.putText(frame, duration_text, (left + 6, bottom - 6), 
                           cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1)
                
                # متن دقت
                cv2.putText(frame, confidence_text, (left + 6, top - 6), 
                           cv2.FONT_HERSHEY_DUPLEX, 0.5, color, 1)
        
        # اطلاعات سیستم
        height, width = frame.shape[:2]
        
        # تعداد افراد شناسایی شده و ناشناس
        known_count = len([f for f in face_data if f['is_known']])
        unknown_count = len([f for f in face_data if not f['is_known']])
        
        # نمایش آمار
        stats_text = f"شناسایی: {known_count} | ناشناس: {unknown_count}"
        cv2.putText(frame, stats_text, (10, height - 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # نمایش وضعیت
        status_text = "تشخیص لایو فعال"
        cv2.putText(frame, status_text, (10, height - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        return frame
    
    def get_frame(self):
        """دریافت فریم فعلی (برای استریم معمولی)"""
        frame = self.get_live_frame()
        
        # تبدیل به JPEG
        ret, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        
        return jpeg.tobytes() if ret else b''
    
    def capture_photo(self):
        """گرفتن عکس از وب‌کم"""
        with self.lock:
            if self.frame is not None:
                return self.frame.copy()
        return None
    
    def get_live_data(self):
        """دریافت داده‌های تشخیص لایو"""
        with self.live_lock:
            return self.face_data.copy()
    
    def get_camera_info(self):
        """دریافت اطلاعات دوربین"""
        return {
            'id': self.camera_model.id if self.camera_model else None,
            'name': self.camera_model.name if self.camera_model else 'وب‌کم',
            'location': self.camera_model.location if self.camera_model else 'نا‌مشخص',
            'map_x': self.camera_model.map_x if self.camera_model else 0,
            'map_y': self.camera_model.map_y if self.camera_model else 0,
            'is_active': self.camera_model.is_active if self.camera_model else True
        }
    
    def release(self):
        """آزاد کردن وب‌کم"""
        self.running = False
        
        # توقف همه ضبط‌های ویدیویی
        for face_id, face_data in list(self.unknown_persons.items()):
            self.stop_unknown_recording(face_id, identified=False)
        
        if not self.test_mode and self.video is not None:
            self.video.release()
            print("✅ وب‌کم آزاد شد")
    
    def __del__(self):
        self.release()

# ایجاد نمونه جهانی وب‌کم
webcam = WebcamCamera()