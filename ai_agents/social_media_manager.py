import os
import random
import time
import json
import requests
import firebase_admin
from firebase_admin import firestore, credentials
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import textwrap

# Initialize Firebase
cred = credentials.Certificate('firebase-key.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

class SocialMediaManager:
    def __init__(self):
        self.platforms = {
            "facebook": {
                "api_key": os.getenv('FB_API_KEY'),
                "page_id": os.getenv('FB_PAGE_ID'),
                "access_token": os.getenv('FB_ACCESS_TOKEN')
            },
            "twitter": {
                "api_key": os.getenv('TWITTER_API_KEY'),
                "api_secret": os.getenv('TWITTER_API_SECRET'),
                "access_token": os.getenv('TWITTER_ACCESS_TOKEN'),
                "access_secret": os.getenv('TWITTER_ACCESS_SECRET')
            },
            "instagram": {
                "page_id": os.getenv('INSTAGRAM_PAGE_ID'),
                "access_token": os.getenv('INSTAGRAM_ACCESS_TOKEN')
            }
        }
        self.hashtags = [
            "#FreeState", "#FreeStateDirectory", "#LocalBusiness", 
            "#SouthAfrica", "#SupportLocal", "#SmallBusinessSA"
        ]
        
    def create_content(self):
        """Create social media content"""
        # Get featured business
        business = self.get_featured_business()
        if not business:
            return None
            
        # Generate content
        text = self.generate_caption(business)
        image = self.create_image(business)
        
        return text, image
    
    def get_featured_business(self):
        """Select a business to feature"""
        # Look for businesses with paid tiers first
        paid_ref = db.collection('listings').where('tier', 'in', ['independent', 'large_business'])\
            .where('last_featured', '<', datetime.utcnow() - timedelta(days=7))\
            .limit(20)
        
        paid_businesses = [doc.to_dict() for doc in paid_ref.stream()]
        
        if paid_businesses:
            return random.choice(paid_businesses)
        
        # Fallback to free listings
        free_ref = db.collection('listings').where('tier', '==', 'free')\
            .where('last_featured', '<', datetime.utcnow() - timedelta(days=30))\
            .limit(50)
        
        free_businesses = [doc.to_dict() for doc in free_ref.stream()]
        return random.choice(free_businesses) if free_businesses else None
    
    def generate_caption(self, business):
        """Generate social media caption"""
        templates = [
            f"🌟 Featured Business: {business['business_name']} in {business['town']}! 🌟\n\n"
            f"{business.get('description', 'Check out this great local business!')}\n\n"
            f"📍 {business['address']}\n"
            f"📞 {business['phone']}\n\n",
            
            f"Looking for {business['category']} services in {business['region']}? "
            f"Check out {business['business_name']} in {business['town']}!\n\n"
            f"{business.get('description', 'Quality services at great prices!')}\n\n",
            
            f"🚀 Boost your local business! {business['business_name']} is featured today on Free State Directory.\n"
            f"Services: {business.get('services', business['category'])}\n\n"
        ]
        
        caption = random.choice(templates)
        caption += f"👉 Visit their listing: https://freestatedirectory.co.za/b/{business['id']}\n\n"
        caption += " ".join(random.sample(self.hashtags, 3))
        
        return caption
    
    def create_image(self, business):
        """Create social media image"""
        # Create base image
        img = Image.new('RGB', (1200, 630), color=(35, 35, 60))
        draw = ImageDraw.Draw(img)
        
        # Add business name
        title = business['business_name']
        font = ImageFont.truetype("arialbd.ttf", 48)
        title_lines = textwrap.wrap(title, width=30)
        
        y = 50
        for line in title_lines:
            w, h = draw.textsize(line, font=font)
            draw.text(((1200-w)/2, y), line, fill=(255, 215, 0), font=font)
            y += h + 10
        
        # Add location and category
        subtitle = f"{business['category']} • {business['town']}, {business['region']}"
        font = ImageFont.truetype("arial.ttf", 32)
        w, h = draw.textsize(subtitle, font=font)
        draw.text(((1200-w)/2, y+20), subtitle, fill=(220, 220, 220), font=font)
        
        # Add Free State Directory logo
        try:
            logo = Image.open("assets/logo.png")
            logo.thumbnail((200, 200))
            img.paste(logo, (50, 50), logo)
        except:
            pass
        
        # Convert to bytes
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        return img_bytes
    
    def post_to_platforms(self, text, image):
        """Post content to all platforms"""
        # Facebook
        if self.platforms['facebook']['access_token']:
            self.post_to_facebook(text, image)
        
        # Twitter
        if self.platforms['twitter']['access_token']:
            self.post_to_twitter(text, image)
        
        # Instagram
        if self.platforms['instagram']['access_token']:
            self.post_to_instagram(text, image)
    
    def post_to_facebook(self, text, image):
        """Post to Facebook Page"""
        url = f"https://graph.facebook.com/{self.platforms['facebook']['page_id']}/photos"
        files = {'source': ('image.png', image, 'image/png')}
        data = {
            'access_token': self.platforms['facebook']['access_token'],
            'message': text
        }
        
        try:
            response = requests.post(url, files=files, data=data)
            if response.status_code == 200:
                print("✅ Posted to Facebook")
            else:
                print(f"Facebook error: {response.text}")
        except Exception as e:
            print(f"Facebook error: {str(e)}")
    
    def post_to_twitter(self, text, image):
        """Post to Twitter"""
        # Twitter API v2 requires media upload first
        media_url = "https://upload.twitter.com/1.1/media/upload.json"
        media_data = {'media': image.read()}
        headers = {"Authorization": f"Bearer {self.platforms['twitter']['access_token']}"}
        
        try:
            # Upload media
            media_response = requests.post(media_url, files=media_data, headers=headers)
            media_id = media_response.json().get('media_id_string')
            
            if media_id:
                # Create tweet
                tweet_url = "https://api.twitter.com/2/tweets"
                tweet_data = {"text": text, "media": {"media_ids": [media_id]}}
                response = requests.post(tweet_url, json=tweet_data, headers=headers)
                
                if response.status_code == 201:
                    print("✅ Posted to Twitter")
                else:
                    print(f"Twitter error: {response.text}")
        except Exception as e:
            print(f"Twitter error: {str(e)}")
    
    def post_to_instagram(self, text, image):
        """Post to Instagram"""
        # Instagram requires Facebook page connection
        page_id = self.platforms['instagram']['page_id']
        access_token = self.platforms['instagram']['access_token']
        
        # Step 1: Create media container
        container_url = f"https://graph.facebook.com/v18.0/{page_id}/media"
        container_data = {
            'image_url': 'https://example.com/image.png',  # Would need to upload first
            'caption': text,
            'access_token': access_token
        }
        
        try:
            # This is simplified - real implementation requires image upload
            print("⚠️ Instagram posting not fully implemented")
        except Exception as e:
            print(f"Instagram error: {str(e)}")
    
    def schedule_posts(self):
        """Schedule posts throughout the day"""
        post_times = ["09:00", "12:00", "15:00", "18:00"]
        
        for post_time in post_times:
            # Create and post content
            content = self.create_content()
            if content:
                text, image = content
                self.post_to_platforms(text, image)
            
            # Wait until next post time
            time.sleep(3 * 3600)  # 3 hours
    
    def run(self):
        """Main run loop"""
        while True:
            try:
                self.schedule_posts()
                print("💤 Social media agent sleeping until tomorrow")
                time.sleep(86400)  # 24 hours
            except Exception as e:
                print(f"Social media error: {str(e)}")
                time.sleep(3600)  # Retry after 1 hour

if __name__ == "__main__":
    smm = SocialMediaManager()
    smm.run()
