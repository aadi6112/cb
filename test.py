import os
from dotenv import load_dotenv
import openai

load_dotenv()

# Test OpenAI connection
client = openai.OpenAI(api_key=os.getenv('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'))

# Test chat
response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Say hello!"}]
)
print("Chat test:", response.choices[0].message.content)

# Test embeddings
embedding = client.embeddings.create(
    model="text-embedding-3-small",
    input="Test embedding"
)
print("Embedding test: Success!" if embedding.data[0].embedding else "Failed")