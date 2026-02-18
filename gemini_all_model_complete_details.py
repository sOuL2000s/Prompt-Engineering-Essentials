from google import genai
from pprint import pprint

client = genai.Client(api_key="api_key_goes_here")

models = client.models.list()

print("=" * 100)
print("GEMINI MODEL FULL DETAILS")
print("=" * 100)

for m in models:
    print("\n" + "=" * 80)
    print("MODEL:", m.name)
    print("=" * 80)

    data = m.model_dump()

    # Basic Info
    print("Display Name:", data.get("display_name"))
    print("Description:", data.get("description"))

    # Token Limits
    print("Input Token Limit:", data.get("input_token_limit"))
    print("Output Token Limit:", data.get("output_token_limit"))

    # Version / Capabilities if available
    print("Supported Modalities:", data.get("supported_modalities"))
    print("Temperature Range:", data.get("temperature_range"))
    print("Top-P Range:", data.get("top_p_range"))

    print("\n--- RAW DATA ---")
    pprint(data)