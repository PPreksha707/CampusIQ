
from flask import Flask, render_template, request
import fitz
import os
import re
import io

from dotenv import load_dotenv
from google import genai
from deep_translator import GoogleTranslator
import pytesseract
from PIL import Image

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)


# 1. Simplify college notice using Gemini

def simplify_notice(text):

    prompt = f"""
    You are CampusIQ, an assistant that helps college students
    understand college notices.

    Simplify the following notice using easy English.

    Instructions:
    1. Use simple words and short sentences.
    2. Keep all dates, deadlines and important details unchanged.
    3. Do not remove important instructions.
    4. Do not add information that is not in the original notice.
    5. Make the explanation easy for students to understand.

    Original Notice:
    {text}
    """

    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt
    )

    return response.text


# 2. Extract important dates and sentences

def extract_important_info(text):

    date_pattern = r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b'

    dates = re.findall(date_pattern, text)

    keywords = [
        "deadline",
        "last date",
        "submission",
        "exam",
        "examination",
        "registration",
        "application",
        "important"
    ]

    important_sentences = []

    sentences = re.split(r'[.!?\n]', text)

    for sentence in sentences:
        if any(word in sentence.lower() for word in keywords):
            if sentence.strip():
                important_sentences.append(sentence.strip())

    return dates, important_sentences


# 3. Translate notice

def translate_notice(text, language):

    translator = GoogleTranslator(
        source='auto',
        target=language
    )

    translated_text = translator.translate(text[:4000])

    return translated_text


# 4. Extract text using OCR

def extract_text_with_ocr(pdf_document):

    ocr_text = ""

    for page in pdf_document:

        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))

        image = Image.open(
            io.BytesIO(pix.tobytes("png"))
        )

        page_text = pytesseract.image_to_string(image)

        ocr_text += page_text + "\n"

    return ocr_text


# 5. Classify notice

def classify_notice(text):

    text = text.lower()

    categories = {
        "Examination": ["exam", "examination", "timetable", "hall ticket"],
        "Events": ["event", "fest", "workshop", "seminar"],
        "Fees": ["fee", "payment", "scholarship", "receipt"],
        "Registration": ["registration", "admission", "application", "enrollment"]
    }

    for category, keywords in categories.items():
        if any(keyword in text for keyword in keywords):
            return category

    return "General Announcement"


# 6. Extract important details

def extract_details(text):

    details = []

    keywords = [
        "fee",
        "amount",
        "deadline",
        "last date",
        "eligibility",
        "documents required",
        "submit",
        "venue",
        "time",
        "reporting"
    ]

    sentences = re.split(r'[.!?\n]', text)

    for sentence in sentences:
        if any(word in sentence.lower() for word in keywords):
            if sentence.strip():
                details.append(sentence.strip())

    return details


# Flask application

app = Flask(__name__)


# Home page

@app.route("/")
def home():

    return render_template("index.html")


# Upload and process notice

@app.route("/upload", methods=["POST"])
def upload():

    if "notice" not in request.files:
        return "No file selected"

    file = request.files["notice"]

    if file.filename == "":
        return "Please select a file"

    if not file.filename.lower().endswith(".pdf"):
        return "Please upload a PDF file"

    pdf_document = fitz.open(
        stream=file.read(),
        filetype="pdf"
    )

    extracted_text = ""

    for page in pdf_document:
        extracted_text += page.get_text()

    # Use OCR if PDF has no selectable text

    if not extracted_text.strip():
        extracted_text = extract_text_with_ocr(pdf_document)

    pdf_document.close()

    if not extracted_text.strip():
        return "Could not extract text from this PDF. Please try another file."

    # AI simplification

    try:
        simplified_text = simplify_notice(extracted_text)

    except Exception as e:
        print("Gemini Error:", e)

        simplified_text = (
            "AI simplification is temporarily unavailable. "
            "Please try again later."
        )

    # Extract dates and important sentences

    dates, important_sentences = extract_important_info(extracted_text)

    # Classify notice

    notice_category = classify_notice(extracted_text)

    # Extract important details

    important_details = extract_details(extracted_text)

    # Translation

    language = request.form.get("language", "English")

    language_codes = {
        "English": "en",
        "Hindi": "hi",
        "Marathi": "mr"
    }

    translated_text = None

    if language in language_codes and language != "English":

        try:
            translated_text = translate_notice(
                extracted_text,
                language_codes[language]
            )

        except Exception as e:
            print("Translation Error:", e)
            translated_text = "Translation is temporarily unavailable."

    # Display results

    return render_template(
        "result.html",
        extracted_text=extracted_text,
        simplified_text=simplified_text,
        dates=dates,
        important_sentences=important_sentences,
        translated_text=translated_text,
        notice_category=notice_category,
        important_details=important_details
    )


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
