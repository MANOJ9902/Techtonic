from flask import Flask, render_template, request, jsonify
import openai
import speech_recognition as sr
import pyttsx3
from deep_translator import GoogleTranslator
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
from langchain_openai import ChatOpenAI
import logging
import google.generativeai as genai
from PIL import Image

# Initialize logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)

# Replace 'your_openai_api_key' with your actual OpenAI API key
openai.api_key = 'sk-proj-74nl78OByS2CNvepXP1RT3BlbkFJrchUmV0pF6qkRd6vCnM7'

# Manually assign the API key (replace with your actual API key)
GOOGLE_API_KEY = "AIzaSyDmJCH8sJZiVxZ6-nYkycKMsrgjPJx2xbk"
genai.configure(api_key=GOOGLE_API_KEY)

class ChatBot:
    def __init__(self):
        self.input_prompt = """
            Welcome to the Pet Care ChatBot. Ask any questions related to pet care and pets!
            """
        self.memory = ConversationBufferMemory()
        self.openai_llm = ChatOpenAI(api_key=openai.api_key)
        self.conversation_chain = ConversationChain(llm=self.openai_llm, memory=self.memory)
        self.recognizer = sr.Recognizer()
        self.tts_engine = pyttsx3.init()

    def translate_text(self, text, target_language):
        translated_text = GoogleTranslator(source='auto', target=target_language).translate(text)
        return translated_text

    def chat(self, msg, target_lang='en'):
        logging.debug(f"Original message: {msg}")
        if target_lang != 'en':
            msg = self.translate_text(msg, 'en')  # Translate to English for processing
            logging.debug(f"Translated message to English: {msg}")

        response = self.invoke(input=self.input_prompt + "\n" + msg)
        logging.debug(f"Response from OpenAI: {response}")

        if target_lang != 'en':
            response['response'] = self.translate_text(response['response'], target_lang)  # Translate response back to target language
            logging.debug(f"Translated response to target language: {response['response']}")

        return jsonify(response)

    def invoke(self, input):
        response = self.conversation_chain.invoke(input=input)
        return response

    def voice_to_text(self):
        with sr.Microphone() as source:
            logging.info("Listening...")
            audio = self.recognizer.listen(source)
            try:
                text = self.recognizer.recognize_google(audio)
                logging.info(f"Recognized text: {text}")
                return text
            except sr.UnknownValueError:
                logging.error("Google Speech Recognition could not understand the audio")
            except sr.RequestError as e:
                logging.error(f"Could not request results from Google Speech Recognition service; {e}")
        return None

    def text_to_speech(self, text):
        self.tts_engine.say(text)
        self.tts_engine.runAndWait()

# Initialize ChatBot instance
chatbot = ChatBot()

# Function to load Google Gemini Pro Vision API And get response
def get_gemini_response(input_text, image_parts, prompt):
    model = genai.GenerativeModel('gemini-pro-vision')
    response = model.generate_content([input_text, image_parts[0], prompt])
    return response.text

def input_image_setup(file_storage):
    if file_storage is not None:
        # Read the file into bytes
        bytes_data = file_storage.read()

        image_parts = [
            {
                "mime_type": file_storage.content_type,
                "data": bytes_data
            }
        ]
        return image_parts
    else:
        raise FileNotFoundError("No file uploaded")

@app.route("/")
def home():
    return render_template('index.html')

@app.route("/get", methods=["POST"])
def chat():
    msg = request.form["msg"]
    target_lang = request.form.get("lang", "en")  # Default to English if lang parameter is not provided
    response = chatbot.chat(msg, target_lang)
    return response

@app.route("/voice", methods=["POST"])
def voice():
    text = chatbot.voice_to_text()
    if text:
        target_lang = request.form.get("lang", "en")  # Default to English if lang parameter is not provided
        response = chatbot.chat(text, target_lang)
        chatbot.text_to_speech(response.get_json()["response"])
        return response
    else:
        return jsonify({"response": "Could not understand audio."})

@app.route('/chatbot', methods=['GET', 'POST'])
def chatbot_interface():
    if request.method == 'POST':
        if request.form['submit_button'] == 'Text Input':
            msg = request.form['msg']
            target_lang = request.form.get('lang', 'en')  # Default to English if lang parameter is not provided
            response = chatbot.chat(msg, target_lang)
            return render_template('chat.html', response=response)
        elif request.form['submit_button'] == 'Voice Input':
            # Perform voice input processing
            return render_template('voice.html')
    else:
        return render_template('chat.html')

@app.route("/about")
def about():
    return render_template('about.html')

@app.route("/contact")
def contact():
    return render_template('contact.html')
@app.route('/disease', methods=['GET', 'POST'])
def disease():
    # Handle POST request to process form data
    if request.method == 'POST':
        input_text = request.form['input']
        uploaded_file = request.files['file']

        if uploaded_file:
            image_parts = input_image_setup(uploaded_file)
            prompt = """
            You are an expert in health management where you need to identify the symptoms of pet diseases from the provided description or image and provide detailed information on the disease, its causes, prevention measures, and recommend appropriate medications if necessary.

            Your response should be in the following format:

            1. Disease Name:
               - Symptoms:
               - Causes:
               - Prevention Measures:
               - Recommended Medications (if applicable):

            Please provide comprehensive information to assist users in understanding and managing their health effectively. You should not answer questions other than health topics, and you should mention a disclaimer at the end of the answers/context that you are not an expert. Please ensure to connect with a health professional.
            """
            response = get_gemini_response(input_text, image_parts, prompt)

            target_lang = request.form.get("lang", "en")  # Default to English if lang parameter is not provided
            if target_lang != 'en':
                response = chatbot.translate_text(response, target_lang)

        return render_template('disease.html', response=response)

    # Handle GET request to render the initial form
    return render_template('disease.html')

if __name__ == '__main__':
    app.run(debug=True, port=8000)
