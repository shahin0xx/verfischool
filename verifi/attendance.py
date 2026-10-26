# attendance.py
from celery import shared_task
from django.utils import timezone
from django.db.models import Q
from datetime import datetime, timedelta
import os
import shutil
from .models import Attendance, Student, Camera, DailyReport, UnknownPerson, FaceRecognitionLog
import json
from django.conf import settings


@shared_task
def cleanup_old_files():
    """
    پاکسازی فایل‌های قدیمی
    """
    try:
        print("🧹 شروع پاکسازی فایل‌های قدیمی...")
        
        # پوشه‌های مورد نظر
        folders = [
            os.path.join(settings.MEDIA_ROOT, 'attendance/captured'),
            os.path.join(settings.MEDIA_ROOT, 'unknown_persons/videos'),
            os.path.join(settings.MEDIA_ROOT, 'unknown_persons/thumbnails'),
            os.path.join(settings.MEDIA_ROOT, 'debug'),
        ]
        
        deleted_files = 0
        deleted_size = 0
        
        for folder_path in folders:
            if os.path.exists(folder_path):
                # حذف فایل‌های قدیمی‌تر از 30 روز
                for filename in os.listdir(folder_path):
                    file_path = os.path.join(folder_path, filename)
                    
                    if os.path.isfile(file_path):
                        # تاریخ ایجاد فایل
                        file_time = os.path.getctime(file_path)
                        file_age = (timezone.now().timestamp() - file_time) / (24 * 3600)
                        
                        if file_age > 30:  # فایل‌های قدیمی‌تر از 30 روز
                            try:
                                file_size = os.path.getsize(file_path)
                                os.unlink(file_path)
                                deleted_files += 1
                                deleted_size += file_size
                                print(f"🗑️ فایل حذف شد: {file_path}")
                            except Exception as e:
                                print(f"⚠️ خطا در حذف فایل {file_path}: {e}")
        
        print(f"✅ پاکسازی کامل شد: {deleted_files} فایل ({deleted_size/1024/1024:.2f} MB) حذف شد")
        
    except Exception as e:
        print(f"❌ خطا در پاکسازی فایل‌ها: {e}")


@shared_task
def generate_daily_reports():
    """
    تولید گزارش روزانه برای کلاس‌ها
    """
    try:
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        print(f"📊 شروع تولید گزارش روزانه برای تاریخ {yesterday}...")
        
        from .models import ClassRoom
        
        classrooms = ClassRoom.objects.all()
        
        for classroom in classrooms:
            # تعداد کل دانش‌آموزان
            total_students = Student.objects.filter(
                classroom=classroom,
                is_active=True
            ).count()
            
            if total_students == 0:
                continue
            
            # تعداد حاضرین دیروز
            present_count = Attendance.objects.filter(
                student__classroom=classroom,
                date=yesterday
            ).values('student').distinct().count()
            
            # ایجاد یا به‌روزرسانی گزارش
            report, created = DailyReport.objects.update_or_create(
                classroom=classroom,
                date=yesterday,
                defaults={
                    'total_students': total_students,
                    'present_count': present_count,
                    'absent_count': total_students - present_count
                }
            )
            
            if created:
                print(f"✅ گزارش کلاس {classroom.name} ایجاد شد")
            else:
                print(f"📝 گزارش کلاس {classroom.name} به‌روزرسانی شد")
        
        print("✅ تولید گزارش‌های روزانه کامل شد")
        
    except Exception as e:
        print(f"❌ خطا در تولید گزارش‌های روزانه: {e}")


@shared_task
def process_unknown_persons():
    """
    پردازش افراد ناشناس قدیمی
    """
    try:
        print("👤 شروع پردازش افراد ناشناس قدیمی...")
        
        # افراد ناشناس قدیمی‌تر از 7 روز که پردازش نشده‌اند
        seven_days_ago = timezone.now() - timedelta(days=7)
        old_unknown = UnknownPerson.objects.filter(
            first_seen__lt=seven_days_ago,
            is_processed=False
        )
        
        processed_count = 0
        
        for person in old_unknown:
            try:
                # علامت‌گذاری به عنوان پردازش شده
                person.is_processed = True
                person.save(update_fields=['is_processed'])
                processed_count += 1
                
                # حذف فایل‌های ویدیویی اگر بیش از 30 روز است
                if person.video_path:
                    video_age = (timezone.now() - person.first_seen).days
                    if video_age > 30:
                        video_path = os.path.join(settings.MEDIA_ROOT, str(person.video_path))
                        if os.path.exists(video_path):
                            os.unlink(video_path)
                            person.video_path = None
                            person.save(update_fields=['video_path'])
                
            except Exception as e:
                print(f"⚠️ خطا در پردازش فرد ناشناس {person.id}: {e}")
        
        print(f"✅ {processed_count} فرد ناشناس پردازش شدند")
        
    except Exception as e:
        print(f"❌ خطا در پردازش افراد ناشناس: {e}")


@shared_task
def check_absent_students():
    """
    بررسی دانش‌آموزان غایب امروز
    """
    try:
        today = timezone.now().date()
        
        print(f"👥 بررسی دانش‌آموزان غایب برای تاریخ {today}...")
        
        from .models import ClassRoom
        
        absent_students = []
        
        classrooms = ClassRoom.objects.all()
        
        for classroom in classrooms:
            # دانش‌آموزان فعال این کلاس
            students = Student.objects.filter(
                classroom=classroom,
                is_active=True
            )
            
            # دانش‌آموزان حاضر امروز
            present_students = Attendance.objects.filter(
                student__in=students,
                date=today
            ).values_list('student_id', flat=True)
            
            # دانش‌آموزان غایب
            absent_in_class = students.exclude(id__in=present_students)
            
            for student in absent_in_class:
                absent_students.append({
                    'id': student.id,
                    'name': student.full_name(),
                    'student_id': student.student_id,
                    'classroom': classroom.name,
                    'last_seen': Attendance.objects.filter(
                        student=student
                    ).order_by('-date').first()
                })
        
        # ثبت لاگ برای مدیر
        if absent_students:
            FaceRecognitionLog.objects.create(
                action='error',
                details=json.dumps({
                    'type': 'absent_students',
                    'count': len(absent_students),
                    'students': absent_students,
                    'date': today.isoformat()
                })
            )
        
        print(f"✅ بررسی غایبین کامل شد: {len(absent_students)} دانش‌آموز غایب")
        return absent_students
        
    except Exception as e:
        print(f"❌ خطا در بررسی دانش‌آموزان غایب: {e}")
        return []


@shared_task
def backup_system():
    """
    پشتیبان‌گیری از سیستم
    """
    try:
        print("💾 شروع پشتیبان‌گیری از سیستم...")
        
        from django.core.management import call_command
        import subprocess
        import datetime
        
        # تاریخ برای نام فایل
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 1. پشتیبان از دیتابیس
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        db_backup_path = os.path.join(backup_dir, f'db_backup_{timestamp}.json')
        
        with open(db_backup_path, 'w') as f:
            call_command('dumpdata', format='json', indent=2, stdout=f)
        
        print(f"✅ پشتیبان دیتابیس ایجاد شد: {db_backup_path}")
        
        # 2. پشتیبان از مدل‌های تشخیص چهره
        models_dir = os.path.join(backup_dir, f'models_{timestamp}')
        os.makedirs(models_dir, exist_ok=True)
        
        model_files = [
            "shape_predictor_68_face_landmarks.dat",
            "dlib_face_recognition_resnet_model_v1.dat"
        ]
        
        for model_file in model_files:
            if os.path.exists(model_file):
                shutil.copy2(model_file, models_dir)
                print(f"✅ پشتیبان مدل {model_file} ایجاد شد")
        
        # 3. پشتیبان از عکس‌های دانش‌آموزان
        photos_backup_dir = os.path.join(backup_dir, f'photos_{timestamp}')
        photos_source_dir = os.path.join(settings.MEDIA_ROOT, 'students/photos')
        
        if os.path.exists(photos_source_dir):
            shutil.copytree(photos_source_dir, photos_backup_dir)
            print(f"✅ پشتیبان عکس‌ها ایجاد شد")
        
        # 4. حذف پشتیبان‌های قدیمی (بیشتر از 30 روز)
        for item in os.listdir(backup_dir):
            item_path = os.path.join(backup_dir, item)
            if os.path.isdir(item_path) or item.endswith('.json'):
                item_age = (timezone.now().timestamp() - os.path.getctime(item_path)) / (24 * 3600)
                if item_age > 30:
                    try:
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                        else:
                            os.unlink(item_path)
                        print(f"🗑️ پشتیبان قدیمی حذف شد: {item}")
                    except Exception as e:
                        print(f"⚠️ خطا در حذف پشتیبان قدیمی: {e}")
        
        print("✅ پشتیبان‌گیری کامل شد")
        
    except Exception as e:
        print(f"❌ خطا در پشتیبان‌گیری: {e}")


@shared_task
def send_daily_notifications():
    """
    ارسال اعلان‌های روزانه
    """
    try:
        print("📨 ارسال اعلان‌های روزانه...")
        
        today = timezone.now().date()
        
        # آمار امروز
        attendance_today = Attendance.objects.filter(date=today).count()
        unknown_today = UnknownPerson.objects.filter(first_seen__date=today).count()
        
        # دانش‌آموزان غایب
        absent_students = check_absent_students()
        
        # ایجاد لاگ اعلان
        FaceRecognitionLog.objects.create(
            action='recognition',
            details=json.dumps({
                'type': 'daily_report',
                'date': today.isoformat(),
                'attendance_count': attendance_today,
                'unknown_count': unknown_today,
                'absent_count': len(absent_students),
                'message': f'گزارش روزانه: {attendance_today} حضور، {unknown_today} ناشناس، {len(absent_students)} غایب'
            })
        )
        
        print(f"✅ اعلان روزانه ارسال شد: {attendance_today} حضور، {unknown_today} ناشناس")
        
    except Exception as e:
        print(f"❌ خطا در ارسال اعلان‌ها: {e}")


@shared_task
def monitor_system_health():
    """
    نظارت بر سلامت سیستم
    """
    try:
        print("🩺 بررسی سلامت سیستم...")
        
        issues = []
        
        # 1. بررسی دوربین‌ها
        cameras = Camera.objects.filter(is_active=True)
        for camera in cameras:
            if camera.last_seen:
                time_diff = (timezone.now() - camera.last_seen).total_seconds()
                if time_diff > 300:  # 5 دقیقه
                    issues.append(f"دوربین {camera.name} برای {int(time_diff/60)} دقیقه غیرفعال است")
        
        # 2. بررسی فضا
        import shutil
        total, used, free = shutil.disk_usage("/")
        disk_usage_percent = (used / total) * 100
        
        if disk_usage_percent > 90:
            issues.append(f"فضای دیسک {disk_usage_percent:.1f}% پر شده است")
        
        # 3. بررسی مدل‌ها
        model_files = [
            "shape_predictor_68_face_landmarks.dat",
            "dlib_face_recognition_resnet_model_v1.dat"
        ]
        
        for model_file in model_files:
            if not os.path.exists(model_file):
                issues.append(f"فایل مدل {model_file} پیدا نشد")
        
        if issues:
            # ثبت لاگ
            FaceRecognitionLog.objects.create(
                action='error',
                details=json.dumps({
                    'type': 'system_health',
                    'issues': issues,
                    'timestamp': timezone.now().isoformat()
                })
            )
            
            print(f"⚠️ مشکلات سیستم: {len(issues)} مورد")
            for issue in issues:
                print(f"   • {issue}")
        else:
            print("✅ سیستم سالم است")
        
        return issues
        
    except Exception as e:
        print(f"❌ خطا در بررسی سلامت سیستم: {e}")
        return [f"خطا در بررسی سلامت: {str(e)}"]


# وظایف زمان‌بندی شده
@shared_task
def scheduled_tasks():
    """
    اجرای تمام وظایف زمان‌بندی شده
    """
    try:
        print("⏰ شروع وظایف زمان‌بندی شده...")
        
        # 1. پاکسازی فایل‌های قدیمی (هر روز)
        cleanup_old_files.delay()
        
        # 2. تولید گزارش روزانه (هر روز ساعت ۲ بامداد)
        current_hour = timezone.now().hour
        if current_hour == 2:
            generate_daily_reports.delay()
        
        # 3. پردازش افراد ناشناس (هر روز)
        process_unknown_persons.delay()
        
        # 4. بررسی غایبین (هر ساعت)
        check_absent_students.delay()
        
        # 5. ارسال اعلان‌ها (هر روز ساعت ۱۷)
        if current_hour == 17:
            send_daily_notifications.delay()
        
        # 6. پشتیبان‌گیری (هر هفته)
        current_weekday = timezone.now().weekday()  # 0 = Monday
        current_hour = timezone.now().hour
        if current_weekday == 0 and current_hour == 3:  # دوشنبه ساعت ۳ بامداد
            backup_system.delay()
        
        # 7. بررسی سلامت سیستم (هر ساعت)
        monitor_system_health.delay()
        
        print("✅ وظایف زمان‌بندی شده ارسال شدند")
        
    except Exception as e:
        print(f"❌ خطا در اجرای وظایف زمان‌بندی شده: {e}")


# اجرای اولیه
try:
    # ایجاد تنظیمات اولیه
    from .models import SystemConfig
    
    # تنظیم وظایف دوره‌ای
    from celery.schedules import crontab
    from celery import Celery

    app = Celery('verifi')

    app.conf.beat_schedule = {
        'scheduled-tasks-every-hour': {
            'task': 'verifi.attendance.scheduled_tasks',
            'schedule': crontab(minute=0, hour='*'),  # هر ساعت
        },
    }
    
    print("✅ سیستم وظایف زمان‌بندی شده راه‌اندازی شد")
    
except Exception as e:
    print(f"⚠️ خطا در راه‌اندازی وظایف: {e}")