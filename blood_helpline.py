from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather, Pause
from twilio.rest import Client
from dotenv import load_dotenv
import os
import requests
import whisper
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import subprocess # Import subprocess to run ffmpeg

# Load environment variables
load_dotenv()
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
FFMPEG_PATH = os.getenv("FFMPEG_PATH") # This should hold the full executable path, e.g., "C:\\...\\ffmpeg.exe"
# Print the FFMPEG_PATH to verify it's being loaded
print(f"DEBUG: FFMPEG_PATH from .env is: {FFMPEG_PATH}")

# Initialize Twilio client for sending messages
twilio_client = Client(TWILIO_SID, TWILIO_AUTH)

# Whisper model
# Consider using a larger model for better accuracy, e.g., "small", "medium", or "large"
# model = whisper.load_model("small")
model = whisper.load_model("base") # Keeping base as per original, but recommend testing larger models for Telugu

# Google Sheets setup
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS, scope)
client = gspread.authorize(creds)
sheet = client.open("CollectRecords").worksheet("Sheet1")
donor_sheet = client.open("CollectRecords").worksheet("DonorDatabase")

# App setup
app = Flask(__name__)
call_data = {}

@app.route("/voice", methods=["POST"])
def voice():
    response = VoiceResponse()
    gather = Gather(num_digits=1, action="/language", timeout=5)
    gather.say("Welcome to the Blood Emergency Helpline. For English, press 1. Hindi ke liye, dho dhabayiye. Telugu kosam, moodu nokkandi.", language="en-IN")
    response.append(gather)
    response.say("No input received. Goodbye.")
    response.hangup()
    return str(response)

@app.route("/language", methods=["POST"])
def language():
    digit = request.form.get("Digits")
    lang_map = {"1": "en-IN", "2": "hi-IN", "3": "te-IN"}
    lang = lang_map.get(digit, "en-IN")
    response = VoiceResponse()
    response.redirect(f"/register?lang={lang}&step=name", method="POST")
    return str(response)

@app.route("/register", methods=["GET", "POST"])
def register():
    lang = request.args.get("lang", "en-IN")
    step = request.args.get("step", "name")

    prompts = {
        "name": {
            "en-IN": "Please say the patient's name after the beep.",
            "hi-IN": "कृपया बीप के बाद मरीज़ का नाम बताएं।",
            "te-IN": "Dayachesi beep taruvata rogi peru cheppandi." # Romanized Telugu
        },
        "phone": {
            "en-IN": "Please enter the 10-digit contact phone number using your keypad.",
            "hi-IN": "कृपया कीपैड से 10 अंकों का संपर्क नंबर दर्ज करें।",
            "te-IN": "Dayachesi Keypad Upayoginchukoni Mobile number nu Type chyandi." # Romanized Telugu
        },
        "blood": {
            "en-IN": "Press the number for required blood group: 1 for A positive, 2 for A negative, 3 for B positive, 4 for B negative, 5 for O positive, 6 for O negative, 7 for A B positive, 8 for A B negative.",
            "hi-IN": "जरूरी ब्लड ग्रुप के लिए नंबर दबाएं: 1 ए पॉजिटिव के लिए, 2 ए नेगेटिव के लिए, 3 बी पॉजिटिव के लिए, 4 बी नेगेटिव के लिए, 5 ओ पॉजिटिव के लिए, 6 ओ नेगेटिव के लिए, 7 एबी पॉजिटिव के लिए, 8 एबी नेगेटिव के लिए।",
            "te-IN": "Miku Kavlasina Blood group : A positive kosam okati nokkandi , A negative Kosam rendu nokkandi, B positive Kosam moodu nokkandi , B negative kosam Naalugu Nokkandi , O Positive kosam Ayidhu nokkandi , O Negative Kosam Aaaru nokkandi , A B positive kosam yeedu nokkandi , A B Negative kosam Yenimidhiii nokkandi." # Romanized Telugu
        },
        "hospital": {
            "en-IN": "Say the hospital and location.",
            "hi-IN": "अस्पताल और स्थान बताएं।",
            "te-IN": "Hospital Address cheppandi." # Romanized Telugu
        }
    }

    response = VoiceResponse()
    response.pause(length=1.5)

    if step == "phone":
        gather = Gather(num_digits=10, action=f"/confirm_phone?lang={lang}", method="POST")
        gather.say(prompts[step].get(lang, prompts[step]["en-IN"]), language=lang)
        response.append(gather)
        response.say("No input received. Goodbye.", language=lang)
        response.hangup()
        return str(response)

    if step == "blood":
        gather = Gather(num_digits=1, action=f"/blood_choice?lang={lang}", method="POST")
        gather.say(prompts[step].get(lang, prompts[step]["en-IN"]), language=lang)
        response.append(gather)
        response.say("No input received. Goodbye.", language=lang)
        response.hangup()
        return str(response)

    response.say(prompts[step].get(lang, prompts[step]["en-IN"]), language=lang)
    response.record(
        max_length=6,
        timeout=3,
        play_beep=True,
        action=f"/process_recording?lang={lang}&step={step}",
        method="POST"
    )
    return str(response)

@app.route("/confirm_phone", methods=["POST"])
def confirm_phone():
    lang = request.args.get("lang", "en-IN")
    phone_number = request.form.get("Digits")
    call_sid = request.form.get("CallSid")

    if not phone_number or len(phone_number) != 10:
        response = VoiceResponse()
        response.say("Invalid phone number. Let's try again.", language=lang)
        response.redirect(f"/register?lang={lang}&step=phone", method="POST")
        return str(response)

    call_data[call_sid] = call_data.get(call_sid, {})
    call_data[call_sid]["Phone"] = phone_number
    print(f"✅ Phone number received: {phone_number}")

    response = VoiceResponse()
    response.say("To confirm the number, press 1. To re-enter, press 2.", language=lang)
    gather = Gather(num_digits=1, action=f"/phone_decision?lang={lang}&phone={phone_number}", method="POST")
    response.append(gather)
    response.say("No input received. Goodbye.", language=lang)
    response.hangup()
    return str(response)

@app.route("/phone_decision", methods=["POST"])
def phone_decision():
    lang = request.args.get("lang", "en-IN")
    digit = request.form.get("Digits")

    if digit == "1":
        response = VoiceResponse()
        response.redirect(f"/register?lang={lang}&step=blood", method="POST")
    else:
        response = VoiceResponse()
        response.redirect(f"/register?lang={lang}&step=phone", method="POST")
    return str(response)

@app.route("/blood_choice", methods=["POST"])
def blood_choice():
    lang = request.args.get("lang", "en-IN")
    digit = request.form.get("Digits")
    call_sid = request.form.get("CallSid")

    blood_map = {
        "1": "A+",
        "2": "A-",
        "3": "B+",
        "4": "B-",
        "5": "O+",
        "6": "O-",
        "7": "AB+",
        "8": "AB-"
    }
    blood = blood_map.get(digit, "Unknown")
    call_data[call_sid] = call_data.get(call_sid, {})
    call_data[call_sid]["BloodGroup"] = blood
    print(f"✅ Blood group received: {blood}")

    response = VoiceResponse()
    response.redirect(f"/register?lang={lang}&step=hospital", method="POST")
    return str(response)

@app.route("/process_recording", methods=["POST"])
def process_recording():
    lang = request.args.get("lang", "en-IN")
    step = request.args.get("step", "name")
    call_sid = request.form.get("CallSid")
    recording_url = request.form.get("RecordingUrl") + ".mp3"

    if not call_sid or not recording_url:
        return "Missing data", 400

    os.makedirs("recordings", exist_ok=True)
    filename_mp3 = f"{call_sid}_{step}.mp3"
    filepath_mp3 = os.path.join("recordings", filename_mp3)

    try:
        audio_data = requests.get(recording_url, auth=(TWILIO_SID, TWILIO_AUTH))
        with open(filepath_mp3, "wb") as f:
            f.write(audio_data.content)
    except Exception as e:
        print(f"⚠️ Error downloading audio from Twilio: {e}")
        return f"Download error: {e}", 500

    if not os.path.exists(filepath_mp3):
        print(f"⚠️ Recording file not found at path: {filepath_mp3}")
        return "Recording not found", 500

    # Create a new WAV file path for transcription
    filename_wav = f"{call_sid}_{step}.wav"
    filepath_wav = os.path.join("recordings", filename_wav)

    try:
        # Use the FFMPEG_PATH directly, as it already contains the full executable path
        ffmpeg_executable = FFMPEG_PATH 
        
        if not ffmpeg_executable or not os.path.exists(ffmpeg_executable):
            print(f"❌ CRITICAL ERROR: ffmpeg executable not found at '{ffmpeg_executable}'. Please ensure FFMPEG_PATH in your .env is correct and points directly to ffmpeg.exe.")
            return "ffmpeg not found", 500 # Return 500 as this is a critical setup error

        # Use ffmpeg to convert the downloaded mp3 to a wav file
        print(f"▶️ Converting {filepath_mp3} to {filepath_wav} using '{ffmpeg_executable}'...")
        subprocess.run(
            [ffmpeg_executable, "-i", filepath_mp3, "-acodec", "pcm_s16le", "-ar", "16000", filepath_wav],
            check=True,
            capture_output=True,
            text=True
        )
        print("✅ Conversion successful.")
    except subprocess.CalledProcessError as e:
        print(f"❌ ffmpeg conversion failed. Error: {e.stderr}")
        return "Audio conversion error", 500
    except Exception as e: # Catch any other exceptions during subprocess run
        print(f"❌ An unexpected error occurred during ffmpeg conversion: {e}")
        return "Audio conversion error", 500


    # Map the application language codes to Whisper's language codes
    # For Telugu (te-IN), we will now use 'en' for transcription as per your strategy
    lang_map_whisper = {
        "en-IN": "en",
        "hi-IN": "hi",
        "te-IN": "en" # Corrected to 'en' for Romanized Telugu transcription
    }
    whisper_lang = lang_map_whisper.get(lang, "en")

    try:
        print(f"▶️ Starting transcription for WAV file: {filepath_wav} with language: {whisper_lang}")
        # Use the converted WAV file for transcription
        result = model.transcribe(filepath_wav, language=whisper_lang)
        text = result["text"].strip()
        print(f"✅ Transcription successful: '{text}'")
    except Exception as e:
        print(f"❌ Whisper transcription failed with error: {e}")
        return f"Whisper error: {e}", 500

    if call_sid not in call_data:
        call_data[call_sid] = {"CallSID": call_sid}

    field_map = {
        "name": "Name",
        "hospital": "Hospital"
    }
    if step in field_map:
        call_data[call_sid][field_map[step]] = text

    steps = ["name", "phone", "blood", "hospital"]

    if step == "hospital":
        row = [
            call_data[call_sid].get("CallSID", ""),
            call_data[call_sid].get("Name", ""),
            call_data[call_sid].get("Phone", ""),
            call_data[call_sid].get("BloodGroup", ""),
            call_data[call_sid].get("Hospital", "")
        ]
        try:
            sheet.append_row(row)
        except Exception as e:
            return f"Sheet write error: {e}", 500

        try:
            patient_blood = call_data[call_sid].get("BloodGroup", "").strip().upper()
            patient_phone = call_data[call_sid].get("Phone", "")
            patient_hospital = call_data[call_sid].get("Hospital", "")
            patient_name = call_data[call_sid].get("Name", "")

            donors = donor_sheet.get_all_records()
            matching_donors = [d for d in donors if d["BloodGroup"].strip().upper() == patient_blood]

            print(f"\n📢 Found {len(matching_donors)} matched donors for blood group {patient_blood}.")
            
            # This is the new SMS sending logic
            for donor in matching_donors:
                donor_phone = donor.get("DonorPhone")
                if donor_phone:
                    # Convert donor_phone to a string to ensure len() and concatenation work correctly.
                    # Also, format the phone number to E.164 standard (+91) if it's a 10-digit number.
                    donor_phone_str = str(donor_phone)
                    e164_donor_phone = "+91" + donor_phone_str if len(donor_phone_str) == 10 else donor_phone_str

                    message_body = (
                        f"Urgent: Blood donation request for {patient_blood} at {patient_hospital}. "
                        f"Patient Name: {patient_name}. " # Include patient name
                        f"Please contact {patient_phone} for details and to assist."
                    )
                    try:
                        message = twilio_client.messages.create(
                            body=message_body,
                            from_=TWILIO_PHONE_NUMBER,
                            to=e164_donor_phone
                        )
                        print(f"✅ SMS sent to {donor.get('DonorName')} at {donor_phone}. SID: {message.sid}")
                    except Exception as sms_e:
                        print(f"❌ Failed to send SMS to {donor.get('DonorName')} at {donor_phone}. Error: {sms_e}")

        except Exception as e:
            print("⚠️ Donor Matching or SMS Error:", e)

        response = VoiceResponse()
        response.say("Thank you. Your details are recorded and an alert has been sent to potential donors. Goodbye!", language=lang)
        response.hangup()
        return str(response)

    next_step = steps[steps.index(step) + 1]
    response = VoiceResponse()
    response.redirect(f"/register?lang={lang}&step={next_step}", method="POST")
    return str(response)

if __name__ == "__main__":
    app.run(debug=True)
