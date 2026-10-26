from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Student, ClassRoom, Camera, Attendance
import os
import cv2
import numpy as np
from django.core.exceptions import ValidationError
import threading
import json
import face_recognition
from django.conf import settings


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="ایمیل")
    first_name = forms.CharField(max_length=30, required=True, label="نام")
    last_name = forms.CharField(max_length=150, required=True, label="نام خانوادگی")
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control', 'placeholder': self.fields[field].label})
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user


class StudentRegistrationForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['first_name', 'last_name', 'student_id', 'national_id', 'classroom', 'photo']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'نام دانش‌آموز'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'نام خانوادگی'}),
            'student_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'کد دانش‌آموزی'}),
            'national_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'کد ملی'}),
            'classroom': forms.Select(attrs={'class': 'form-control'}),
            'photo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }
    
    def clean_student_id(self):
        student_id = self.cleaned_data.get('student_id')
        if Student.objects.filter(student_id=student_id).exists():
            raise ValidationError('این کد دانش‌آموزی قبلاً ثبت شده است')
        return student_id
    
    def clean_national_id(self):
        national_id = self.cleaned_data.get('national_id')
        if national_id:
            if len(national_id) != 10:
                raise ValidationError('کد ملی باید ۱۰ رقمی باشد')
            if not national_id.isdigit():
                raise ValidationError('کد ملی باید فقط عدد باشد')
        return national_id
    
    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo:
            if not photo.name.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                raise ValidationError('فقط فرمت‌های تصویری مجاز هستند')
            
            if photo.size > 5 * 1024 * 1024:
                raise ValidationError('حجم عکس نباید بیشتر از ۵ مگابایت باشد')
            
            try:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                    for chunk in photo.chunks(1024):
                        tmp_file.write(chunk)
                    tmp_file.flush()
                    
                    img = cv2.imread(tmp_file.name)
                    if img is None:
                        raise ValidationError('عکس نامعتبر است')
                    
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
                    faces = face_cascade.detectMultiScale(gray, 1.1, 4)
                    
                    if len(faces) == 0:
                        raise ValidationError('چهره‌ای در عکس تشخیص داده نشد')
                    elif len(faces) > 1:
                        raise ValidationError('بیش از یک چهره در عکس تشخیص داده شد')
                    
                    os.unlink(tmp_file.name)
                    
            except Exception as e:
                if isinstance(e, ValidationError):
                    raise e
                raise ValidationError(f'خطا در پردازش عکس')
        
        return photo
    
    def save(self, commit=True):
        student = super().save(commit=False)
        
        if commit:
            student.save()
            
            if student.photo:
                def extract_and_save_encoding():
                    try:
                        photo_path = student.photo.path if hasattr(student.photo, 'path') else os.path.join(settings.MEDIA_ROOT, str(student.photo))
                        
                        if os.path.exists(photo_path):
                            image = face_recognition.load_image_file(photo_path)
                            encodings = face_recognition.face_encodings(image)
                            
                            if encodings:
                                encoding = encodings[0]
                                student.face_encoding = json.dumps(encoding.tolist())
                                student.save(update_fields=['face_encoding'])
                                
                                from .recognition import face_system
                                if hasattr(face_system, 'load_known_faces'):
                                    face_system.load_known_faces()
                                    
                    except Exception as e:
                        print(f"خطا در استخراج ویژگی‌های چهره: {e}")
                
                thread = threading.Thread(target=extract_and_save_encoding)
                thread.daemon = True
                thread.start()
        
        return student


class CameraSetupForm(forms.ModelForm):
    class Meta:
        model = Camera
        fields = ['name', 'location', 'camera_type', 'ip_address', 'port', 
                 'username', 'password', 'map_x', 'map_y', 'record_unknown_videos',
                 'unknown_recording_threshold', 'video_format', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'نام دوربین'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'محل نصب'}),
            'camera_type': forms.Select(attrs={'class': 'form-control'}),
            'ip_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'آدرس IP'}),
            'port': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'پورت'}),
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'نام کاربری'}),
            'password': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'رمز عبور'}),
            'map_x': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': 'موقعیت X'}),
            'map_y': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': 'موقعیت Y'}),
            'record_unknown_videos': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'unknown_recording_threshold': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '60', 'placeholder': 'آستانه ضبط'}),
            'video_format': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_ip_address(self):
        ip_address = self.cleaned_data.get('ip_address')
        camera_type = self.cleaned_data.get('camera_type')
        
        if camera_type == 'ip' and not ip_address:
            raise ValidationError('برای دوربین IP باید آدرس IP وارد شود')
        
        return ip_address
    
    def clean_port(self):
        port = self.cleaned_data.get('port')
        if port and (port < 1 or port > 65535):
            raise ValidationError('پورت باید بین ۱ تا ۶۵۵۳۵ باشد')
        return port


class AttendanceManualForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['student', 'camera', 'confidence', 'notes']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control'}),
            'camera': forms.Select(attrs={'class': 'form-control'}),
            'confidence': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '1', 'step': '0.01', 'placeholder': 'دقت تشخیص'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'توضیحات'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student'].queryset = Student.objects.filter(is_active=True)
        self.fields['camera'].queryset = Camera.objects.filter(is_active=True)


class SearchStudentForm(forms.Form):
    search_type = forms.ChoiceField(
        choices=[
            ('name', 'نام و نام خانوادگی'),
            ('student_id', 'کد دانش‌آموزی'),
            ('national_id', 'کد ملی'),
            ('classroom', 'کلاس'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='نوع جستجو'
    )
    
    search_query = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'عبارت جستجو را وارد کنید...'}),
        label='عبارت جستجو'
    )
    
    camera = forms.ModelChoiceField(
        queryset=Camera.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='نمایش در دوربین'
    )


class ClassRoomForm(forms.ModelForm):
    class Meta:
        model = ClassRoom
        fields = ['name', 'grade', 'field', 'room_number']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'نام کلاس'}),
            'grade': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'پایه'}),
            'field': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'رشته'}),
            'room_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'شماره کلاس'}),
        }


class SystemConfigForm(forms.Form):
    attendance_threshold = forms.FloatField(
        min_value=0.1,
        max_value=1.0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.05'}),
        label='آستانه دقت برای ثبت حضور'
    )
    
    recognition_interval = forms.FloatField(
        min_value=0.001,
        max_value=1.0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
        label='فاصله تشخیص چهره (ثانیه)'
    )
    
    max_unknown_duration = forms.IntegerField(
        min_value=1,
        max_value=600,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label='حداکثر زمان ضبط افراد ناشناس (ثانیه)'
    )
    
    auto_reload_faces = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='بارگذاری مجدد خودکار چهره‌ها'
    )
    
    notification_enabled = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='فعال بودن اعلان‌ها'
    )
    
    backup_enabled = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='فعال بودن پشتیبان‌گیری'
    )


class FaceCaptureForm(forms.Form):
    student_id = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'کد دانش‌آموزی'}),
        label='کد دانش‌آموزی'
    )
    
    capture_method = forms.ChoiceField(
        choices=[
            ('webcam', 'وب‌کم'),
            ('upload', 'آپلود عکس'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label='روش گرفتن عکس',
        initial='webcam'
    )
    
    image_file = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        label='آپلود عکس'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        capture_method = cleaned_data.get('capture_method')
        image_file = cleaned_data.get('image_file')
        
        if capture_method == 'upload' and not image_file:
            raise ValidationError('برای روش آپلود باید عکس انتخاب شود')
        
        return cleaned_data