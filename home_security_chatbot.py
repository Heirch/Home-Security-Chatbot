from chatterbot import ChatBot
from chatterbot.trainers import ListTrainer
from flask import Flask, request, render_template, jsonify
import requests
import random
import re
import os
import smtplib
from email.mime.text import MIMEText
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Initialize ChatBot with SQLite storage
chatbot = ChatBot(
    'SecurityBot',
    storage_adapter='chatterbot.storage.SQLStorageAdapter',
    database_uri='sqlite:///security_bot.db'
)

# Mock home security system data with multiple zones
security_data = {
    "system_status": "Disarmed",
    "zones": {
        "living_room": {"status": "Closed", "motion": "None", "alert": None},
        "kitchen": {"status": "Closed", "motion": "None", "alert": None},
        "bedroom": {"status": "Closed", "motion": "None", "alert": None},
        "hallway": {"status": "Closed", "motion": "None", "alert": None}
    },
    "camera_status": "Online",
    "alerts": []
}

# EMAIL_CONFIG_FILE
EMAIL_CONFIG_FILE = 'email_config.json'

# Load or initialize email configuration
def load_email_config():
    if os.path.exists(EMAIL_CONFIG_FILE):
        with open(EMAIL_CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {"recipient_email": "recipient_email@gmail.com"}  # Default fallback

def save_email_config(email):
    config = {"recipient_email": email}
    with open(EMAIL_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
    print(f"Saved email config: {email}")

# Send email alert for security events
def send_alert_email(message):
    sender = "secureurhome69@gmail.com"  # Replace with your email
    config = load_email_config()
    receiver = config["recipient_email"]
    password = "hukq ssdc voxm ifvs"  # Replace with your Gmail App Password
    msg = MIMEText(message)
    msg['Subject'] = 'Home Security Alert'
    msg['From'] = sender
    msg['To'] = receiver
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())
        print(f"Alert email sent successfully to {receiver}")
    except Exception as e:
        print(f"Failed to send alert email: {str(e)}")

# Mock API endpoint for security status
@app.route('/api/security_status', methods=['GET'])
def get_security_status():
    # Simulate dynamic status for multiple zones
    zones = security_data["zones"]
    for zone in zones:
        zones[zone]["motion"] = random.choice(["None", "Detected"])
        if zones[zone]["motion"] == "Detected":
            zones[zone]["alert"] = f"Motion detected in {zone}!"
            security_data["alerts"].append(zones[zone]["alert"])
    if security_data["alerts"]:
        send_alert_email("\n".join(security_data["alerts"]))
    return {
        "system_status": security_data["system_status"],
        "zones": {k: v for k, v in zones.items()},
        "camera_status": security_data["camera_status"],
        "alert_status": security_data["alerts"] if security_data["alerts"] else ["All clear!"]
    }

# Endpoint to register email
@app.route('/register_email', methods=['POST'])
def register_email():
    email = request.form.get('email', '').strip()
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        return jsonify({"response": "Error: Invalid email format. Please enter a valid email."})
    save_email_config(email)
    return jsonify({"response": f"Email registered successfully: {email}"})

# OpenWeatherMap API integration
def get_weather(city, api_key="63f5a78aa9a5276c805a4c1e1328320d"):
    api_key = api_key or os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        error_msg = "Error: OpenWeatherMap API key not set. Please set OPENWEATHER_API_KEY."
        print(error_msg)
        return error_msg
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    try:
        print(f"Weather API request for {city}: URL={url.replace(api_key, 'HIDDEN')}")
        response = requests.get(url).json()
        print(f"Weather API response for {city}: {response}")
        if response.get("cod") == 200:
            weather = response["weather"][0]["description"]
            temp = response["main"]["temp"]
            return f"Current weather in {city}: {weather}, {temp}°C."
        else:
            error_msg = f"Error: Could not fetch weather for {city}. API response: {response.get('message', 'Unknown error')}"
            print(error_msg)
            return error_msg
    except requests.RequestException as e:
        error_msg = f"Error: Network issue while fetching weather for {city}: {str(e)}"
        print(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"Error: Failed to fetch weather for {city}: {str(e)}"
        print(error_msg)
        return error_msg

# Handle weather queries with state name detection
def handle_weather_query(user_input, user_context):
    state_to_city = {
        "punjab": "Try 'Weather in Amritsar' or 'Weather in Chandigarh'.",
        "bihar": "Try 'Weather in Patna'.",
    }
    weather_patterns = [
        r"weather in\s+([\w\s,]+?)(?:\?|$)",
        r"what's the weather in\s+([\w\s,]+?)(?:\?|$)",
        r"what is the weather in\s+([\w\s,]+?)(?:\?|$)",
        r"weather\s+([\w\s,]+?)(?:\?|$)"
    ]
    for pattern in weather_patterns:
        match = re.search(pattern, user_input.lower(), re.IGNORECASE)
        if match:
            city = match.group(1).strip().title()
            user_context["city"] = city
            print(f"Detected weather query: city={city}")
            if city.lower() in state_to_city:
                return f"{city} is a state. {state_to_city[city.lower()]}"
            weather_status = get_weather(city)
            return f"Fetching weather for {city}... {weather_status}"
    if "weather" in user_input.lower():
        print(f"Weather query without valid city: {user_input}")
        return "Please specify a valid city, e.g., 'Weather in London'."
    return None

# Conversation pairs
conversation = [
    # Greetings and Personalization
    "Hi", "Hello! I'm your Home Security Assistant. What's your name?",
    "Hello", "Hey there! Ready to check your home security? What's your name?",
    "Hey", "Yo! Ready to secure your home? What's your name?",
    "My name is {name}", "Nice to meet you, {name}! How can I help secure your home today?",
    "{name}", "Nice to meet you, {name}! How can I help secure your home today?",
    "I can’t share my name", "No worries, friend! How can I help with your home security?",
    "No I can’t share my name", "No problem, friend! How can I help with your home security?",

    # Email Registration
    "Register email {email}", "Registering email... {email_status}",

    # System Status Checks
    "Check security status", "Let me check... {api_status}",
    "Is my house secure?", "Checking the system... {api_status}",
    "Are the doors locked?", "Let me verify... {door_status}",
    "Any motion detected?", "Scanning sensors... {motion_status}",
    "Camera status", "Checking cameras... {camera_status}",

    # Control Commands
    "Arm the system", "System armed! Your home is now secure.",
    "Disarm the system", "System disarmed. Stay safe!",
    "Turn on cameras", "Cameras activated. Monitoring in progress.",
    "Turn off cameras", "Cameras deactivated. Privacy mode enabled.",

    # Alerts and Notifications
    "Any alerts?", "Checking for alerts... {alert_status}",
    "Is there a problem?", "Let me see... {alert_status}",
    "Notify me", "I'll alert you if anything unusual happens. What's your preferred city for weather updates?",

    # Generic Responses
    "Yes", "Got it! Anything specific about your security system I should check?",
    "No", "Alright, let me know what you need help with!",
    "Ok", "Cool, what's next? Want to check the security status or something else?",
    "Okay", "All good! What's on your mind?",

    # Small Talk and Security Tips
    "How are you?", "I'm on guard, keeping your home safe! How about you?",
    "Tell me a security tip", "Always double-check your door locks at night and consider motion-sensor lights for extra protection!",
    "What can you do?", "I can check your security system, arm/disarm it, monitor cameras, give weather updates, or register an email for alerts. Try me!",
    "Are you a real guard?", "Nope, I'm a digital sentinel, but I'm just as vigilant! What's on your mind?",

    # Handling Confusion
    "What?", "Oops, did I miss something? Ask about your security system or try 'check status'!",
    "I don’t understand", "No worries, let’s try again. Want to check your home’s security or get a tip?",
    "Huh?", "Haha, my sensors might’ve glitched! Ask about doors, cameras, or alerts.",
    "I can't share my name", "No worries, friend! How can I help with your home security?",

    # New Conversation Pairs
    "What’s the temperature?", "I can check the weather! Tell me a city.",
    "Help me secure my home", "Great idea! Try arming the system or adding motion lights.",
    "Can you call the police?", "I’m digital, but I can send an alert! Register an email first.",
    "Is it safe outside?", "Let’s check the weather—tell me your city for a clue!",
    "How do I lock the doors?", "Use the 'Arm the system' command to secure everything.",
    "What’s a good password?", "Use a mix of letters, numbers, and symbols—change it often!",
    "Can you turn on lights?", "Not yet, but arming the system adds extra security!",
    "Is my camera working?", "Check with 'Camera status'—it should say Online!",
    "What if I’m away?", "Arm the system and register an email for alerts while you’re gone.",
    "Can you detect fire?", "I can’t yet, but motion detection is active—stay safe!",
    "Tell me about weather", "Sure, try 'Weather in [city]' to get the latest update!",
    "How’s my system?", "Let me check... {api_status}",
    "What’s new?", "I’ve got weather updates and email alerts now—try me out!",
    "Can you learn?", "I’m getting smarter with every chat—keep talking to me!",
    "Is the house quiet?", "Checking motion... {motion_status}",
    "What’s my status?", "Your security status is... {api_status}",
    "Give me advice", "Install a doorbell camera for extra peace of mind!",
    "Can you remind me?", "I’ll alert you via email if motion is detected—register one!",
    "What’s next?", "How about checking the security status or weather?",
    "Thanks!", "You’re welcome, {name}! Stay secure!"
]

# Train the chatbot
trainer = ListTrainer(chatbot)
trainer.train(conversation)

# Store user context and conversation history
user_context = {"name": "", "city": ""}
conversation_history = []  # List to store (input, response) pairs

# Process chatbot response with API data, personalization, and memory
def process_response(user_input):
    print(f"Processing input: {user_input}")

    # Handle weather queries first
    weather_response = handle_weather_query(user_input, user_context)
    if weather_response:
        print(f"Input: {user_input}, Response: {weather_response}")
        conversation_history.append((user_input, weather_response))
        return weather_response

    # Handle email registration via chat
    email_status = ""
    email_match = re.match(r"register email\s+([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", user_input.lower(), re.IGNORECASE)
    if email_match:
        email = email_match.group(1)
        save_email_config(email)
        email_status = f"Email registered successfully: {email}"
        conversation_history.append((user_input, email_status))
        return email_status

    # Fetch security status from mock API
    try:
        api_response = requests.get("http://127.0.0.1:5000/api/security_status").json()
        zones_status = {k: v["motion"] for k, v in api_response["zones"].items()}
        api_status = (f"System: {api_response['system_status']}, Zones: {', '.join([f'{k}: {v}' for k, v in zones_status.items()])}"
                      f", Cameras: {api_response['camera_status']}")
    except Exception as e:
        print(f"Mock API error: {str(e)}")
        api_status = "Unable to fetch status."

    # Handle name personalization
    if "my name is" in user_input.lower():
        match = re.search(r"my name is\s+([a-zA-Z]+)", user_input.lower(), re.IGNORECASE)
        if match:
            name = match.group(1).capitalize()
            user_context["name"] = name
            print(f"Detected name: {name}")
    elif re.search(r"(i\s*(can'?t|cannot)\s*share\s*my\s*name)", user_input.lower(), re.IGNORECASE):
        user_context["name"] = "friend"
        print(f"Detected name refusal")
        return "No problem, friend! How can I help with your home security?"
    elif (re.match(r"^[a-zA-Z]+$", user_input.strip(), re.IGNORECASE) and
          user_input.strip().lower() not in ["yes", "no", "ok", "okay", "hi", "hello", "what", "huh", "weather"]):
        name = user_input.strip().capitalize()
        user_context["name"] = name
        print(f"Detected single-word name: {name}")
        return f"Nice to meet you, {name}! How can I help secure your home today?"

    # Get chatbot response
    response = str(chatbot.get_response(user_input))

    # Add to conversation history
    full_response = response
    conversation_history.append((user_input, response))

    # Occasionally recall a past input for a natural chat feel
    if random.random() < 0.3 and len(conversation_history) > 1:  # 30% chance to recall
        past_input, past_response = random.choice(conversation_history[:-1])  # Avoid current input
        full_response = f"{response} Oh, by the way, you asked '{past_input}' earlier, and I said '{past_response}'. Anything else?"

    # Replace placeholders with API data and user context
    full_response = full_response.replace("{api_status}", api_status)
    full_response = full_response.replace("{motion_status}", ", ".join([v["motion"] for v in security_data["zones"].values()]))
    full_response = full_response.replace("{camera_status}", security_data["camera_status"])
    full_response = full_response.replace("{alert_status}", ", ".join(api_response["alert_status"]))
    full_response = full_response.replace("{email_status}", email_status)
    full_response = full_response.replace("{name}", user_context["name"] or "friend")
    full_response = full_response.replace("{city}", user_context["city"] or "your city")

    print(f"Input: {user_input}, Response: {full_response}")
    return full_response

# Flask routes for web interface
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.form['message']
    response = process_response(user_input)
    return {"response": response}

@app.route('/toggle_dark_mode', methods=['POST'])
def toggle_dark_mode():
    mode = request.form.get('mode', 'light')
    return jsonify({"status": "success", "mode": mode})

if __name__ == '__main__':
    app.run(debug=True)
"""
#from chatterbot import ChatBot
# from chatterbot.trainers import ListTrainer
# from flask import Flask, request, render_template, jsonify
# import requests
# import random
# import re
# import os
# import smtplib
# from email.mime.text import MIMEText
# import json
# from dotenv import load_dotenv

# # Load environment variables
# load_dotenv()

# # Initialize Flask app
# app = Flask(__name__)

# # Initialize ChatBot with SQLite storage
# chatbot = ChatBot(
#     'SecurityBot',
#     storage_adapter='chatterbot.storage.SQLStorageAdapter',
#     database_uri='sqlite:///security_bot.db'
# )

# # Mock home security system data
# security_data = {
#     "system_status": "Disarmed",
#     "door_status": "Closed",
#     "motion_status": "None",
#     "camera_status": "Online",
#     "alerts": []
# }

# # Email configuration file
# EMAIL_CONFIG_FILE = 'email_config.json'

# # Load or initialize email configuration
# def load_email_config():
#     if os.path.exists(EMAIL_CONFIG_FILE):
#         with open(EMAIL_CONFIG_FILE, 'r') as f:
#             return json.load(f)
#     return {"recipient_email": "recipient_email@gmail.com"}  # Default fallback

# def save_email_config(email):
#     config = {"recipient_email": email}
#     with open(EMAIL_CONFIG_FILE, 'w') as f:
#         json.dump(config, f, indent=4)
#     print(f"Saved email config: {email}")

# # Send email alert for security events
# def send_alert_email(message):
#     sender = "secureurhome69@gmail.com"  # Replace with your email
#     config = load_email_config()
#     receiver = config["recipient_email"]
#     password = "hukq ssdc voxm ifvs"  # Replace with your Gmail App Password
#     msg = MIMEText(message)
#     msg['Subject'] = 'Home Security Alert'
#     msg['From'] = sender
#     msg['To'] = receiver
#     try:
#         with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
#             server.login(sender, password)
#             server.sendmail(sender, receiver, msg.as_string())
#         print(f"Alert email sent successfully to {receiver}")
#     except Exception as e:
#         print(f"Failed to send alert email: {str(e)}")

# # Mock API endpoint for security status
# @app.route('/api/security_status', methods=['GET'])
# def get_security_status():
#     # Simulate dynamic status
#     security_data["motion_status"] = random.choice(["None", "Detected"])
#     security_data["alerts"] = ["Motion detected in living room!"] if security_data["motion_status"] == "Detected" else []
#     app.run(debug=True)
"""