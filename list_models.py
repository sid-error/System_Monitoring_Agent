import google.generativeai as genai
import os

# Your API key is already set in environment variable
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

for model in genai.list_models():
    if "generateContent" in model.supported_generation_methods:
        print(model.name)