import requests
from firebase_admin import firestore

def process_payment(user_id, amount, package):
    payload = {
        "merchant_id": os.getenv("PAYFAST_MERCHANT_ID"),
        "merchant_key": os.getenv("PAYFAST_MERCHANT_KEY"),
        "amount": str(amount),
        "item_name": package,
        "return_url": "https://yourdomain.com/success",
        "cancel_url": "https://yourdomain.com/cancel",
        "notify_url": "https://yourdomain.com/payfast-webhook",
        "custom_int1": user_id
    }
    
    response = requests.post("https://www.payfast.co.za/eng/process", data=payload)
    return response.url  # Redirect user to this URL

def handle_webhook(data):
    db = firestore.client()
    if data['payment_status'] == 'COMPLETE':
        user_id = data['custom_int1']
        amount = float(data['amount_gross'])
        
        # Apply revenue split
        owner_share = amount * 0.60
        ai_fund = amount * 0.40
        
        # Update Firestore
        db.collection('transactions').document(data['pf_payment_id']).set({
            'user_id': user_id,
            'amount': amount,
            'owner_share': owner_share,
            'ai_fund': ai_fund,
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        
        # Upgrade listing
        upgrade_listing(user_id, data['item_name'])
