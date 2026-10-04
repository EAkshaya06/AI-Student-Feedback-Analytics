// ======================================================
// AI STUDENT FEEDBACK ANALYTICS
// PREDICTIVE ANALYTICS
// ======================================================


let predictionChart = null;


// ======================================================
// LOAD PREDICTIONS
// ======================================================

async function loadPredictions() {

    const status =
        document.getElementById(
            "predictionStatus"
        );


    try {

        status.textContent =
            "Loading prediction results...";


        // ----------------------------------------------
        // GET ALL FEEDBACK
        // ----------------------------------------------

        const response =
            await fetch(
                "/api/feedback"
            );


        if (!response.ok) {

            throw new Error(
                "Unable to load feedback"
            );

        }


        const result =
            await response.json();


        console.log(
            "Prediction data:",
            result
        );


        if (!result.success ||
            !result.data) {

            throw new Error(
                "No prediction data found"
            );

        }


        const records =
            result.data;


        // ----------------------------------------------
        // COUNT PREDICTED SENTIMENT
        // ----------------------------------------------

        let positive = 0;

        let neutral = 0;

        let negative = 0;


        records.forEach(
            record => {

                const sentiment =
                    String(
                        record.predicted_sentiment ||
                        record.sentiment ||
                        "neutral"
                    )
                    .toLowerCase()
                    .trim();


                if (
                    sentiment ===
                    "positive"
                ) {

                    positive++;

                }

                else if (
                    sentiment ===
                    "negative"
                ) {

                    negative++;

                }

                else {

                    neutral++;

                }

            }
        );


        // ----------------------------------------------
        // UPDATE CARDS
        // ----------------------------------------------

        document.getElementById(
            "predictionTotal"
        ).textContent =
            records.length;


        document.getElementById(
            "predictionPositive"
        ).textContent =
            positive;


        document.getElementById(
            "predictionNeutral"
        ).textContent =
            neutral;


        document.getElementById(
            "predictionNegative"
        ).textContent =
            negative;


        // ----------------------------------------------
        // CREATE CHART
        // ----------------------------------------------

        createPredictionChart(
            positive,
            neutral,
            negative
        );


        status.textContent =
            "Prediction analysis loaded successfully.";


    } catch (error) {

        console.error(
            "Prediction error:",
            error
        );


        status.textContent =
            "Unable to load prediction results.";

        status.classList.add(
            "error"
        );

    }

}


// ======================================================
// CREATE PREDICTION CHART
// ======================================================

function createPredictionChart(
    positive,
    neutral,
    negative
) {

    const canvas =
        document.getElementById(
            "predictionChart"
        );


    if (!canvas) return;


    if (predictionChart) {

        predictionChart.destroy();

    }


    predictionChart =
        new Chart(

            canvas,

            {

                type: "doughnut",

                data: {

                    labels: [

                        "Positive",

                        "Neutral",

                        "Negative"

                    ],

                    datasets: [{

                        data: [

                            positive,

                            neutral,

                            negative

                        ]

                    }]

                },

                options: {

                    responsive: true,

                    maintainAspectRatio: false,

                    plugins: {

                        legend: {

                            position:
                                "bottom"

                        }

                    }

                }

            }

        );

}


// ======================================================
// START
// ======================================================

document.addEventListener(

    "DOMContentLoaded",

    function () {

        loadPredictions();

    }

);