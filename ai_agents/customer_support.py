import os
import re
import json
import time
import random
import requests
import firebase_admin
from firebase_admin import firestore, credentials
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from rasa.core.agent import Agent
from rasa.shared.constants import DEFAULT_MODELS_PATH

# Initialize Firebase
cred = credentials.Certificate('firebase-key.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

class CustomerSupportAgent:
    def __init__(self):
        # Load Rasa model
        self.agent = Agent.load(os.path.join(DEFAULT_MODELS_PATH, "rasa_model.tar.gz"))
        
        # Initialize Telegram bot
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.updater = Updater(token=self.telegram_token, use_context=True)
        self.dispatcher = self.updater.dispatcher
        
        # Register handlers
        self.dispatcher.add_handler(MessageHandler(Filters.text, self.handle_message))
        self.dispatcher.add_handler(CommandHandler('renew', self.handle_renewal))
        self.dispatcher.add_handler(CommandHandler('help', self.handle_help))
        
        # Start polling in background
        self.updater.start_polling()
        
        print("🤖 Customer Support Agent Initialized")

    async def handle_rasa_message(self, user_id, message):
        """Process messages with Rasa NLP"""
        responses = await self.agent.handle_text(message, sender_id=user_id)
        return responses[0]['text'] if responses else "I didn't understand that."

    def handle_message(self, update: Update, context: CallbackContext):
        """Handle incoming messages"""
        user_id = str(update.message.from_user.id)
        message = update.message.text
        
        # Check if it's a command-like message
        if message.lower().startswith(('renew', 'payment', 'boost')):
            response = self.handle_renewal_request(user_id, message)
        else:
            # Process with Rasa
            response = asyncio.run(self.handle_rasa_message(user_id, message))
        
        update.message.reply_text(response)

    def handle_renewal(self, update: Update, context: CallbackContext):
        """Handle /renew command"""
        user_id = str(update.message.from_user.id)
        response = self.handle_renewal_request(user_id)
        update.message.reply_text(response)

    def handle_help(self, update: Update, context: CallbackContext):
        """Handle /help command"""
        help_text = (
            "🌟 Free State Directory Support 🌟\n\n"
            "Commands:\n"
            "/renew - Renew your listing\n"
            "/help - Show this help\n\n"
            "Ask me about:\n"
            "- Listing status\n"
            "- Payment issues\n"
            "- Boosting your listing\n"
            "- Account management"
        )
        update.message.reply_text(help_text)

    def handle_renewal_request(self, user_id, message=None):
        """Process listing renewal requests"""
        # Fetch user's active listings
        listings_ref = db.collection('listings').where('owner_id', '==', user_id)
        listings = listings_ref.stream()
        
        expiring_listings = []
        for listing in listings:
            listing_data = listing.to_dict()
            if listing_data.get('expiry_date') and listing_data['expiry_date'] < time.time() + 259200:  # 3 days
                expiring_listings.append({
                    'id': listing.id,
                    'name': listing_data.get('business_name', 'Unknown'),
                    'expiry': listing_data['expiry_date']
                })
        
        if not expiring_listings:
            return "You don't have any listings expiring soon!"
        
        # Generate payment links
        response = "Your listings expiring soon:\n"
        for listing in expiring_listings:
            payment_link = self.generate_payment_link(user_id, listing['id'])
            response += f"\n- {listing['name']}: [Renew Now]({payment_link})"
        
        return response + "\n\nClick the links to renew your listings!"

    def generate_payment_link(self, user_id, listing_id):
        """Generate PayFast payment link"""
        # Get listing details
        listing_ref = db.collection('listings').document(listing_id)
        listing = listing_ref.get().to_dict()
        
        # Determine price based on type
        if listing.get('tier') == 'large_business':
            amount = 800.00  # ZAR
        elif listing.get('tier') == 'independent':
            amount = 300.00
        else:
            amount = 0.00  # Free tier renewal should be handled separately
        
        payload = {
            "merchant_id": os.getenv('PAYFAST_MERCHANT_ID'),
            "merchant_key": os.getenv('PAYFAST_MERCHANT_KEY'),
            "amount": str(amount),
            "item_name": f"Listing Renewal - {listing['business_name']}",
            "return_url": "https://freestatedirectory.co.za/success",
            "cancel_url": "https://freestatedirectory.co.za/cancel",
            "notify_url": "https://freestatedirectory.co.za/payfast-webhook",
            "custom_int1": user_id,
            "custom_str1": listing_id
        }
        
        # For demo, return a mock link
        return f"https://freestatedirectory.co.za/pay?user={user_id}&listing={listing_id}"

    def send_renewal_reminder(self):
        """Send renewal reminders to users with expiring listings"""
        now = time.time()
        three_days = 259200  # 3 days in seconds
        
        # Query listings expiring in 3 days
        expiring_ref = db.collection('listings').where('expiry_date', '>', now).where('expiry_date', '<', now + three_days)
        listings = expiring_ref.stream()
        
        for listing in listings:
            listing_data = listing.to_dict()
            user_ref = db.collection('users').document(listing_data['owner_id'])
            user = user_ref.get().to_dict()
            
            if user.get('telegram_id'):
                # Send Telegram message
                bot = Bot(token=self.telegram_token)
                message = (
                    f"⏰ Your listing for {listing_data['business_name']} is expiring soon!\n"
                    f"Renew now to maintain your visibility: /renew"
                )
                bot.send_message(chat_id=user['telegram_id'], text=message)
            
            if user.get('email'):
                # Send email
                self.send_email(
                    user['email'],
                    "Your Free State Directory Listing is Expiring",
                    f"Renew your listing for {listing_data['business_name']}: https://freestatedirectory.co.za/renew/{listing.id}"
                )

    def send_email(self, email, subject, body):
        """Send email via SendGrid"""
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        
        message = Mail(
            from_email='support@freestatedirectory.co.za',
            to_emails=email,
            subject=subject,
            html_content=body)
        
        try:
            sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
            sg.send(message)
        except Exception as e:
            print(f"Email error: {str(e)}")

    def run(self):
        """Main run loop"""
        while True:
            try:
                # Check every hour for renewals
                self.send_renewal_reminder()
                time.sleep(3600)
            except Exception as e:
                print(f"Support agent error: {str(e)}")
                time.sleep(60)

if __name__ == "__main__":
    agent = CustomerSupportAgent()
    agent.run()
