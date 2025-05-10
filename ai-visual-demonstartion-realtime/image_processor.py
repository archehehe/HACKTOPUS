from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch

class ImageDescriber:
    def __init__(self):
        self.device = "cpu"
        model_name = "Salesforce/blip-image-captioning-base"
        self.processor = BlipProcessor.from_pretrained(model_name)
        self.model = BlipForConditionalGeneration.from_pretrained(model_name).to(self.device)

    def describe_image(self, image_path):
        try:
            raw_image = Image.open(image_path).convert("RGB")
            inputs = self.processor(raw_image, return_tensors="pt").to(self.device)
            out = self.model.generate(**inputs, max_new_tokens=30)  # Reduced for speed
            description = self.processor.decode(out[0], skip_special_tokens=True)
            return description
        except Exception as e:
            return f"Error: {str(e)}"
