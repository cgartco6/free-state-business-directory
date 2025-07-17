import os
import random
import time
from datetime import datetime
import firebase_admin
from firebase_admin import firestore
from firebase_admin import credentials
import requests
import json

# Initialize Firestore
cred = credentials.Certificate('firebase-key.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

class SocialMediaManager:
    def __init__(self):
        self.buffer_token = os.getenv('BUFFER_TOKEN')
        self.facebook_page_id = os.getenv('FB_PAGE_ID')
        self.instagram_id = os.getenv('INSTAGRAM_ID')
        self.twitter_handle = os.getenv('TWITTER_HANDLE')
        
    def post_content(self):
        # Get a random featured business
        featured = self._get_featured_business()
        if not featured:
            print("No featured businesses to post.")
            return
            
        # Create post content
        message = self._generate_message(featured)
        image_url = featured.get('image_url', None)
        
        # Post to Buffer (which schedules to all connected profiles)
        self._post_to_buffer(message, image_url)
        
    def _get_featured_business(self):
        # Get a random paid business that hasn't been featured recently
        now = datetime.utcnow()
        one_week_ago = now - timedelta(days=7)
        
        # Query Firestore for eligible businesses
        query = db.collection('listings').where('subscription_tier', 'in', ['independent', 'large'])\
            .where('last_featured', '<', one_week_ago)\
            .limit(100)
        
        businesses = [doc.to_dict() for doc in query.stream()]
        if not businesses:
            return None
            
        return random.choice(businesses)
        
    def _generate_message(self, business):
        # Create engaging social media text
        templates = [
            f"Check out {business['name']} in {business['region']}! {business['description'][:100]}...",
            f"Featured Business: {business['name']} - {business['category']} service in {business['town']}",
            f"Looking for {business['category']} services? Visit {business['name']} in {business['town']}!"
        ]
        message = random.choice(templates)
        message += f"\n\nView their listing: https://freestatedirectory.co.za/business/{business['id']}"
        message += "\n#FreeStateDirectory #FreeStateBusiness"
        return message
        
    def _post_to_buffer(self, message, image_url=None):
        headers = {
            'Authorization': f'Bearer {self.buffer_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'text': message,
            'profile_ids': [
                self.facebook_page_id,
                self.instagram_id,
                self.twitter_handle
            ],
            'media': {'photo': image_url} if image_url else None,
            'shorten': True,
            'now': True  # Post immediately
        }
        
        response = requests.post('https://api.bufferapp.com/1/updates/create.json', 
                                headers=headers, 
                                data=json.dumps(payload))
        
        if response.status_code != 200:
            print(f"Buffer post failed: {response.text}")
        else:
            print("Successfully posted to Buffer!")
            
    # Example: Run daily at scheduled time
    def schedule_daily_post(self):
        # This would be called by the orchestrator at a set time
        self.post_content()

if __name__ == "__main__":
    smm = SocialMediaManager()
    smm.schedule_daily_post()
