import os
import numpy as np
import tensorflow as tf
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Embedding, LSTM, Dense, Dropout
from firebase_admin import firestore, credentials
import json
import pickle

# Initialize Firestore
cred = credentials.Certificate('firebase-key.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

class ModelTrainer:
    def __init__(self):
        self.model = None
        self.tokenizer = Tokenizer(num_words=10000)
        self.max_length = 100
        
    def load_data(self):
        # Fetch training data from Firestore
        scam_data = []
        legit_data = []
        
        # Get scam reports (manually verified)
        scam_ref = db.collection('scam_reports').where('verified', '==', True).stream()
        for doc in scam_ref:
            scam_data.append(doc.to_dict()['text'])
            
        # Get legitimate listings (random sample)
        legit_ref = db.collection('listings').where('reported', '==', False).limit(len(scam_data)*2).stream()
        for doc in legit_ref:
            legit_data.append(doc.to_dict()['description'])
            
        # Create labels: 1 for scam, 0 for legitimate
        texts = scam_data + legit_data
        labels = [1] * len(scam_data) + [0] * len(legit_data)
        
        return texts, labels
        
    def preprocess_data(self, texts, labels):
        # Tokenize text
        self.tokenizer.fit_on_texts(texts)
        sequences = self.tokenizer.texts_to_sequences(texts)
        padded = pad_sequences(sequences, maxlen=self.max_length, truncating='post', padding='post')
        
        # Shuffle data
        indices = np.arange(padded.shape[0])
        np.random.shuffle(indices)
        padded = padded[indices]
        labels = np.array(labels)[indices]
        
        # Split train/test
        split = int(0.8 * len(padded))
        X_train, X_test = padded[:split], padded[split:]
        y_train, y_test = labels[:split], labels[split:]
        
        return X_train, X_test, y_train, y_test
        
    def build_model(self):
        model = Sequential([
            Embedding(10000, 128, input_length=self.max_length),
            LSTM(64, return_sequences=True),
            LSTM(32),
            Dense(24, activation='relu'),
            Dropout(0.5),
            Dense(1, activation='sigmoid')
        ])
        
        model.compile(
            loss='binary_crossentropy',
            optimizer='adam',
            metrics=['accuracy']
        )
        
        return model
        
    def train(self, X_train, y_train, X_test, y_test):
        self.model = self.build_model()
        self.model.fit(
            X_train, y_train,
            epochs=10,
            validation_data=(X_test, y_test),
            batch_size=32
        )
        
        # Save model
        self.model.save('models/scam_detection_model.h5')
        
        # Save tokenizer
        with open('models/tokenizer.pickle', 'wb') as handle:
            pickle.dump(self.tokenizer, handle, protocol=pickle.HIGHEST_PROTOCOL)
            
    def upload_to_storage(self):
        # Upload model and tokenizer to Firebase Storage for production use
        # Implementation depends on your storage setup
        pass
        
    def retrain(self):
        print("Loading data for retraining...")
        texts, labels = self.load_data()
        if len(texts) < 100:
            print("Insufficient data for retraining.")
            return
            
        print(f"Training on {len(texts)} samples...")
        X_train, X_test, y_train, y_test = self.preprocess_data(texts, labels)
        self.train(X_train, y_train, X_test, y_test)
        self.upload_to_storage()
        print("Retraining complete!")

if __name__ == "__main__":
    trainer = ModelTrainer()
    trainer.retrain()
