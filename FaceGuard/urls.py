from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('verifi.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# تنظیمات ادمین
admin.site.site_header = 'مدیریت سیستم تشخیص چهره مدرسه'
admin.site.site_title = 'سیستم تشخیص چهره'
admin.site.index_title = 'پنل مدیریت'