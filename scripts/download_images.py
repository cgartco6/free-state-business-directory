import requests
import os
import shutil

# List of towns in Free State by area
towns = [
    # Mangaung
    "Bloemfontein", "Botshabelo", "Thaba Nchu",
    # Xhariep
    "Trompsburg", "Philippolis", "Reddersburg",
    # ... add more
]

# Categories for which we need images
categories = [
    "Estate Agents", "Plumbers", "Electricians", "Auto Electricians", "Repair Shops"
]

# Create directories
os.makedirs("frontend/src/assets/towns", exist_ok=True)
os.makedirs("frontend/src/assets/categories", exist_ok=True)

# Unsplash API access key (sign up for free and get one)
ACCESS_KEY = "YOUR_UNSPLASH_ACCESS_KEY"

def download_image(query, save_path):
    url = "https://api.unsplash.com/photos/random"
    params = {
        "query": query,
        "client_id": ACCESS_KEY
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        image_url = data['urls']['regular']
        image_response = requests.get(image_url, stream=True)
        if image_response.status_code == 200:
            with open(save_path, 'wb') as f:
                image_response.raw.decode_content = True
                shutil.copyfileobj(image_response.raw, f)
                print(f"Downloaded {query} image to {save_path}")
        else:
            print(f"Failed to download image for {query}")
    else:
        print(f"Failed to get image for {query}: {response.status_code}")

# Download town images
for town in towns:
    save_path = f"frontend/src/assets/towns/{town.replace(' ', '_').lower()}.jpg"
    download_image(f"{town} Free State South Africa", save_path)

# Download category images
for category in categories:
    save_path = f"frontend/src/assets/categories/{category.replace(' ', '_').lower()}.jpg"
    download_image(f"{category} service Free State South Africa", save_path)
