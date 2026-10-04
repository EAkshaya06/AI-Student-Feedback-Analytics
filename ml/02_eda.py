import pandas as pd
import matplotlib.pyplot as plt
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(BASE_DIR, "backend", "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "ml", "output")

os.makedirs(OUTPUT_DIR, exist_ok=True)

INPUT_FILE = os.path.join(DATA_DIR, "cleaned_feedback.csv")


print("\n======================================")
print("EXPLORATORY DATA ANALYSIS")
print("======================================\n")


# Load dataset
df = pd.read_csv(INPUT_FILE)

print("Records:", len(df))
print("Columns:", list(df.columns))


# ==================================================
# 1. SENTIMENT DISTRIBUTION
# ==================================================

sentiment_counts = df["sentiment"].value_counts()

plt.figure(figsize=(8, 5))

sentiment_counts.plot(kind="bar")

plt.title("Student Feedback Sentiment Distribution")
plt.xlabel("Sentiment")
plt.ylabel("Number of Feedback Records")

plt.xticks(rotation=0)
plt.tight_layout()

sentiment_file = os.path.join(
    OUTPUT_DIR,
    "sentiment_distribution.png"
)

plt.savefig(sentiment_file, dpi=300)

plt.close()

print("\nCreated:")
print(sentiment_file)


# ==================================================
# 2. CATEGORY DISTRIBUTION
# ==================================================

category_counts = df["category"].value_counts()

plt.figure(figsize=(9, 5))

category_counts.plot(kind="bar")

plt.title("Student Feedback by Category")
plt.xlabel("Category")
plt.ylabel("Number of Feedback Records")

plt.xticks(rotation=45, ha="right")
plt.tight_layout()

category_file = os.path.join(
    OUTPUT_DIR,
    "category_distribution.png"
)

plt.savefig(category_file, dpi=300)

plt.close()

print("\nCreated:")
print(category_file)


# ==================================================
# 3. SENTIMENT BY CATEGORY
# ==================================================

cross_table = pd.crosstab(
    df["category"],
    df["sentiment"]
)

plt.figure(figsize=(10, 6))

cross_table.plot(
    kind="bar",
    ax=plt.gca()
)

plt.title("Sentiment by Feedback Category")
plt.xlabel("Category")
plt.ylabel("Number of Feedback Records")

plt.xticks(rotation=45, ha="right")

plt.tight_layout()

sentiment_category_file = os.path.join(
    OUTPUT_DIR,
    "sentiment_by_category.png"
)

plt.savefig(
    sentiment_category_file,
    dpi=300
)

plt.close()

print("\nCreated:")
print(sentiment_category_file)


# ==================================================
# COMPLETED
# ==================================================

print("\n======================================")
print("EDA COMPLETED SUCCESSFULLY")
print("======================================")

print("\nAll graphs are saved in:")

print(OUTPUT_DIR)

print("\nFiles created:")

print("1. sentiment_distribution.png")
print("2. category_distribution.png")
print("3. sentiment_by_category.png")