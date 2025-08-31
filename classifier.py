import joblib
import re
from nltk.corpus import stopwords
from pathlib import Path
from langdetect import detect
from deep_translator import GoogleTranslator

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "classifier.joblib"
VEC_PATH = BASE_DIR / "vectorizer.joblib"

clf = joblib.load(MODEL_PATH)
vectorizer = joblib.load(VEC_PATH)

stop_words = set(stopwords.words('english'))

CATEGORY_KEYWORDS = {
    "xenophobia": ["immigrants", "go back", "deport", "illegal alien", "invasion", "anchor baby"],
    "racism": ["white power", "black people", "slur", "ape", "nazi", "klan", "jews"],
    "misogyny": ["feminazi", "bitches", "women should", "kitchen", "slut"],
    "homophobia": ["gay agenda", "burn them", "faggot", "lesbo", "abomination"],
    "general hate": ["kill", "burn", "lynch", "hang", "die", "terrorist", "rape", "muslims"]
}


def clean_text(text):
    text = text.lower()
    text = re.sub(r"http\S+|www\S+|https\S+", '', text)
    text = re.sub(r'\W', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return ' '.join([word for word in text.split() if word not in stop_words])


def detect_language_and_translate(text):
    try:
        lang = detect(text)
        if lang != "en":
            text = GoogleTranslator(source='auto', target='en').translate(text)
        return text
    except:
        return text  # fallback


def classify_text(text):
    original_text = text
    text = detect_language_and_translate(text)
    cleaned = clean_text(text)

    matched_categories = []
    matched_keywords = []

    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in cleaned:
                matched_categories.append(category)
                matched_keywords.append(kw)

    is_hate = bool(matched_categories)
    confidence = 0.9 if is_hate else 0.0

    return {
        "is_hate_speech": is_hate,
        "confidence": confidence,
        "category": matched_categories[0] if matched_categories else None,
        "explanation": f"Keyword(s) matched: {', '.join(set(matched_keywords))}" if matched_keywords else None,
        "original_language": detect(original_text) if original_text != text else "en"
    }
