# apps.py
from django.apps import AppConfig


class VerifiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "verifi"
    
    def ready(self):
        """هنگام راه‌اندازی اپ"""
        try:
            # ایجاد پوشه‌های مورد نیاز
            import os
            from django.conf import settings
            
            media_folders = [
                'students/photos',
                'attendance/captured',
                'attendance/videos',
                'unknown_persons/videos',
                'unknown_persons/thumbnails',
                'debug',
                'logs',
            ]
            
            for folder in media_folders:
                folder_path = os.path.join(settings.MEDIA_ROOT, folder)
                os.makedirs(folder_path, exist_ok=True)
            
            print("✅ پوشه‌های رسانه ایجاد شدند")
            
            # شروع سیستم تشخیص چهره
            from .recognition import face_system
            print("✅ سیستم تشخیص چهره راه‌اندازی شد")
            
        except Exception as e:
            print(f"⚠️ خطا در راه‌اندازی اپ: {e}")