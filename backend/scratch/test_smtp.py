import os
import smtplib
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

print(f"Testing SMTP connection for: {SMTP_EMAIL}")
print("Attempting to connect to smtp.gmail.com:587...")

try:
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    print("Connection established. Attempting login...")
    server.login(SMTP_EMAIL, SMTP_PASSWORD)
    print("[+] Success! SMTP credentials are correct and working.")
    server.quit()
except Exception as e:
    print("[-] Error: SMTP connection/authentication failed.")
    print(f"Details: {e}")
