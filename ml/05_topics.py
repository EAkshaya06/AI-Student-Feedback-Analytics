import pandas as pd
import os

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans


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

INPUT_FILE = os.path.join(
    DATA_DIR,
    "emotion_feedback.csv"
)

OUTPUT_FILE = os.path.join(
    DATA_DIR,
    "topic_feedback.csv"
)


df = pd.read_csv(
    INPUT_FILE
)


vectorizer = TfidfVectorizer(
    stop_words="english",
    max_features=3000
)


X = vectorizer.fit_transform(
    df["cleaned_text"]
)


number_of_topics = 6


model = KMeans(
    n_clusters=number_of_topics,
    random_state=42,
    n_init=10
)


df["topic_cluster"] = model.fit_predict(
    X
)


terms = vectorizer.get_feature_names_out()


print("\n======================================")
print("TOPIC CLUSTERING")
print("======================================\n")


topic_names = {}


for cluster in range(number_of_topics):

    center = model.cluster_centers_[cluster]

    top_indices = center.argsort()[-8:][::-1]

    top_words = [
        terms[index]
        for index in top_indices
    ]

    topic_names[
        cluster
    ] = " / ".join(top_words)

    print(
        f"Topic {cluster + 1}:",
        ", ".join(top_words)
    )


df["topic"] = df[
    "topic_cluster"
].map(topic_names)


df.to_csv(
    OUTPUT_FILE,
    index=False
)


print(
    "\nTopic analysis completed."
)

print(
    "Saved:",
    OUTPUT_FILE
)