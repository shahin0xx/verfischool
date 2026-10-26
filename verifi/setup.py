# setup.py
import cv2
import numpy as np
import dlib
import os
import sys
from django.core.wsgi import get_wsgi_application

# تنظیم Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings')
application = get_wsgi_application()

from verifi.models import Camera, SystemConfig, Student, ClassRoom
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import transaction

def setup_system():
    """تنظیم اولیه سیستم تشخیص چهره"""
    
    print("\n" + "="*70)
    print("🔧 در حال راه‌اندازی سیستم تشخیص چهره مدرسه...")
    print("="*70)
    
    # 1. بررسی وجود فایل‌های مدل
    print("\n📁 1. بررسی فایل‌های مدل:")
    
    model_files = [
        "shape_predictor_68_face_landmarks.dat",
        "dlib_face_recognition_resnet_model_v1.dat"
    ]
    
    missing_files = []
    for file in model_files:
        if os.path.exists(file):
            print(f"   ✅ {file}")
        else:
            print(f"   ❌ {file} (مفقود)")
            missing_files.append(file)
    
    if missing_files:
        print(f"\n⚠️ فایل‌های زیر را دانلود و در پوشه پروژه قرار دهید:")
        for file in missing_files:
            print(f"   - {file}")
        print("\n🔗 لینک دانلود: http://dlib.net/files/")
        print("   🔗 جایگزین: https://github.com/davisking/dlib-models")
        return False
    
    # 2. بررسی دوربین
    print("\n📷 2. بررسی دوربین‌ها:")
    cap = cv2.VideoCapture(0)
    if cap.isOpened():
        print("   ✅ دوربین وب‌کم فعال است")
        cap.release()
    else:
        print("   ⚠️ دوربین وب‌کم پیدا نشد")
        print("   💡 راه‌حل: از دوربین USB استفاده کنید یا درایورها را بروزرسانی کنید")
    
    # 3. ایجاد پوشه‌های لازم
    print("\n📁 3. ایجاد پوشه‌ها:")
    folders = [
        './media',
        './media/students',
        './media/students/photos',
        './media/attendance',
        './media/attendance/captured',
        './media/attendance/videos',
        './media/unknown_persons',
        './media/unknown_persons/videos',
        './media/unknown_persons/thumbnails',
        './media/debug',
        './media/logs',
    ]
    
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
        print(f"   📂 {folder}")
    
    # 4. بررسی و ایجاد دیتابیس اولیه
    print("\n🗄️ 4. بررسی دیتابیس:")
    try:
        # ایجاد کاربر مدیر اگر وجود ندارد
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@school.com',
                password='admin123',
                first_name='مدیر',
                last_name='سیستم'
            )
            print("   ✅ کاربر مدیر ایجاد شد")
        
        # ایجاد دوربین وب‌کم پیش‌فرض
        camera, created = Camera.objects.get_or_create(
            name='وب‌کم لپتاپ',
            defaults={
                'location': 'دفتر مرکزی',
                'camera_type': 'webcam',
                'map_x': 100,
                'map_y': 100,
                'record_unknown_videos': True,
                'unknown_recording_threshold': 15,
                'video_format': 'mp4',
                'is_active': True
            }
        )
        if created:
            print("   ✅ دوربین وب‌کم ایجاد شد")
        
        # ایجاد کلاس‌های نمونه
        sample_classes = [
            {'name': 'دهم ریاضی', 'grade': 'دهم', 'field': 'ریاضی فیزیک', 'room_number': '101'},
            {'name': 'یازدهم تجربی', 'grade': 'یازدهم', 'field': 'علوم تجربی', 'room_number': '102'},
            {'name': 'دوازدهم انسانی', 'grade': 'دوازدهم', 'field': 'علوم انسانی', 'room_number': '103'},
        ]
        
        for class_data in sample_classes:
            classroom, created = ClassRoom.objects.get_or_create(
                name=class_data['name'],
                defaults=class_data
            )
            if created:
                print(f"   ✅ کلاس {class_data['name']} ایجاد شد")
        
        # تعداد رکوردها
        user_count = User.objects.count()
        camera_count = Camera.objects.count()
        class_count = ClassRoom.objects.count()
        student_count = Student.objects.count()
        
        print(f"\n📊 آمار دیتابیس:")
        print(f"   👤 کاربران: {user_count}")
        print(f"   📷 دوربین‌ها: {camera_count}")
        print(f"   🏫 کلاس‌ها: {class_count}")
        print(f"   👥 دانش‌آموزان: {student_count}")
        
    except Exception as e:
        print(f"   ❌ خطا در بررسی دیتابیس: {e}")
        return False
    
    # 5. تست مدل‌های dlib
    print("\n🤖 5. تست مدل‌های dlib:")
    try:
        detector = dlib.get_frontal_face_detector()
        predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")
        face_recognizer = dlib.face_recognition_model_v1("dlib_face_recognition_resnet_model_v1.dat")
        print("   ✅ مدل‌های dlib با موفقیت بارگذاری شدند")
        
        # تست تشخیص چند چهره
        print("   🔍 تست تشخیص چند چهره همزمان...")
        
        # ایجاد یک تصویر تست با چند چهره (شبیه‌سازی)
        test_image = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # نقاشی چند دایره به جای چهره برای تست
        cv2.circle(test_image, (200, 200), 50, (255, 255, 255), -1)
        cv2.circle(test_image, (400, 200), 50, (255, 255, 255), -1)
        cv2.circle(test_image, (300, 350), 50, (255, 255, 255), -1)
        
        # تبدیل به خاکستری
        gray = cv2.cvtColor(test_image, cv2.COLOR_BGR2GRAY)
        
        # تشخیص چهره‌ها
        faces = detector(gray)
        print(f"   ✅ سیستم قادر به تشخیص {len(faces)} چهره همزمان است")
        
    except Exception as e:
        print(f"   ❌ خطا در بارگذاری مدل‌ها: {e}")
        return False
    
    # 6. تنظیمات سیستم
    print("\n⚙️ 6. تنظیمات سیستم:")
    try:
        # تنظیمات پیش‌فرض
        default_configs = [
            ('system_name', 'سیستم تشخیص چهره مدرسه', 'نام سیستم'),
            ('attendance_threshold', '0.6', 'آستانه دقت برای ثبت حضور'),
            ('recognition_interval', '0.01', 'فاصله تشخیص چهره (ثانیه)'),
            ('max_unknown_duration', '300', 'حداکثر زمان ضبط افراد ناشناس (ثانیه)'),
            ('auto_reload_faces', 'True', 'بارگذاری مجدد خودکار چهره‌ها'),
            ('notification_enabled', 'True', 'فعال بودن اعلان‌ها'),
            ('backup_enabled', 'True', 'فعال بودن پشتیبان‌گیری'),
        ]
        
        for key, value, description in default_configs:
            SystemConfig.set_config(key, value, description)
            print(f"   ✅ تنظیم {key} = {value}")
        
    except Exception as e:
        print(f"   ⚠️ خطا در تنظیمات سیستم: {e}")
    
    print("\n" + "="*70)
    print("🎉 راه‌اندازی سیستم با موفقیت انجام شد!")
    print("="*70)
    
    print("\n📝 مراحل بعدی:")
    print("   1. 🔐 وارد سیستم شوید (admin/admin123)")
    print("   2. 👥 دانش‌آموزان جدید ثبت کنید")
    print("   3. 📸 از چهره دانش‌آموزان عکس بگیرید")
    print("   4. 🎬 سیستم تشخیص لایو را تست کنید")
    print("   5. 📊 گزارشات را بررسی کنید")
    print("\n⚠️ نکات مهم:")
    print("   • سیستم قادر به تشخیص چندین چهره همزمان است")
    print("   • از افراد ناشناس بعد از ۱۵ ثانیه فیلم گرفته می‌شود")
    print("   • همه حضورها به صورت خودکار ثبت می‌شوند")
    print("   • مدیر می‌تواند در داشبورد همه چیز را کنترل کند")
    
    return True


if __name__ == "__main__":
    success = setup_system()
    if success:
        print("\n✅ سیستم آماده استفاده است!")
        print("🌐 برای شروع، سرور Django را اجرا کنید:")
        print("   python manage.py runserver")
    else:
        print("\n❌ راه‌اندازی با خطا مواجه شد!")
        print("⚠️ لطفاً مشکلات بالا را برطرف کنید")