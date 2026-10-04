import pandas as pd
import os
import joblib

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(
    BASE_DIR,
    "backend",
    "data"
)

MODEL_DIR = os.path.join(
    BASE_DIR,
    "backend",
    "models"
)

os.makedirs(MODEL_DIR, exist_ok=True)

INPUT_FILE = os.path.join(
    DATA_DIR,
    "cleaned_feedback.csv"
)


df = pd.read_csv(INPUT_FILE)

X = df["cleaned_text"]

y = df["sentiment"]


X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)


vectorizer = TfidfVectorizer(
    max_features=5000,
    ngram_range=(1, 2),
    stop_words="english"
)


X_train_tfidf = vectorizer.fit_transform(
    X_train
)

X_test_tfidf = vectorizer.transform(
    X_test
)


model = LogisticRegression(
    max_iter=1000
)


model.fit(
    X_train_tfidf,
    y_train
)


predictions = model.predict(
    X_test_tfidf
)


accuracy = accuracy_score(
    y_test,
    predictions
)


print("\n======================================")
print("SENTIMENT ANALYSIS")
print("======================================")

print(
    f"\nModel Accuracy: {accuracy * 100:.2f}%\n"
)

print(
    classification_report(
        y_test,
        predictions
    )
)


joblib.dump(
    model,
    os.path.join(
        MODEL_DIR,
        "sentiment_model.pkl"
    )
)


joblib.dump(
    vectorizer,
    os.path.join(
        MODEL_DIR,
        "sentiment_vectorizer.pkl"
    )
)


print("Model saved successfully.")