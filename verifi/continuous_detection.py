# به انتهای recognition.py اضافه کنید

class HighAccuracyFaceRecognition(FaceRecognitionSystem):
    def __init__(self):
        super().__init__()
        self.accuracy_boost = {
            'multiple_encodings': True,
            'enhanced_matching': True,
            'adaptive_threshold': True
        }
    
    def extract_multiple_encodings(self, image_path):
        """استخراج چندین encoding از یک تصویر"""
        try:
            image = face_recognition.load_image_file(image_path)
            encodings = []
            
            # چرخش‌های مختلف
            rotations = [0, 90, 180, 270]
            
            for angle in rotations:
                if angle > 0:
                    # چرخش تصویر
                    from PIL import Image
                    pil_image = Image.open(image_path)
                    rotated = pil_image.rotate(angle)
                    rotated_image = np.array(rotated)
                else:
                    rotated_image = image
                
                # استخراج encoding با تنظیمات مختلف
                face_encodings = face_recognition.face_encodings(
                    rotated_image, 
                    face_recognition.face_locations(rotated_image),
                    num_jitters=10,  # افزایش برای دقت بیشتر
                    model='large'    # مدل بزرگتر
                )
                
                if face_encodings:
                    encodings.extend(face_encodings)
            
            return encodings if encodings else None
            
        except Exception as e:
            self.print_error(f"خطا در استخراج چندگانه: {e}")
            return None
    
    def enhanced_face_matching(self, student, test_encoding):
        """تشخیص پیشرفته با دقت بالا"""
        try:
            # بارگذاری encoding‌های ذخیره شده
            if student.face_encoding:
                stored_encodings = json.loads(student.face_encoding)
                
                # اگر چندین encoding ذخیره شده
                if isinstance(stored_encodings[0], list):
                    best_confidence = 0
                    
                    for stored_encoding in stored_encodings:
                        distance = face_recognition.face_distance(
                            [np.array(stored_encoding)], 
                            test_encoding
                        )[0]
                        confidence = 1.0 - distance
                        
                        if confidence > best_confidence:
                            best_confidence = confidence
                    
                    return best_confidence
                else:
                    # encoding تک
                    distance = face_recognition.face_distance(
                        [np.array(stored_encodings)], 
                        test_encoding
                    )[0]
                    return 1.0 - distance
            
            return 0.0
            
        except Exception as e:
            self.print_error(f"خطا در تطبیق پیشرفته: {e}")
            return 0.0

# ایجاد نمونه با دقت بالا
high_accuracy_system = HighAccuracyFaceRecognition()