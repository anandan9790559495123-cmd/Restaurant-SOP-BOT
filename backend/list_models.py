import google.generativeai as genai

genai.configure(api_key="AIzaSyDd5Zxlf2XDz6_rVuS9wvLrXFQ-MO_3f7A")

for model in genai.list_models():
    print(model.name)