import pandas as pd
import re
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "backend", "data")

INPUT_FILE = os.path.join(DATA_DIR, "feedback.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "cleaned_feedback.csv")


def clean_text(text):
    text = str(text).lower()
    text = re.sub(r"http\S+|www\S+", "", text)
    text = re.sub(r"[^a-zA-Z\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


print("\n======================================")
print("AI STUDENT FEEDBACK ANALYTICS")
print("DATA CLEANING")
print("======================================\n")

df = pd.read_csv(INPUT_FILE)

print("Original records:", len(df))
print("Original columns:", list(df.columns))

# Remove duplicate feedback
before = len(df)
df = df.drop_duplicates(subset=["text"])
print("Duplicates removed:", before - len(df))

# Handle missing values
df["text"] = df["text"].fillna("").astype(str)
df["category"] = df["category"].fillna("unknown").astype(str)
df["sentiment"] = df["sentiment"].fillna("neutral").astype(str)

df["sentiment_score"] = pd.to_numeric(
    df["sentiment_score"],
    errors="coerce"
).fillna(0)

# Clean text
df["cleaned_text"] = df["text"].apply(clean_text)

# Remove empty feedback
df = df[df["cleaned_text"].str.strip() != ""]

# Standardize values
df["category"] = df["category"].str.lower().str.strip()
df["sentiment"] = df["sentiment"].str.lower().str.strip()

df.to_csv(OUTPUT_FILE, index=False)

print("\nCleaning completed!")
print("Final records:", len(df))
print("\nSentiment:")
print(df["sentiment"].value_counts())

print("\nCategories:")
print(df["category"].value_counts())

print("\nSaved:")
print(OUTPUT_FILE)