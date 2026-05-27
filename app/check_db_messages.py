import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django.setup()

from ai_tools.models import AiConversationMessage

def check():
    messages = AiConversationMessage.objects.filter(role=AiConversationMessage.ROLE_ASSISTANT).order_by("-id")[:5]
    print(f"Found {len(messages)} assistant messages:")
    for msg in messages:
        print(f"\nID: {msg.id} | Session: {msg.session_id} | Model: {msg.model}")
        print(f"Content Length: {len(msg.content)}")
        print("--- CONTENT ---")
        # Print the last 300 characters
        print(msg.content[-400:])
        print("----------------")

if __name__ == "__main__":
    check()
