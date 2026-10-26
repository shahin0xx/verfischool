from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q, Sum, F, Value
from django.db.models.functions import TruncDate
from django.core.paginator import Paginator
from django.conf import settings
import os
import cv2
import numpy as np
import json
import tempfile
import time
import base64
from datetime import datetime, timedelta
import pandas as pd
from io import BytesIO

from .models import Student, ClassRoom, Camera, Attendance, DailyReport, FaceRecognitionLog, UnknownPerson, SystemConfig
from .forms import StudentRegistrationForm, CameraSetupForm, SearchStudentForm, ClassRoomForm, SystemConfigForm, FaceCaptureForm
from .camera import webcam
from .recognition import face_system
from .laboratory import face_lab

def is_admin(user):
    return user.is_authenticated and user.is_staff

def login_view(request):
    if request.user.is_authenticated:
        return redirect('verifi:dashboard')
    
    if request.method == 'POST':
        from django.contrib.auth import authenticate, login
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'خوش آمدید!')
            return redirect('verifi:dashboard')
        else:
            messages.error(request, 'نام کاربری یا رمز عبور نادرست است')
    
    return render(request, 'verifi/auth/login.html')

@login_required
def logout_view(request):
    from django.contrib.auth import logout
    logout(request)
    messages.success(request, 'با موفقیت خارج شدید')
    return redirect('verifi:login')

@login_required
@user_passes_test(is_admin)
def dashboard(request):
    try:
        today = timezone.now().date()
        now = timezone.now()
        
        stats = {
            'total_students': Student.objects.filter(is_active=True).count(),
            'total_classes': ClassRoom.objects.count(),
            'total_cameras': Camera.objects.filter(is_active=True).count(),
            'attendances_today': Attendance.objects.filter(date=today).count(),
            'unknown_persons_today': UnknownPerson.objects.filter(first_seen__date=today).count(),
            'system_uptime': get_system_uptime(),
        }
        
        absent_students = get_absent_students_today()
        stats['absent_today'] = len(absent_students)
        
        chart_data = get_attendance_chart_data()
        
        online_cameras = Camera.objects.filter(
            is_active=True,
            last_seen__gte=now - timedelta(minutes=5)
        ).count()
        stats['online_cameras'] = online_cameras
        
        recent_attendances = Attendance.objects.select_related(
            'student', 'camera'
        ).order_by('-date', '-time')[:10]
        
        recent_unknown = UnknownPerson.objects.select_related(
            'camera'
        ).order_by('-first_seen')[:5]
        
        class_stats = get_class_stats()
        
        recent_logs = FaceRecognitionLog.objects.select_related(
            'student', 'camera'
        ).order_by('-created_at')[:10]
        
        system_health = check_system_health()
        
        webcam_status = "online" if hasattr(webcam, 'video') and webcam.video and webcam.video.isOpened() else "offline"
        
        context = {
            'stats': stats,
            'chart_data': json.dumps(chart_data),
            'absent_students': absent_students[:10],
            'recent_attendances': recent_attendances,
            'recent_unknown': recent_unknown,
            'class_stats': class_stats,
            'recent_logs': recent_logs,
            'system_health': system_health,
            'today': today,
            'now': now,
            'webcam_status': webcam_status,
        }
        
        return render(request, 'verifi/dashboard.html', context)
        
    except Exception as e:
        print(f"خطا در داشبورد: {e}")
        messages.error(request, f'خطا در بارگذاری داشبورد: {e}')
        return render(request, 'verifi/dashboard.html', {})

def get_system_uptime():
    try:
        import psutil
        import time
        uptime_seconds = time.time() - psutil.boot_time()
        
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        
        return f"{days} روز, {hours} ساعت, {minutes} دقیقه"
    except:
        return "نامشخص"

def get_absent_students_today():
    try:
        today = timezone.now().date()
        
        all_students = Student.objects.filter(is_active=True)
        present_students = Attendance.objects.filter(
            date=today
        ).values_list('student_id', flat=True)
        
        absent_students = []
        for student in all_students.exclude(id__in=present_students):
            last_attendance = Attendance.objects.filter(
                student=student
            ).order_by('-date', '-time').first()
            
            absent_students.append({
                'id': student.id,
                'name': student.full_name(),
                'student_id': student.student_id,
                'classroom': student.classroom.name if student.classroom else 'بدون کلاس',
                'photo_url': student.photo.url if student.photo else '',
                'last_seen': last_attendance,
                'days_absent': (today - last_attendance.date).days if last_attendance else 999,
            })
        
        absent_students.sort(key=lambda x: x['days_absent'], reverse=True)
        return absent_students
    except Exception as e:
        print(f"خطا در دریافت غایبین: {e}")
        return []

def get_attendance_chart_data():
    try:
        today = timezone.now().date()
        
        dates = []
        attendance_counts = []
        unknown_counts = []
        
        for i in range(6, -1, -1):
            date = today - timedelta(days=i)
            dates.append(date.strftime('%m/%d'))
            
            attendance_count = Attendance.objects.filter(date=date).count()
            attendance_counts.append(attendance_count)
            
            unknown_count = UnknownPerson.objects.filter(first_seen__date=date).count()
            unknown_counts.append(unknown_count)
        
        return {
            'dates': dates,
            'attendance': attendance_counts,
            'unknown': unknown_counts,
        }
    except Exception as e:
        print(f"خطا در دریافت داده‌های نمودار: {e}")
        return {'dates': [], 'attendance': [], 'unknown': []}

def get_class_stats():
    try:
        today = timezone.now().date()
        classes = ClassRoom.objects.all()
        
        class_stats = []
        for classroom in classes:
            total = Student.objects.filter(classroom=classroom, is_active=True).count()
            if total == 0:
                continue
            
            present = Attendance.objects.filter(
                student__classroom=classroom,
                date=today
            ).values('student').distinct().count()
            
            percentage = (present / total * 100) if total > 0 else 0
            
            class_stats.append({
                'classroom': classroom,
                'total': total,
                'present': present,
                'absent': total - present,
                'percentage': round(percentage, 1),
                'color': 'success' if percentage >= 80 else 'warning' if percentage >= 50 else 'danger'
            })
        
        class_stats.sort(key=lambda x: x['percentage'], reverse=True)
        return class_stats
    except Exception as e:
        print(f"خطا در دریافت آمار کلاس‌ها: {e}")
        return []

def check_system_health():
    try:
        issues = []
        
        import shutil
        total, used, free = shutil.disk_usage("/")
        disk_usage = (used / total) * 100
        if disk_usage > 90:
            issues.append(f"فضای دیسک {disk_usage:.1f}% پر شده است")
        
        model_files = [
            "shape_predictor_68_face_landmarks.dat",
            "dlib_face_recognition_resnet_model_v1.dat"
        ]
        for model_file in model_files:
            if not os.path.exists(model_file):
                issues.append(f"فایل مدل {model_file} پیدا نشد")
        
        cameras = Camera.objects.filter(is_active=True)
        for camera in cameras:
            if camera.last_seen:
                time_diff = (timezone.now() - camera.last_seen).total_seconds()
                if time_diff > 300:
                    issues.append(f"دوربین {camera.name} برای {int(time_diff/60)} دقیقه غیرفعال است")
        
        if len(face_system.known_face_encodings) == 0:
            issues.append("هیچ چهره‌ای در سیستم بارگذاری نشده است")
        
        return {
            'issues': issues,
            'status': 'healthy' if len(issues) == 0 else 'warning' if len(issues) <= 2 else 'critical',
            'disk_usage': disk_usage,
            'face_count': len(face_system.known_face_encodings),
            'camera_count': cameras.count(),
            'online_cameras': cameras.filter(last_seen__gte=timezone.now()-timedelta(minutes=5)).count(),
        }
    except Exception as e:
        print(f"خطا در بررسی سلامت سیستم: {e}")
        return {'issues': [f'خطا در بررسی سلامت: {e}'], 'status': 'critical'}

@login_required
@user_passes_test(is_admin)
def search_student(request):
    if request.method == 'POST':
        form = SearchStudentForm(request.POST)
        if form.is_valid():
            search_type = form.cleaned_data['search_type']
            search_query = form.cleaned_data['search_query']
            camera_id = form.cleaned_data['camera_id'] if 'camera_id' in request.POST else None
            
            students = Student.objects.filter(is_active=True)
            
            if search_type == 'name':
                students = students.filter(
                    Q(first_name__icontains=search_query) | 
                    Q(last_name__icontains=search_query)
                )
            elif search_type == 'student_id':
                students = students.filter(student_id__icontains=search_query)
            elif search_type == 'national_id':
                students = students.filter(national_id__icontains=search_query)
            elif search_type == 'classroom':
                students = students.filter(classroom__name__icontains=search_query)
            
            search_results = []
            for student in students:
                today = timezone.now().date()
                present_today = Attendance.objects.filter(
                    student=student,
                    date=today
                ).exists()
                
                last_attendance = Attendance.objects.filter(
                    student=student
                ).order_by('-date', '-time').first()
                
                total_attendance = Attendance.objects.filter(
                    student=student
                ).count()
                
                search_results.append({
                    'student': student,
                    'present_today': present_today,
                    'last_attendance': last_attendance,
                    'total_attendance': total_attendance,
                })
            
            context = {
                'form': form,
                'search_results': search_results,
                'search_query': search_query,
                'search_type': search_type,
                'cameras': Camera.objects.filter(is_active=True),
                'selected_camera': camera_id,
            }
            
            return render(request, 'verifi/search_student.html', context)
    else:
        form = SearchStudentForm()
    
    context = {
        'form': form,
        'cameras': Camera.objects.filter(is_active=True),
    }
    
    return render(request, 'verifi/search_student.html', context)

@csrf_exempt
@login_required
def live_track_student(request, student_id):
    try:
        student = get_object_or_404(Student, id=student_id)
        
        if request.method == 'POST':
            data = json.loads(request.body)
            camera_id = data.get('camera_id')
            
            if camera_id:
                camera = get_object_or_404(Camera, id=camera_id)
                
                if camera.camera_type == 'webcam':
                    return JsonResponse({
                        'success': True,
                        'camera_type': 'webcam',
                        'camera_name': camera.name,
                        'stream_url': reverse('verifi:webcam_feed'),
                        'student': {
                            'id': student.id,
                            'name': student.full_name(),
                            'photo_url': student.photo.url if student.photo else '',
                        }
                    })
                else:
                    return JsonResponse({
                        'success': True,
                        'camera_type': 'ip',
                        'camera_name': camera.name,
                        'stream_url': camera.get_stream_url(),
                        'student': {
                            'id': student.id,
                            'name': student.full_name(),
                            'photo_url': student.photo.url if student.photo else '',
                        }
                    })
        
        return JsonResponse({
            'success': False,
            'error': 'دوربین انتخاب نشده'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def student_detail(request, student_id):
    try:
        student = get_object_or_404(Student, id=student_id)
        
        attendances = Attendance.objects.filter(student=student).order_by('-date', '-time')
        
        today = timezone.now().date()
        present_today = attendances.filter(date=today).exists()
        
        total_attendance = attendances.count()
        total_days = attendances.values('date').distinct().count()
        
        monthly_stats = []
        for i in range(6):
            month_start = today.replace(day=1) - timedelta(days=30*i)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            month_attendances = attendances.filter(date__range=[month_start, month_end])
            month_days = month_attendances.values('date').distinct().count()
            month_total_days = (month_end - month_start).days + 1
            
            monthly_stats.append({
                'month': month_start.strftime('%Y/%m'),
                'days': month_days,
                'total_days': month_total_days,
                'percentage': round((month_days / month_total_days * 100) if month_total_days > 0 else 0, 1)
            })
        
        face_encoding_status = "✅ ثبت شده" if student.face_encoding else "❌ نیاز به ثبت"
        
        context = {
            'student': student,
            'attendances': attendances[:50],
            'present_today': present_today,
            'total_attendance': total_attendance,
            'total_days': total_days,
            'monthly_stats': monthly_stats,
            'face_encoding_status': face_encoding_status,
            'cameras': Camera.objects.filter(is_active=True),
        }
        
        return render(request, 'verifi/student_detail.html', context)
        
    except Exception as e:
        messages.error(request, f'خطا در بارگذاری جزئیات: {e}')
        return redirect('verifi:search_student')

@login_required
@user_passes_test(is_admin)
def register_student(request):
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            student = form.save()
            messages.success(request, f'دانش‌آموز {student.full_name()} با موفقیت ثبت شد')
            return redirect('verifi:student_detail', student_id=student.id)
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = StudentRegistrationForm()
    
    context = {
        'form': form,
        'classrooms': ClassRoom.objects.all(),
    }
    
    return render(request, 'verifi/register_student.html', context)

@login_required
@user_passes_test(is_admin)
def capture_face(request, student_id):
    try:
        student = get_object_or_404(Student, id=student_id)
        
        if request.method == 'POST':
            form = FaceCaptureForm(request.POST, request.FILES)
            if form.is_valid():
                capture_method = form.cleaned_data['capture_method']
                
                if capture_method == 'webcam':
                    if hasattr(webcam, 'capture_photo'):
                        photo = webcam.capture_photo()
                        if photo is not None:
                            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
                            filename = f"student_{student.student_id}_{timestamp}.jpg"
                            filepath = os.path.join(settings.MEDIA_ROOT, 'students', 'photos', filename)
                            
                            cv2.imwrite(filepath, photo)
                            
                            student.photo = f'students/photos/{filename}'
                            student.save()
                            
                            extract_face_encoding(student)
                            
                            messages.success(request, 'عکس با موفقیت گرفته و پردازش شد')
                            return redirect('verifi:student_detail', student_id=student.id)
                        else:
                            messages.error(request, 'خطا در گرفتن عکس از وب‌کم')
                    else:
                        messages.error(request, 'وب‌کم در دسترس نیست')
                
                elif capture_method == 'upload':
                    image_file = form.cleaned_data['image_file']
                    if image_file:
                        student.photo = image_file
                        student.save()
                        
                        extract_face_encoding(student)
                        
                        messages.success(request, 'عکس با موفقیت آپلود و پردازش شد')
                        return redirect('verifi:student_detail', student_id=student.id)
        
        else:
            form = FaceCaptureForm()
        
        context = {
            'student': student,
            'form': form,
        }
        
        return render(request, 'verifi/capture_face.html', context)
        
    except Exception as e:
        messages.error(request, f'خطا در ثبت چهره: {e}')
        return redirect('verifi:student_detail', student_id=student_id)

def extract_face_encoding(student):
    try:
        if student.photo:
            photo_path = student.photo.path
            image = face_recognition.load_image_file(photo_path)
            encodings = face_recognition.face_encodings(image)
            
            if encodings:
                encoding = encodings[0]
                encoding_list = encoding.tolist()
                student.face_encoding = json.dumps(encoding_list)
                student.save(update_fields=['face_encoding'])
                
                face_system.load_known_faces()
                
                return True
    except Exception as e:
        print(f"خطا در استخراج ویژگی‌های چهره: {e}")
    
    return False

@login_required
def webcam_view(request):
    try:
        cameras = Camera.objects.filter(is_active=True)
        
        if not cameras.exists():
            camera = Camera.objects.create(
                name='وب‌کم لپتاپ',
                location='دفتر',
                camera_type='webcam',
                map_x=100,
                map_y=100,
                is_active=True
            )
            cameras = Camera.objects.filter(is_active=True)
        
        context = {
            'cameras': cameras,
            'today': timezone.now().date(),
        }
        
        return render(request, 'verifi/webcam.html', context)
    except Exception as e:
        messages.error(request, f'خطا در بارگذاری صفحه وب‌کم: {e}')
        return redirect('verifi:dashboard')

def webcam_feed(request):
    def generate():
        while True:
            frame = webcam.get_frame()
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
            time.sleep(0.01)
    
    return StreamingHttpResponse(generate(), 
                                 content_type='multipart/x-mixed-replace; boundary=frame')

@csrf_exempt
@login_required
def webcam_capture(request):
    if request.method == 'POST':
        try:
            photo = webcam.capture_photo()
            
            if photo is None:
                return JsonResponse({
                    'success': False,
                    'message': 'وب‌کم فعال نیست یا عکس گرفته نشد'
                })
            
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                temp_path = tmp_file.name
                cv2.imwrite(temp_path, photo)
            
            camera = Camera.objects.filter(is_active=True).first()
            if not camera:
                camera = Camera.objects.create(
                    name='وب‌کم لپتاپ',
                    location='دفتر',
                    camera_type='webcam',
                    map_x=100,
                    map_y=100,
                    is_active=True
                )
            
            results = face_system.recognize_from_image(temp_path, camera.id)
            
            recognized_students = []
            for result in results:
                if result['student']:
                    student = result['student']
                    
                    attendance_recorded = face_system.record_attendance(student, camera.id, result['confidence'], temp_path)
                    
                    recognized_students.append({
                        'id': student.id,
                        'name': student.full_name(),
                        'student_id': student.student_id,
                        'class': student.classroom.name if student.classroom else 'بدون کلاس',
                        'confidence': f"{result['confidence']:.1%}",
                        'confidence_raw': result['confidence'],
                        'location': result.get('location', []),
                        'time': timezone.now().strftime('%H:%M:%S'),
                        'attendance_recorded': attendance_recorded,
                        'photo_url': student.photo.url if student.photo else '',
                    })
            
            try:
                os.unlink(temp_path)
            except:
                pass
            
            return JsonResponse({
                'success': True,
                'recognized': recognized_students,
                'total_faces': len(results),
                'message': f"{len(recognized_students)} نفر شناسایی شدند"
            })
            
        except Exception as e:
            print(f"خطا در webcam_capture: {e}")
            return JsonResponse({
                'success': False,
                'message': f'خطای سیستمی: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'متد نامعتبر'})

@login_required
def live_detection_view(request):
    try:
        context = {
            'today': timezone.now().date(),
            'cameras': Camera.objects.filter(is_active=True),
        }
        
        return render(request, 'verifi/live_detection.html', context)
    except Exception as e:
        messages.error(request, f'خطا در صفحه تشخیص لایو: {e}')
        return redirect('verifi:dashboard')

def live_detection_feed(request):
    def generate():
        while True:
            frame = webcam.get_frame()
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
            time.sleep(0.01)
    
    return StreamingHttpResponse(generate(), 
                                 content_type='multipart/x-mixed-replace; boundary=frame')

@csrf_exempt
def get_live_detection_data(request):
    try:
        face_data = webcam.get_live_data()
        
        formatted_data = []
        for face in face_data:
            student = face.get('student')
            if student:
                formatted_data.append({
                    'id': student.id,
                    'name': student.full_name(),
                    'student_id': student.student_id,
                    'class': student.classroom.name if student.classroom else 'بدون کلاس',
                    'confidence': f"{face['confidence']:.1%}",
                    'confidence_raw': face['confidence'],
                    'timestamp': face['timestamp'].strftime('%H:%M:%S'),
                    'type': 'known',
                    'photo_url': student.photo.url if student.photo else '',
                })
            else:
                formatted_data.append({
                    'id': face.get('face_id', 0),
                    'name': 'ناشناس',
                    'student_id': 'N/A',
                    'class': 'ناشناس',
                    'confidence': f"{face.get('confidence', 0):.1%}",
                    'confidence_raw': face.get('confidence', 0),
                    'timestamp': face['timestamp'].strftime('%H:%M:%S'),
                    'presence_duration': face.get('presence_duration', 0),
                    'type': 'unknown',
                    'photo_url': '',
                })
        
        return JsonResponse({
            'success': True,
            'faces': formatted_data,
            'count': len(formatted_data),
            'timestamp': timezone.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@user_passes_test(is_admin)
def camera_management(request):
    try:
        cameras = Camera.objects.all().order_by('name')
        
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'add_camera':
                form = CameraSetupForm(request.POST)
                if form.is_valid():
                    camera = form.save()
                    messages.success(request, f'دوربین {camera.name} با موفقیت اضافه شد')
                else:
                    for error in form.errors.values():
                        messages.error(request, error)
            
            elif action == 'update_camera':
                camera_id = request.POST.get('camera_id')
                camera = get_object_or_404(Camera, id=camera_id)
                form = CameraSetupForm(request.POST, instance=camera)
                if form.is_valid():
                    camera = form.save()
                    messages.success(request, f'دوربین {camera.name} با موفقیت به‌روزرسانی شد')
                else:
                    for error in form.errors.values():
                        messages.error(request, error)
            
            elif action == 'delete_camera':
                camera_id = request.POST.get('camera_id')
                camera = get_object_or_404(Camera, id=camera_id)
                camera_name = camera.name
                camera.delete()
                messages.success(request, f'دوربین {camera_name} با موفقیت حذف شد')
            
            return redirect('verifi:camera_management')
        
        context = {
            'cameras': cameras,
            'camera_types': Camera.CAMERA_TYPE_CHOICES,
            'video_formats': ['mp4', 'avi', 'mov'],
        }
        
        return render(request, 'verifi/camera_management.html', context)
    except Exception as e:
        messages.error(request, f'خطا در مدیریت دوربین‌ها: {e}')
        return redirect('verifi:dashboard')

@login_required
def camera_map_view(request):
    try:
        cameras = Camera.objects.filter(is_active=True)
        camera_data = []
        
        for camera in cameras:
            status = 'online'
            if camera.last_seen:
                time_diff = (timezone.now() - camera.last_seen).seconds
                if time_diff > 300:
                    status = 'offline'
                elif time_diff > 60:
                    status = 'warning'
            
            today_attendances = Attendance.objects.filter(
                camera=camera,
                date=timezone.now().date()
            ).count()
            
            today_unknown = UnknownPerson.objects.filter(
                camera=camera,
                first_seen__date=timezone.now().date()
            ).count()
            
            camera_data.append({
                'id': camera.id,
                'name': camera.name,
                'location': camera.location,
                'type': camera.get_camera_type_display(),
                'map_x': camera.map_x,
                'map_y': camera.map_y,
                'status': status,
                'last_seen': camera.last_seen.strftime('%H:%M:%S') if camera.last_seen else 'نامشخص',
                'today_attendances': today_attendances,
                'today_unknown': today_unknown,
                'stream_url': camera.get_stream_url(),
            })
        
        context = {
            'cameras_json': json.dumps(camera_data, default=str),
            'total_cameras': len(camera_data),
        }
        
        return render(request, 'verifi/camera_map.html', context)
    except Exception as e:
        messages.error(request, f'خطا در صفحه نقشه: {e}')
        return redirect('verifi:dashboard')

@csrf_exempt
@login_required
def update_camera_position(request, camera_id):
    if request.method == 'POST':
        try:
            camera = get_object_or_404(Camera, id=camera_id)
            data = json.loads(request.body)
            
            camera.map_x = float(data.get('x', camera.map_x))
            camera.map_y = float(data.get('y', camera.map_y))
            camera.save()
            
            return JsonResponse({
                'success': True,
                'message': f'موقعیت دوربین {camera.name} به‌روزرسانی شد.',
                'camera': {
                    'id': camera.id,
                    'name': camera.name,
                    'map_x': camera.map_x,
                    'map_y': camera.map_y,
                }
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'خطا: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'متد نامعتبر'})

@login_required
@user_passes_test(is_admin)
def unknown_persons_view(request):
    try:
        unknown_persons = UnknownPerson.objects.select_related('camera') \
            .order_by('-first_seen')
        
        camera_id = request.GET.get('camera')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        processed = request.GET.get('processed')
        
        if camera_id:
            unknown_persons = unknown_persons.filter(camera_id=camera_id)
        if start_date:
            unknown_persons = unknown_persons.filter(first_seen__date__gte=start_date)
        if end_date:
            unknown_persons = unknown_persons.filter(first_seen__date__lte=end_date)
        if processed == 'yes':
            unknown_persons = unknown_persons.filter(is_processed=True)
        elif processed == 'no':
            unknown_persons = unknown_persons.filter(is_processed=False)
        
        paginator = Paginator(unknown_persons, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        total_unknown = unknown_persons.count()
        with_video = unknown_persons.exclude(video_path='').count()
        processed_count = unknown_persons.filter(is_processed=True).count()
        
        cameras = Camera.objects.filter(is_active=True)
        
        context = {
            'page_obj': page_obj,
            'cameras': cameras,
            'selected_camera': camera_id,
            'start_date': start_date,
            'end_date': end_date,
            'processed': processed,
            'total_unknown': total_unknown,
            'with_video': with_video,
            'processed_count': processed_count,
        }
        
        return render(request, 'verifi/unknown_persons.html', context)
    except Exception as e:
        messages.error(request, f'خطا در مدیریت افراد ناشناس: {e}')
        return redirect('verifi:dashboard')

@login_required
def unknown_person_detail(request, unknown_id):
    try:
        unknown_person = get_object_or_404(UnknownPerson, id=unknown_id)
        
        duration_minutes = unknown_person.duration_seconds // 60
        duration_seconds = unknown_person.duration_seconds % 60
        
        context = {
            'unknown_person': unknown_person,
            'duration_minutes': duration_minutes,
            'duration_seconds': duration_seconds,
        }
        
        return render(request, 'verifi/unknown_person_detail.html', context)
    except Exception as e:
        messages.error(request, f'خطا در جزئیات فرد ناشناس: {e}')
        return redirect('verifi:unknown_persons_view')

@csrf_exempt
@login_required
def mark_as_processed(request, unknown_id):
    try:
        unknown_person = get_object_or_404(UnknownPerson, id=unknown_id)
        unknown_person.is_processed = True
        unknown_person.save()
        
        messages.success(request, f'فرد ناشناس به عنوان پردازش شده علامت‌گذاری شد.')
        return redirect('verifi:unknown_persons_view')
    except Exception as e:
        messages.error(request, f'خطا: {str(e)}')
        return redirect('verifi:unknown_persons_view')

@csrf_exempt
@login_required
def delete_unknown_person(request, unknown_id):
    try:
        unknown_person = get_object_or_404(UnknownPerson, id=unknown_id)
        
        if unknown_person.video_path:
            video_path = os.path.join(settings.MEDIA_ROOT, str(unknown_person.video_path))
            if os.path.exists(video_path):
                os.remove(video_path)
        
        if unknown_person.thumbnail:
            thumbnail_path = os.path.join(settings.MEDIA_ROOT, str(unknown_person.thumbnail))
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
        
        unknown_person.delete()
        
        messages.success(request, 'فرد ناشناس و فایل‌های مرتبط حذف شدند.')
        return redirect('verifi:unknown_persons_view')
    except Exception as e:
        messages.error(request, f'خطا: {str(e)}')
        return redirect('verifi:unknown_persons_view')

@login_required
@user_passes_test(is_admin)
def attendance_report(request):
    try:
        classroom_id = request.GET.get('classroom')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        student_id = request.GET.get('student')
        camera_id = request.GET.get('camera')
        
        attendances = Attendance.objects.select_related('student', 'camera').all()
        
        if classroom_id:
            attendances = attendances.filter(student__classroom_id=classroom_id)
        if start_date:
            attendances = attendances.filter(date__gte=start_date)
        if end_date:
            attendances = attendances.filter(date__lte=end_date)
        if student_id:
            attendances = attendances.filter(student_id=student_id)
        if camera_id:
            attendances = attendances.filter(camera_id=camera_id)
        
        paginator = Paginator(attendances, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        total_attendances = attendances.count()
        unique_dates = attendances.values('date').distinct().count()
        unique_students = attendances.values('student').distinct().count()
        unique_cameras = attendances.values('camera').distinct().count()
        
        daily_stats = attendances.values('date') \
            .annotate(count=Count('id')) \
            .order_by('-date')[:30]
        
        context = {
            'page_obj': page_obj,
            'classrooms': ClassRoom.objects.all(),
            'students': Student.objects.filter(is_active=True),
            'cameras': Camera.objects.filter(is_active=True),
            'selected_classroom': classroom_id,
            'selected_student': student_id,
            'selected_camera': camera_id,
            'start_date': start_date,
            'end_date': end_date,
            'total_attendances': total_attendances,
            'unique_dates': unique_dates,
            'unique_students': unique_students,
            'unique_cameras': unique_cameras,
            'daily_stats': daily_stats,
        }
        
        return render(request, 'verifi/attendance_report.html', context)
    except Exception as e:
        messages.error(request, f'خطا در گزارش حضور: {e}')
        return redirect('verifi:dashboard')

@login_required
def classroom_report(request, classroom_id):
    try:
        classroom = get_object_or_404(ClassRoom, id=classroom_id)
        students = Student.objects.filter(classroom=classroom, is_active=True)
        
        today = timezone.now().date()
        
        present_today_ids = Attendance.objects.filter(
            student__classroom=classroom,
            date=today
        ).values_list('student_id', flat=True)
        
        student_data = []
        for student in students:
            attendance_count = Attendance.objects.filter(student=student).count()
            last_attendance = Attendance.objects.filter(student=student) \
                .order_by('-date', '-time').first()
            
            student_data.append({
                'student': student,
                'present_today': student.id in present_today_ids,
                'attendance_count': attendance_count,
                'last_seen': last_attendance,
            })
        
        week_stats = []
        for i in range(7):
            date = today - timedelta(days=i)
            day_present = Attendance.objects.filter(
                student__classroom=classroom,
                date=date
            ).count()
            
            week_stats.append({
                'date': date,
                'present': day_present,
                'total': students.count(),
                'percentage': round((day_present / students.count() * 100) if students.count() > 0 else 0, 1)
            })
        
        context = {
            'classroom': classroom,
            'student_data': student_data,
            'present_count': len(present_today_ids),
            'absent_count': students.count() - len(present_today_ids),
            'total_students': students.count(),
            'today': today,
            'week_stats': week_stats,
        }
        
        return render(request, 'verifi/classroom_report.html', context)
    except Exception as e:
        messages.error(request, f'خطا در گزارش کلاس: {e}')
        return redirect('verifi:dashboard')

@login_required
@user_passes_test(is_admin)
def recognition_logs(request):
    try:
        logs = FaceRecognitionLog.objects.select_related('student', 'camera') \
            .order_by('-created_at')
        
        action = request.GET.get('action')
        student_id = request.GET.get('student')
        camera_id = request.GET.get('camera')
        date = request.GET.get('date')
        
        if action:
            logs = logs.filter(action=action)
        if student_id:
            logs = logs.filter(student_id=student_id)
        if camera_id:
            logs = logs.filter(camera_id=camera_id)
        if date:
            logs = logs.filter(created_at__date=date)
        
        paginator = Paginator(logs, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        total_logs = logs.count()
        success_logs = logs.filter(action='recognition', confidence__gte=0.6).count()
        error_logs = logs.filter(action='error').count()
        unknown_logs = logs.filter(action='unknown_detected').count()
        
        context = {
            'page_obj': page_obj,
            'students': Student.objects.filter(is_active=True),
            'cameras': Camera.objects.filter(is_active=True),
            'selected_action': action,
            'selected_student': student_id,
            'selected_camera': camera_id,
            'selected_date': date,
            'total_logs': total_logs,
            'success_logs': success_logs,
            'error_logs': error_logs,
            'unknown_logs': unknown_logs,
        }
        
        return render(request, 'verifi/recognition_logs.html', context)
    except Exception as e:
        messages.error(request, f'خطا در لاگ‌ها: {e}')
        return redirect('verifi:dashboard')

@login_required
@user_passes_test(is_admin)
def system_settings(request):
    try:
        if request.method == 'POST':
            form = SystemConfigForm(request.POST)
            if form.is_valid():
                attendance_threshold = form.cleaned_data['attendance_threshold']
                recognition_interval = form.cleaned_data['recognition_interval']
                max_unknown_duration = form.cleaned_data['max_unknown_duration']
                auto_reload_faces = form.cleaned_data['auto_reload_faces']
                notification_enabled = form.cleaned_data['notification_enabled']
                backup_enabled = form.cleaned_data['backup_enabled']
                
                SystemConfig.set_config('attendance_threshold', str(attendance_threshold), 'آستانه دقت برای ثبت حضور')
                SystemConfig.set_config('recognition_interval', str(recognition_interval), 'فاصله تشخیص چهره (ثانیه)')
                SystemConfig.set_config('max_unknown_duration', str(max_unknown_duration), 'حداکثر زمان ضبط افراد ناشناس (ثانیه)')
                SystemConfig.set_config('auto_reload_faces', str(auto_reload_faces), 'بارگذاری مجدد خودکار چهره‌ها')
                SystemConfig.set_config('notification_enabled', str(notification_enabled), 'فعال بودن اعلان‌ها')
                SystemConfig.set_config('backup_enabled', str(backup_enabled), 'فعال بودن پشتیبان‌گیری')
                
                messages.success(request, 'تنظیمات سیستم با موفقیت ذخیره شد')
                return redirect('verifi:system_settings')
        else:
            current_settings = {
                'attendance_threshold': float(SystemConfig.get_config('attendance_threshold', '0.6')),
                'recognition_interval': float(SystemConfig.get_config('recognition_interval', '0.01')),
                'max_unknown_duration': int(SystemConfig.get_config('max_unknown_duration', '300')),
                'auto_reload_faces': SystemConfig.get_config('auto_reload_faces', 'True').lower() == 'true',
                'notification_enabled': SystemConfig.get_config('notification_enabled', 'True').lower() == 'true',
                'backup_enabled': SystemConfig.get_config('backup_enabled', 'True').lower() == 'true',
            }
            form = SystemConfigForm(initial=current_settings)
        
        context = {
            'form': form,
        }
        
        return render(request, 'verifi/system_settings.html', context)
    except Exception as e:
        messages.error(request, f'خطا در تنظیمات سیستم: {e}')
        return redirect('verifi:dashboard')

@login_required
@user_passes_test(is_admin)
def reload_faces(request):
    try:
        face_system.load_known_faces()
        messages.success(request, 'چهره‌ها با موفقیت بارگذاری مجدد شدند.')
    except Exception as e:
        messages.error(request, f'خطا در بارگذاری مجدد: {str(e)}')
    
    return redirect(request.META.get('HTTP_REFERER', 'verifi:dashboard'))

@login_required
@user_passes_test(is_admin)
def export_attendance(request):
    try:
        format_type = request.GET.get('format', 'excel')
        
        attendances = Attendance.objects.select_related('student', 'camera').all()
        
        data = []
        for att in attendances:
            data.append({
                'نام دانش‌آموز': att.student.full_name(),
                'کد دانش‌آموزی': att.student.student_id,
                'کلاس': att.student.classroom.name if att.student.classroom else '',
                'دوربین': att.camera.name,
                'تاریخ': att.date.strftime('%Y/%m/%d'),
                'زمان': att.time.strftime('%H:%M'),
                'دقت تشخیص': f"{att.confidence:.1%}",
                'توضیحات': att.notes,
            })
        
        if format_type == 'excel':
            df = pd.DataFrame(data)
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='حضور و غیاب', index=False)
            
            output.seek(0)
            
            response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename="attendance_report.xlsx"'
            return response
        
        elif format_type == 'csv':
            df = pd.DataFrame(data)
            
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="attendance_report.csv"'
            
            df.to_csv(response, index=False, encoding='utf-8-sig')
            return response
        
        elif format_type == 'json':
            response = JsonResponse(data, safe=False, json_dumps_params={'ensure_ascii': False, 'indent': 2})
            response['Content-Disposition'] = 'attachment; filename="attendance_report.json"'
            return response
        
    except Exception as e:
        messages.error(request, f'خطا در خروجی گزارش: {e}')
        return redirect('verifi:attendance_report')

@login_required
def api_attendance_today(request):
    try:
        today = timezone.now().date()
        
        attendances = Attendance.objects.filter(date=today) \
            .select_related('student', 'camera') \
            .order_by('-time')
        
        data = []
        for att in attendances:
            data.append({
                'student_name': att.student.full_name(),
                'student_id': att.student.student_id,
                'class': att.student.classroom.name if att.student.classroom else '',
                'camera': att.camera.name,
                'time': att.time.strftime('%H:%M'),
                'confidence': att.confidence,
            })
        
        return JsonResponse({
            'success': True,
            'date': today.strftime('%Y/%m/%d'),
            'count': len(data),
            'attendances': data,
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@csrf_exempt
def api_student_attendance(request, student_id):
    try:
        student = get_object_or_404(Student, id=student_id)
        
        attendances = Attendance.objects.filter(student=student) \
            .select_related('camera') \
            .order_by('-date', '-time')
        
        data = []
        for att in attendances:
            data.append({
                'date': att.date.strftime('%Y/%m/%d'),
                'time': att.time.strftime('%H:%M'),
                'camera': att.camera.name,
                'confidence': att.confidence,
            })
        
        return JsonResponse({
            'success': True,
            'student': {
                'id': student.id,
                'name': student.full_name(),
                'student_id': student.student_id,
                'class': student.classroom.name if student.classroom else '',
            },
            'total_attendance': len(data),
            'attendances': data,
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@csrf_exempt
def api_camera_status(request):
    try:
        cameras = Camera.objects.filter(is_active=True)
        
        data = []
        for camera in cameras:
            status = 'online'
            if camera.last_seen:
                time_diff = (timezone.now() - camera.last_seen).seconds
                if time_diff > 300:
                    status = 'offline'
                elif time_diff > 60:
                    status = 'warning'
            
            data.append({
                'id': camera.id,
                'name': camera.name,
                'location': camera.location,
                'type': camera.camera_type,
                'map_x': camera.map_x,
                'map_y': camera.map_y,
                'status': status,
                'last_seen': camera.last_seen.strftime('%H:%M:%S') if camera.last_seen else 'نامشخص',
                'stream_url': camera.get_stream_url(),
            })
        
        return JsonResponse({
            'success': True,
            'cameras': data,
            'count': len(data),
            'timestamp': timezone.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@csrf_exempt
def api_unknown_persons(request):
    try:
        today = timezone.now().date()
        
        unknown_persons = UnknownPerson.objects.filter(first_seen__date=today) \
            .select_related('camera') \
            .order_by('-first_seen')[:20]
        
        data = []
        for person in unknown_persons:
            data.append({
                'id': person.id,
                'camera_name': person.camera.name if person.camera else 'نامشخص',
                'first_seen': person.first_seen.strftime('%H:%M:%S'),
                'duration_seconds': person.duration_seconds,
                'has_video': bool(person.video_path),
                'has_thumbnail': bool(person.thumbnail),
                'is_processed': person.is_processed,
            })
        
        return JsonResponse({
            'success': True,
            'unknown_persons': data,
            'count': len(data),
            'date': today.strftime('%Y/%m/%d')
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

def index(request):
    return redirect('verifi:dashboard')