import schedule
import time
from datetime import datetime, timedelta
from . import data_scraper, customer_support, social_media_manager

def run_agents():
    # Daily scraping for new businesses
    schedule.every().day.at("02:00").do(data_scraper.scrape_new_listings)
    
    # Renewal reminders (3 days before expiry)
    schedule.every().hour.do(check_expirations)
    
    # Social media posting
    schedule.every(4).hours.do(social_media_manager.post_content)
    
    # Customer support monitoring
    schedule.every(30).minutes.do(customer_support.check_messages)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

def check_expirations():
    # Firestore query for expiring listings
    expiring = db.collection('listings').where(
        'expiry_date', '==', datetime.now() + timedelta(days=3)
    ).stream()
    
    for listing in expiring:
        customer_support.send_renewal_reminder(listing.id)

if __name__ == "__main__":
    run_agents()
