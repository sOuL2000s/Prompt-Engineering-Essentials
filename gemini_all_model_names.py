from google import genai

client = genai.Client(api_key="api_key_goes_here")

models = client.models.list()

text_models = []
embedding_models = []
image_models = []
audio_models = []
other = []

for m in models:
    name = m.name.lower()

    if "embedding" in name:
        embedding_models.append(m.name)
    elif "imagen" in name:
        image_models.append(m.name)
    elif "audio" in name or "tts" in name:
        audio_models.append(m.name)
    elif "gemini" in name:
        text_models.append(m.name)
    else:
        other.append(m.name)

print("TEXT MODELS:")
print("\n".join(text_models))

print("\nEMBEDDING MODELS:")
print("\n".join(embedding_models))

print("\nIMAGE MODELS:")
print("\n".join(image_models))

print("\nAUDIO MODELS:")
print("\n".join(audio_models))

print("\nOTHER:")
print("\n".join(other))    