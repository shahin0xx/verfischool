from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import *

class AttendanceInline(admin.TabularInline):
    model = Attendance
    extra = 0
    fields = ['date', 'time', 'camera', 'confidence_display']
    readonly_fields = ['date', 'time', 'camera', 'confidence_display']
    
    def confidence_display(self, obj):
        if obj.confidence:
            return f"{obj.confidence:.1%}"
        return "N/A"
    confidence_display.short_description = 'دقت'

@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'grade', 'field', 'room_number', 'student_count']
    list_filter = ['grade', 'field']
    search_fields = ['name', 'grade', 'field', 'room_number']
    ordering = ['grade', 'name']
    
    def student_count(self, obj):
        count = obj.student_set.filter(is_active=True).count()
        return format_html('<span class="badge bg-primary">{}</span>', count)
    student_count.short_description = 'تعداد دانش‌آموزان'

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['photo_preview', 'full_name_display', 'student_id', 'classroom_link', 'is_active_badge']
    list_filter = ['classroom', 'is_active', 'classroom__grade']
    search_fields = ['first_name', 'last_name', 'student_id', 'national_id']
    readonly_fields = ['photo_preview_large', 'created_at', 'updated_at']
    inlines = [AttendanceInline]
    
    fieldsets = (
        ('اطلاعات شخصی', {
            'fields': (('first_name', 'last_name'), 
                      ('student_id', 'national_id'),
                      'classroom')
        }),
        ('عکس و اطلاعات چهره', {
            'fields': ('photo', 'photo_preview_large')
        }),
        ('وضعیت', {
            'fields': ('is_active',)
        }),
        ('اطلاعات سیستمی', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def full_name_display(self, obj):
        return format_html(
            '<strong>{}</strong><br><small class="text-muted">{}</small>',
            obj.full_name(),
            f'کد: {obj.student_id}'
        )
    full_name_display.short_description = 'نام و کد'
    
    def photo_preview(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" width="50" height="50" style="border-radius: 50%; object-fit: cover;" />',
                obj.photo.url
            )
        return format_html(
            '<div style="width: 50px; height: 50px; border-radius: 50%; background: #f0f0f0; '
            'display: flex; align-items: center; justify-content: center;">'
            '<i class="fas fa-user" style="color: #999;"></i>'
            '</div>'
        )
    photo_preview.short_description = 'عکس'
    
    def photo_preview_large(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" width="200" height="200" style="border-radius: 10px; object-fit: cover;" />',
                obj.photo.url
            )
        return "بدون عکس"
    photo_preview_large.short_description = 'پیش‌نمایش عکس'
    
    def classroom_link(self, obj):
        if obj.classroom:
            url = reverse('admin:verifi_classroom_change', args=[obj.classroom.id])
            return format_html(
                '<a href="{}" style="color: #4361ee; text-decoration: none;">{}</a>',
                url, obj.classroom.name
            )
        return "بدون کلاس"
    classroom_link.short_description = 'کلاس'
    
    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span class="badge bg-success" style="padding: 5px 10px; border-radius: 20px;">فعال</span>'
            )
        return format_html(
            '<span class="badge bg-danger" style="padding: 5px 10px; border-radius: 20px;">غیرفعال</span>'
        )
    is_active_badge.short_description = 'وضعیت'

@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ['name', 'location', 'camera_type_display', 'status_badge', 'is_active']
    list_filter = ['camera_type', 'is_active']
    search_fields = ['name', 'location', 'ip_address']
    readonly_fields = ['last_seen']
    
    def camera_type_display(self, obj):
        return obj.get_camera_type_display()
    camera_type_display.short_description = 'نوع'
    
    def status_badge(self, obj):
        from django.utils import timezone
        if not obj.is_active:
            return format_html(
                '<span class="badge bg-secondary" style="padding: 5px 10px; border-radius: 20px;">غیرفعال</span>'
            )
        
        if obj.last_seen:
            time_diff = (timezone.now() - obj.last_seen).seconds
            if time_diff < 60:
                return format_html(
                    '<span class="badge bg-success" style="padding: 5px 10px; border-radius: 20px;">آنلاین</span>'
                )
        
        return format_html(
            '<span class="badge bg-warning" style="padding: 5px 10px; border-radius: 20px;">آفلاین</span>'
        )
    status_badge.short_description = 'وضعیت'

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['student_info', 'camera_info', 'date', 'time', 'confidence_display']
    list_filter = ['date', 'camera', 'student__classroom']
    search_fields = ['student__first_name', 'student__last_name', 'student__student_id']
    readonly_fields = ['confidence_display']
    
    def student_info(self, obj):
        url = reverse('admin:verifi_student_change', args=[obj.student.id])
        return format_html(
            '<a href="{}" style="color: #333; text-decoration: none; font-weight: bold;">{}</a>',
            url, obj.student.full_name()
        )
    student_info.short_description = 'دانش‌آموز'
    
    def camera_info(self, obj):
        if obj.camera:
            return obj.camera.name
        return "بدون دوربین"
    camera_info.short_description = 'دوربین'
    
    def confidence_display(self, obj):
        return f"{obj.confidence:.1%}"
    confidence_display.short_description = 'دقت'

@admin.register(DailyReport)
class DailyReportAdmin(admin.ModelAdmin):
    list_display = ['classroom', 'date', 'present_count', 'absent_count', 'total_students']
    list_filter = ['date', 'classroom']
    date_hierarchy = 'date'

@admin.register(FaceRecognitionLog)
class FaceRecognitionLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'action_display', 'student_info', 'confidence_display']
    list_filter = ['action', 'created_at']
    search_fields = ['student__first_name', 'student__last_name', 'student__student_id', 'details']
    readonly_fields = ['created_at']
    
    def action_display(self, obj):
        return obj.get_action_display()
    action_display.short_description = 'عملیات'
    
    def student_info(self, obj):
        if obj.student:
            return obj.student.full_name()
        return "ناشناس"
    student_info.short_description = 'دانش‌آموز'
    
    def confidence_display(self, obj):
        if obj.confidence:
            return f"{obj.confidence:.1%}"
        return "-"
    confidence_display.short_description = 'دقت'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(UnknownPerson)
class UnknownPersonAdmin(admin.ModelAdmin):
    list_display = ['camera', 'first_seen', 'last_seen', 'duration_display', 'has_video']
    list_filter = ['camera', 'first_seen']
    search_fields = ['camera__name', 'camera__location']
    readonly_fields = ['first_seen', 'last_seen']
    
    def duration_display(self, obj):
        minutes = obj.duration_seconds // 60
        seconds = obj.duration_seconds % 60
        return f"{minutes}:{seconds:02d}"
    duration_display.short_description = 'مدت زمان'
    
    def has_video(self, obj):
        if obj.video_path:
            return "✅ دارد"
        return "❌ ندارد"
    has_video.short_description = 'ویدیو'

@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ['key', 'value_preview', 'description_preview', 'updated_at']
    search_fields = ['key', 'value', 'description']
    readonly_fields = ['updated_at']
    
    def value_preview(self, obj):
        if len(obj.value) > 50:
            return obj.value[:50] + '...'
        return obj.value
    value_preview.short_description = 'مقدار'
    
    def description_preview(self, obj):
        if obj.description and len(obj.description) > 50:
            return obj.description[:50] + '...'
        return obj.description or '-'
    description_preview.short_description = 'توضیحات'

admin.site.site_header = "سیستم تشخیص چهره مدرسه"
admin.site.site_title = "مدیریت سیستم"
admin.site.index_title = "پنل مدیریت"