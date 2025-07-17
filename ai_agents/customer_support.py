import os
from rasa.core.agent import Agent
from rasa.shared.constants import DEFAULT_MODELS_PATH
from firebase_admin import firestore, credentials
import asyncio
import json
import requests

# Initialize Firestore
cred = credentials.Certificate('firebase-key.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

class CustomerSupportAgent:
    def __init__(self):
        # Load the Rasa model (train with Rasa Open Source and place model in models/)
        model_path = os.path.join(DEFAULT_MODELS_PATH, "rasa_model.tar.gz")
        self.agent = Agent.load(model_path)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
    async def handle_message(self, user_id, message):
        # Get or create conversation track
        conv_ref = db.collection('conversations').document(user_id)
        doc = conv_ref.get()
        if doc.exists:
            tracker = doc.to_dict().get('tracker', [])
        else:
            tracker = []
            
        # Process message with Rasa
        responses = await self.agent.handle_text(message, sender_id=user_id)
        
        # Update conversation tracker in Firestore
        new_tracker = tracker + [{"user": message}, {"bot": responses[0]['text']}]
        conv_ref.set({'tracker': new_tracker})
        
        return responses[0]['text']
    
    def send_renewal_reminder(self, user_id):
        # Fetch user details
        user_ref = db.collection('users').document(user_id)
        user = user_ref.get().to_dict()
        
        # Customized message
        message = f"Hi {user['name']}, your listing for {user['business_name']} expires in 3 days. Renew now to maintain visibility!"
        self._send_sms(user['phone'], message)
        self._send_email(user['email'], "Listing Renewal Reminder", message)
        
    def _send_sms(self, phone, message):
        # Using Twilio free trial (or similar service)
        account_sid = os.getenv('TWILIO_SID')
        auth_token = os.getenv('TWILIO_TOKEN')
        client = Client(account_sid, auth_token)
        
        message = client.messages.create(
            body=message,
            from_=os.getenv('TWILIO_NUMBER'),
            to=phone
        )
        return message.sid
    
    def _send_email(self, email, subject, body):
        # Using SendGrid free tier
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        
        message = Mail(
            from_email='support@freestatedirectory.co.za',
            to_emails=email,
            subject=subject,
            html_content=body)
        try:
            sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
            response = sg.send(message)
            return response.status_code
        except Exception as e:
            print(e)
            return None

# Singleton instance for the agent
support_agent = CustomerSupportAgent()

# Example usage (for testing)
if __name__ == "__main__":
    # Simulate a renewal reminder
    support_agent.send_renewal_reminder("test_user_id")
    
    # Simulate a chat
    async def test_chat():
        response = await support_agent.handle_message("user123", "Hello")
        print(response)
    asyncio.run(test_chat())
