from twilio.rest import Client
import os
from dotenv import load_dotenv

load_dotenv()

client = Client(
    os.getenv("TWILIO_SID"),
    os.getenv("TWILIO_AUTH")
)

call = client.calls.create(
    to=os.getenv("YOUR_PHONE_NUMBER"),
    from_=os.getenv("TWILIO_PHONE_NUMBER"),
    url=" https://implied-maldives-experimental-uzbekistan.trycloudflare.com/voice"
)

print("Calling your number now...")
