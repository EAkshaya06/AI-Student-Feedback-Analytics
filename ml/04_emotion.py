import pandas as pd
import os


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(
    BASE_DIR,
    "backend",
    "data"
)

INPUT_FILE = os.path.join(
    DATA_DIR,
    "cleaned_feedback.csv"
)

OUTPUT_FILE = os.path.join(
    DATA_DIR,
    "emotion_feedback.csv"
)


emotion_keywords = {

    "Joy": [
        "good",
        "great",
        "excellent",
        "happy",
        "satisfied",
        "helpful",
        "amazing",
        "best",
        "love",
        "wonderful"
    ],

    "Frustration": [
        "bad",
        "poor",
        "worst",
        "difficult",
        "problem",
        "issue",
        "slow",
        "disappointed",
        "unhappy",
        "boring"
    ],

    "Confusion": [
        "confused",
        "unclear",
        "understand",
        "doubt",
        "complicated",
        "explain",
        "difficult",
        "clarity"
    ],

    "Excitement": [
        "interesting",
        "exciting",
        "enjoy",
        "fun",
        "innovative",
        "useful",
        "interesting"
    ]
}


def detect_emotion(text):

    text = str(text).lower()

    scores = {}

    for emotion, words in emotion_keywords.items():

        scores[emotion] = sum(
            1
            for word in words
            if word in text
        )

    best_emotion = max(
        scores,
        key=scores.get
    )

    if scores[best_emotion] == 0:

        return "Neutral"

    return best_emotion


df = pd.read_csv(
    INPUT_FILE
)


df["emotion"] = df[
    "cleaned_text"
].apply(
    detect_emotion
)


df.to_csv(
    OUTPUT_FILE,
    index=False
)


print("\n======================================")
print("EMOTION DETECTION")
print("======================================\n")

print(
    df["emotion"].value_counts()
)

print(
    "\nSaved:",
    OUTPUT_FILE
)