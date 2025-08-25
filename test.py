import os
from dotenv import load_dotenv
import openai

load_dotenv()

# Test OpenAI connection
client = openai.OpenAI(api_key=os.getenv(''))

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
