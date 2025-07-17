import os
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import Dense, Embedding, LSTM, Dropout, Bidirectional
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from sklearn.model_selection import train_test_split
from google.cloud import storage
import firebase_admin
from firebase_admin import firestore, credentials
import pickle
import json
from datetime import datetime

# Initialize Firebase
cred = credentials.Certificate('firebase-key.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# Initialize Cloud Storage
storage_client = storage.Client()
bucket = storage_client.bucket(os.getenv('GCS_BUCKET_NAME'))

class ContentModerator:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.max_len = 100
        self.vocab_size = 10000
        self.load_model()
    
    def load_model(self):
        """Load model from storage or initialize"""
        try:
            # Try to load from Cloud Storage
            model_blob = bucket.blob("models/moderation_model.h5")
            model_blob.download_to_filename("local_model.h5")
            self.model = load_model("local_model.h5")
            
            tokenizer_blob = bucket.blob("models/tokenizer.pkl")
            tokenizer_blob.download_to_filename("local_tokenizer.pkl")
            with open("local_tokenizer.pkl", "rb") as f:
                self.tokenizer = pickle.load(f)
                
            print("✅ Loaded existing moderation model")
        except:
            print("⚠️ No model found, initializing new model")
            self.initialize_model()
    
    def initialize_model(self):
        """Initialize a new model"""
        self.model = Sequential([
            Embedding(self.vocab_size, 128, input_length=self.max_len),
            Bidirectional(LSTM(64, return_sequences=True)),
            Bidirectional(LSTM(32)),
            Dense(24, activation='relu'),
            Dropout(0.5),
            Dense(1, activation='sigmoid')
        ])
        
        self.model.compile(
            loss='binary_crossentropy',
            optimizer='adam',
            metrics=['accuracy']
        )
        
        self.tokenizer = Tokenizer(num_words=self.vocab_size)
        print("✅ Initialized new moderation model")
    
    def load_data(self):
        """Load training data from Firestore"""
        scam_ref = db.collection('scam_reports').where('confirmed', '==', True)
        legit_ref = db.collection('listings').where('reported', '==', False).limit(1000)
        
        texts = []
        labels = []
        
        # Scam reports
        for doc in scam_ref.stream():
            data = doc.to_dict()
            texts.append(data['text'])
            labels.append(1)  # Scam
        
        # Legitimate content
        for doc in legit_ref.stream():
            data = doc.to_dict()
            text = f"{data.get('business_name', '')} {data.get('description', '')}"
            texts.append(text)
            labels.append(0)  # Legitimate
        
        return texts, np.array(labels)
    
    def preprocess_data(self, texts, labels):
        """Prepare data for training"""
        # Tokenize text
        self.tokenizer.fit_on_texts(texts)
        sequences = self.tokenizer.texts_to_sequences(texts)
        padded = pad_sequences(sequences, maxlen=self.max_len)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            padded, labels, test_size=0.2, random_state=42
        )
        
        return X_train, X_test, y_train, y_test
    
    def train(self, X_train, y_train, X_test, y_test):
        """Train the model"""
        history = self.model.fit(
            X_train, y_train,
            epochs=10,
            batch_size=32,
            validation_data=(X_test, y_test),
            verbose=1
        )
        
        # Save model
        self.model.save("local_model.h5")
        with open("local_tokenizer.pkl", "wb") as f:
            pickle.dump(self.tokenizer, f)
        
        # Upload to Cloud Storage
        model_blob = bucket.blob("models/moderation_model.h5")
        model_blob.upload_from_filename("local_model.h5")
        
        tokenizer_blob = bucket.blob("models/tokenizer.pkl")
        tokenizer_blob.upload_from_filename("local_tokenizer.pkl")
        
        print("✅ Model trained and saved")
        return history
    
    def predict(self, text):
        """Predict if content is scam"""
        sequence = self.tokenizer.texts_to_sequences([text])
        padded = pad_sequences(sequence, maxlen=self.max_len)
        prediction = self.model.predict(padded)
        return prediction[0][0]
    
    def moderate_content(self, text, threshold=0.7):
        """Moderate text content"""
        scam_score = self.predict(text)
        return scam_score > threshold
    
    def retrain(self):
        """Retrain the model with new data"""
        print("🔁 Retraining moderation model...")
        texts, labels = self.load_data()
        
        if len(texts) < 100:
            print("⚠️ Not enough data for retraining")
            return
            
        X_train, X_test, y_train, y_test = self.preprocess_data(texts, labels)
        self.train(X_train, y_train, X_test, y_test)
        print("✅ Retraining complete")

class ModelTrainer:
    def __init__(self):
        self.moderator = ContentModerator()
    
    def daily_moderation(self):
        """Check new content daily"""
        # Check new listings
        new_listings = db.collection('listings')\
            .where('moderated', '==', False)\
            .where('created_at', '>', datetime.utcnow() - timedelta(days=1))\
            .stream()
        
        for listing in new_listings:
            data = listing.to_dict()
            text = f"{data.get('business_name', '')} {data.get('description', '')}"
            
            if self.moderator.moderate_content(text):
                print(f"🚫 Flagged listing {listing.id}")
                # Mark for review
                db.collection('listings').document(listing.id).update({
                    'status': 'under_review',
                    'moderated': True
                })
            else:
                db.collection('listings').document(listing.id).update({
                    'moderated': True
                })
        
        # Check user reviews
        new_reviews = db.collection('reviews')\
            .where('moderated', '==', False)\
            .where('created_at', '>', datetime.utcnow() - timedelta(days=1))\
            .stream()
        
        for review in new_reviews:
            data = review.to_dict()
            if self.moderator.moderate_content(data['content']):
                print(f"🚫 Flagged review {review.id}")
                db.collection('reviews').document(review.id).update({
                    'status': 'removed',
                    'moderated': True
                })
            else:
                db.collection('reviews').document(review.id).update({
                    'moderated': True
                })
    
    def run(self):
        """Main run loop"""
        while True:
            try:
                print("🔍 Starting daily content moderation")
                self.daily_moderation()
                
                # Retrain weekly
                if datetime.utcnow().weekday() == 0:  # Monday
                    self.moderator.retrain()
                
                print("💤 Training agent sleeping for 24 hours")
                time.sleep(86400)  # 24 hours
            except Exception as e:
                print(f"Training error: {str(e)}")
                time.sleep(3600)  # Retry after 1 hour

if __name__ == "__main__":
    trainer = ModelTrainer()
    trainer.run()
