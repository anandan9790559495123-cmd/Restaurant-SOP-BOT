import google.generativeai as genai

genai.configure(api_key="AIzaSyDd5Zxlf2XDz6_rVuS9wvLrXFQ-MO_3f7A")

models = genai.list_models()

for model in models:
    print(model.name)