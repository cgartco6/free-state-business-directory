import requests
from bs4 import BeautifulSoup
import re
import json
import time
import random
from urllib.robotparser import RobotFileParser
from firebase_admin import firestore, credentials
import os

# Initialize Firestore
cred = credentials.Certificate('firebase-key.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# Polite scraping with rate limiting
HEADERS = {
    'User-Agent': 'FreeStateDirectoryBot/1.0 (+https://freestatedirectory.co.za/bot)'
}

class BusinessScraper:
    def __init__(self):
        self.seen_urls = set()
        self.business_data = []
        
    def scrape_region(self, region):
        # Base URLs for different regions (example)
        base_urls = {
            'mangaung': 'https://example.com/mangaung-businesses',
            'xhariep': 'https://example.com/xhariep-businesses'
        }
        
        if region not in base_urls:
            print(f"Region {region} not configured for scraping.")
            return
            
        self._scrape_page(base_urls[region])
        
    def _scrape_page(self, url):
        # Check robots.txt
        rp = RobotFileParser()
        rp.set_url(f"{url}/robots.txt")
        rp.read()
        
        if not rp.can_fetch(HEADERS['User-Agent'], url):
            print(f"Blocked by robots.txt: {url}")
            return
            
        # Fetch page
        time.sleep(random.uniform(1, 3))  # Be polite
        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200:
            print(f"Failed to fetch {url}: {response.status_code}")
            return
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Example: Extract business cards
        for card in soup.select('.business-card'):
            name = card.select_one('.name').text.strip()
            category = card.select_one('.category').text.strip()
            phone = card.select_one('.phone').text.strip() if card.select_one('.phone') else ''
            email = card.select_one('.email').text.strip() if card.select_one('.email') else ''
            address = card.select_one('.address').text.strip() if card.select_one('.address') else ''
            
            # Generate unique ID
            business_id = hashlib.md5(f"{name}{phone}{address}".encode()).hexdigest()
            
            # Save to Firestore if not exists
            doc_ref = db.collection('unclaimed_listings').document(business_id)
            if not doc_ref.get().exists:
                doc_ref.set({
                    'name': name,
                    'category': category,
                    'phone': phone,
                    'email': email,
                    'address': address,
                    'source_url': url,
                    'scraped_at': firestore.SERVER_TIMESTAMP
                })
                # Send claim invite
                self._send_claim_invite(name, email, phone)
                
        # Pagination handling (example)
        next_page = soup.select_one('a.next')
        if next_page and next_page.get('href'):
            next_url = requests.compat.urljoin(url, next_page['href'])
            if next_url not in self.seen_urls:
                self.seen_urls.add(next_url)
                self._scrape_page(next_url)
                
    def _send_claim_invite(self, business_name, email, phone):
        # Send email invite
        if email:
            subject = f"Claim your business listing for {business_name}"
            body = f"We found your business on our directory! Claim it now to manage your listing: https://freestatedirectory.co.za/claim"
            self._send_email(email, subject, body)
            
        # Send SMS invite
        if phone and re.match(r'^\+27[0-9]{9}$', phone):
            message = f"FreeStateDirectory: Claim {business_name}'s listing at https://freestatedirectory.co.za/claim"
            self._send_sms(phone, message)
            
    def _send_sms(self, phone, message):
        # Placeholder for SMS sending (using Twilio or similar)
        print(f"SMS to {phone}: {message}")
        # Implement actual SMS sending in production
        
    def _send_email(self, email, subject, body):
        # Placeholder for email sending (using SendGrid)
        print(f"Email to {email}: {subject} - {body}")
        # Implement actual email sending in production

if __name__ == "__main__":
    scraper = BusinessScraper()
    regions = ['mangaung', 'xhariep', 'lejweleputswa', 'thabo_mofutsanyana', 'fezile_dabi']
    for region in regions:
        scraper.scrape_region(region)
