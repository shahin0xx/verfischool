from django.db import models
from django.utils import timezone
import json
from django.core.exceptions import ValidationError
import os
from django.contrib.auth.models import User


class ClassRoom(models.Model):
    name = models.CharField(max_length=100)
    grade = models.CharField(max_length=50)
    field = models.CharField(max_length=100)
    room_number = models.CharField(max_length=10)
    
    def __str__(self):
        return f"{self.name} - {self.grade} {self.field}"
    
    class Meta:
        verbose_name = "کلاس"
        verbose_name_plural = "کلاس‌ها"

    def student_count(self):
        return self.student_set.filter(is_active=True).count()


class Student(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    student_id = models.CharField(max_length=20, unique=True)
    national_id = models.CharField(max_length=10, blank=True)
    
    classroom = models.ForeignKey(ClassRoom, on_delete=models.SET_NULL, 
                                  null=True, blank=True)
    
    photo = models.ImageField(upload_to='students/photos/', blank=True, null=True)
    face_encoding = models.TextField(blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.student_id})"
    
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def clean(self):
        if self.national_id and len(self.national_id) != 10:
            raise ValidationError({'national_id': 'کد ملی باید ۱۰ رقمی باشد'})
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        try:
            from .recognition import face_system
            if hasattr(face_system, 'load_known_faces'):
                face_system.load_known_faces()
        except Exception as e:
            print(f"خطا در بارگذاری مجدد چهره‌ها: {e}")
    
    class Meta:
        verbose_name = "دانش‌آموز"
        verbose_name_plural = "دانش‌آموزان"
        ordering = ['last_name', 'first_name']


class Camera(models.Model):
    CAMERA_TYPE_CHOICES = [
        ('webcam', 'وب‌کم'),
        ('ip', 'دوربین IP'),
        ('usb', 'دوربین USB'),
    ]
    
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=200)
    camera_type = models.CharField(max_length=10, choices=CAMERA_TYPE_CHOICES, default='webcam')
    ip_address = models.CharField(max_length=50, blank=True)
    port = models.IntegerField(default=80, blank=True, null=True)
    username = models.CharField(max_length=100, blank=True)
    password = models.CharField(max_length=100, blank=True)
    
    map_x = models.FloatField(default=0)
    map_y = models.FloatField(default=0)
    
    record_unknown_videos = models.BooleanField(default=True)
    unknown_recording_threshold = models.IntegerField(default=15)
    video_format = models.CharField(max_length=10, default='mp4')
    
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.name} ({self.location})"
    
    def get_stream_url(self):
        if self.camera_type == 'webcam':
            return 0
        elif self.camera_type == 'ip' and self.ip_address:
            if self.username and self.password:
                return f"rtsp://{self.username}:{self.password}@{self.ip_address}:{self.port}/stream"
            else:
                return f"rtsp://{self.ip_address}:{self.port}/stream"
        else:
            return None
    
    class Meta:
        verbose_name = "دوربین"
        verbose_name_plural = "دوربین‌ها"


class Attendance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    time = models.TimeField(default=timezone.now)
    confidence = models.FloatField(default=0.0)
    captured_image = models.ImageField(upload_to='attendance/captured/', 
                                       blank=True, null=True)
    video_path = models.FileField(upload_to='attendance/videos/', 
                                  blank=True, null=True)
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.student.full_name()} - {self.date} {self.time}"
    
    class Meta:
        verbose_name = "حضور و غیاب"
        verbose_name_plural = "حضور و غیاب‌ها"
        ordering = ['-date', '-time']
        unique_together = ['student', 'date']


class DailyReport(models.Model):
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    
    total_students = models.IntegerField(default=0)
    present_count = models.IntegerField(default=0)
    absent_count = models.IntegerField(default=0)
    
    def __str__(self):
        return f"گزارش {self.classroom.name} - {self.date}"
    
    def attendance_percentage(self):
        if self.total_students > 0:
            return round((self.present_count / self.total_students) * 100, 2)
        return 0
    
    class Meta:
        verbose_name = "گزارش روزانه"
        verbose_name_plural = "گزارش‌های روزانه"
        unique_together = ['classroom', 'date']


class FaceRecognitionLog(models.Model):
    ACTION_CHOICES = [
        ('registration', 'ثبت چهره'),
        ('recognition', 'تشخیص چهره'),
        ('verification', 'تأیید چهره'),
        ('error', 'خطا'),
        ('unknown_detected', 'فرد ناشناس شناسایی شد'),
        ('video_recorded', 'ویدیو ضبط شد'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, 
                                null=True, blank=True)
    camera = models.ForeignKey(Camera, on_delete=models.SET_NULL,
                               null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    confidence = models.FloatField(null=True, blank=True)
    image_path = models.CharField(max_length=500, blank=True)
    video_path = models.CharField(max_length=500, blank=True)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        student_name = self.student.full_name() if self.student else "ناشناس"
        return f"{self.get_action_display()} - {student_name} - {self.created_at}"
    
    class Meta:
        verbose_name = "لاگ تشخیص چهره"
        verbose_name_plural = "لاگ‌های تشخیص چهره"
        ordering = ['-created_at']


class SystemConfig(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.key} = {self.value[:50]}..."
    
    class Meta:
        verbose_name = "تنظیمات سیستم"
        verbose_name_plural = "تنظیمات سیستم"
    
    @classmethod
    def get_config(cls, key, default=None):
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set_config(cls, key, value, description=""):
        obj, created = cls.objects.update_or_create(
            key=key,
            defaults={'value': value, 'description': description}
        )
        return obj


class UnknownPerson(models.Model):
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    duration_seconds = models.IntegerField(default=0)
    video_path = models.FileField(upload_to='unknown_persons/videos/', 
                                  blank=True, null=True)
    thumbnail = models.ImageField(upload_to='unknown_persons/thumbnails/', 
                                  blank=True, null=True)
    is_processed = models.BooleanField(default=False)
    
    def __str__(self):
        return f"ناشناس - {self.first_seen.strftime('%Y/%m/%d %H:%M:%S')}"
    
    class Meta:
        verbose_name = "فرد ناشناس"
        verbose_name_plural = "افراد ناشناس"
        ordering = ['-first_seen']


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=20, blank=True)
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    department = models.CharField(max_length=100, blank=True)
    is_teacher = models.BooleanField(default=False)
    teacher_code = models.CharField(max_length=20, blank=True)
    
    def __str__(self):
        return self.user.get_full_name()
    
    class Meta:
        verbose_name = "پروفایل کاربر"
        verbose_name_plural = "پروفایل کاربران"