from openai import OpenAI

client = OpenAI(
    api_key="token-abc123",
    base_url="http://10.32.2.11:58795/v1",
    timeout=120.0  # 2 minutes
)

try:
    response = client.chat.completions.create(
        model="/model",
        messages=[{"role": "user", "content": "Hello"}]
    )
    print("Success:", response.choices[0].message.content)
except Exception as e:
    print("Error:", e)