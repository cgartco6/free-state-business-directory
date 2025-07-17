from diffusers import StableDiffusionPipeline
import torch
import requests
from io import BytesIO

def generate_image(prompt, output_path):
    model_id = "stabilityai/stable-diffusion-2-1"
    pipe = StableDiffusionPipeline.from_pretrained(model_id, torch_dtype=torch.float16)
    pipe = pipe.to("cuda" if torch.cuda.is_available() else "cpu")
    
    image = pipe(prompt, height=512, width=768).images[0]
    
    # Add anti-theft watermark
    image = add_watermark(image)
    
    image.save(output_path)
    return output_path

def add_watermark(img):
    # Simplified watermark implementation
    from PIL import Image, ImageDraw, ImageFont
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    text = "FreeStateDir©"
    draw.text((10, img.height-30), text, (255,255,255), font=font)
    return img

# Example usage
generate_image("Bloemfontein cityscape at sunset", "frontend/public/assets/bloemfontein.jpg")
