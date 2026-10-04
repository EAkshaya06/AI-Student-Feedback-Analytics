import pandas as pd
import os


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
    "final_feedback_analysis.csv"
)


df = pd.read_csv(
    INPUT_FILE
)


recommendations = []


# ==========================================
# CATEGORY ANALYSIS
# ==========================================

for category in df["category"].unique():

    category_data = df[
        df["category"] == category
    ]

    total = len(category_data)

    negative = len(
        category_data[
            category_data["sentiment"]
            == "negative"
        ]
    )

    if total == 0:
        continue

    negative_percentage = (
        negative / total
    ) * 100


    if negative_percentage >= 30:

        recommendations.append(
            f"High attention required for "
            f"{category}. Around "
            f"{negative_percentage:.1f}% "
            f"of feedback is negative."
        )

    elif negative_percentage >= 20:

        recommendations.append(
            f"Monitor {category} closely "
            f"and identify recurring student concerns."
        )

    else:

        recommendations.append(
            f"{category} is performing relatively "
            f"well based on current sentiment."
        )


# ==========================================
# PRINT RESULTS
# ==========================================

print("\n======================================")
print("AI RECOMMENDATION ENGINE")
print("======================================\n")


for number, recommendation in enumerate(
    recommendations,
    start=1
):

    print(
        f"{number}. {recommendation}"
    )


# ==========================================
# SAVE RECOMMENDATIONS
# ==========================================

OUTPUT_FILE = os.path.join(
    DATA_DIR,
    "recommendations.txt"
)


with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as file:

    for recommendation in recommendations:

        file.write(
            recommendation + "\n"
        )


print(
    "\nRecommendations saved to:"
)

print(
    OUTPUT_FILE
)