Emergency Blood Alert IVR System – Level 01
A multi-language, AI-powered IVR system to connect patients in urgent need of blood with matching donors in real time using Twilio, OpenAI Whisper, and Google Sheets.
Designed for English, Hindi, and Telugu users, it automates the process of collecting patient details, finding matching donors, and sending SMS alerts — potentially saving lives during emergencies.

🌟 Features
Multi-language support – English, Hindi, Telugu call flows.

Automated IVR – Patients provide details via voice or keypad.

Speech-to-text transcription – Powered by OpenAI Whisper.

Real-time donor matching – Fetches from a Google Sheets donor database.

Instant SMS alerts – Notifies matched donors immediately.

Row-wise patient data logging – Records all patient details in a Google Sheet.

🛠 Tech Stack
Backend: Python (Flask)

Telephony: Twilio IVR

Speech-to-Text: OpenAI Whisper

Database: Google Sheets API

Hosting: Local (cloudflared/ngrok tunnel for Twilio)

