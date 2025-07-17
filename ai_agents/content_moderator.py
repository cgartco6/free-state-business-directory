from google.cloud import vision
import tensorflow as tf

class ContentModerator:
    def __init__(self):
        self.text_model = tf.keras.models.load_model('models/text_moderation.h5')
        self.image_client = vision.ImageAnnotatorClient()
    
    def moderate_text(self, text):
        # Check for banned categories
        banned_keywords = ["crypto", "forex", "investment", "adult", "xxx"]
        if any(kw in text.lower() for kw in banned_keywords):
            return False
        
        # ML-based scam detection
        prediction = self.text_model.predict([text])
        return prediction[0][0] < 0.5  # Allow if scam score < 0.5
    
    def moderate_image(self, image_path):
        with open(image_path, "rb") as image_file:
            content = image_file.read()
        
        image = vision.Image(content=content)
        response = self.image_client.safe_search_detection(image=image)
        
        # Block adult/violative content
        if (response.safe_search_annotation.adult > 2 or 
            response.safe_search_annotation.violence > 2):
            return False
        return True
