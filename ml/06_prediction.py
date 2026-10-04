import pandas as pd
import os
import joblib


BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

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

INPUT_FILE = os.path.join(
    DATA_DIR,
    "topic_feedback.csv"
)

MODEL_FILE = os.path.join(
    MODEL_DIR,
    "sentiment_model.pkl"
)

VECTORIZER_FILE = os.path.join(
    MODEL_DIR,
    "sentiment_vectorizer.pkl"
)


df = pd.read_csv(
    INPUT_FILE
)


model = joblib.load(
    MODEL_FILE
)

vectorizer = joblib.load(
    VECTORIZER_FILE
)


X = vectorizer.transform(
    df["cleaned_text"]
)


df["predicted_sentiment"] = model.predict(
    X
)


OUTPUT_FILE = os.path.join(
    DATA_DIR,
    "final_feedback_analysis.csv"
)


df.to_csv(
    OUTPUT_FILE,
    index=False
)


print("\n======================================")
print("PREDICTIVE ANALYTICS")
print("======================================\n")


print(
    "Predicted sentiment distribution:"
)

print(
    df["predicted_sentiment"].value_counts()
)


print(
    "\nFinal analysis saved:"
)

print(
    OUTPUT_FILE
)