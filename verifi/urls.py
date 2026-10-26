from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

app_name = 'verifi'

urlpatterns = [
    path('', views.index, name='index'),
    
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    path('dashboard/', views.dashboard, name='dashboard'),
    
    path('search-student/', views.search_student, name='search_student'),
    path('student/<int:student_id>/', views.student_detail, name='student_detail'),
    path('live-track/<int:student_id>/', views.live_track_student, name='live_track_student'),
    
    path('register-student/', views.register_student, name='register_student'),
    path('capture-face/<int:student_id>/', views.capture_face, name='capture_face'),
    
    path('webcam/', views.webcam_view, name='webcam_view'),
    path('webcam/feed/', views.webcam_feed, name='webcam_feed'),
    path('webcam/capture/', views.webcam_capture, name='webcam_capture'),
    
    path('live-detection/', views.live_detection_view, name='live_detection_view'),
    path('live-detection/feed/', views.live_detection_feed, name='live_detection_feed'),
    path('api/live-detection/data/', views.get_live_detection_data, name='get_live_detection_data'),
    
    path('camera-management/', views.camera_management, name='camera_management'),
    path('camera-map/', views.camera_map_view, name='camera_map_view'),
    path('api/camera/position/<int:camera_id>/', views.update_camera_position, name='update_camera_position'),
    
    path('unknown-persons/', views.unknown_persons_view, name='unknown_persons_view'),
    path('unknown-person/<int:unknown_id>/', views.unknown_person_detail, name='unknown_person_detail'),
    path('unknown-person/mark-processed/<int:unknown_id>/', views.mark_as_processed, name='mark_as_processed'),
    path('unknown-person/delete/<int:unknown_id>/', views.delete_unknown_person, name='delete_unknown_person'),
    
    path('attendance-report/', views.attendance_report, name='attendance_report'),
    path('classroom/<int:classroom_id>/', views.classroom_report, name='classroom_report'),
    
    path('recognition-logs/', views.recognition_logs, name='recognition_logs'),
    
    path('system-settings/', views.system_settings, name='system_settings'),
    path('reload-faces/', views.reload_faces, name='reload_faces'),
    
    path('export-attendance/', views.export_attendance, name='export_attendance'),
    
    path('api/attendance/today/', views.api_attendance_today, name='api_attendance_today'),
    path('api/student/<int:student_id>/attendance/', views.api_student_attendance, name='api_student_attendance'),
    path('api/camera-status/', views.api_camera_status, name='api_camera_status'),
    path('api/unknown-persons/', views.api_unknown_persons, name='api_unknown_persons'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)