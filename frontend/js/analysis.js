// ======================================================
// AI STUDENT FEEDBACK ANALYTICS
// ANALYTICS PAGE
// ======================================================


let sentimentChart = null;

let emotionChart = null;

let categoryChart = null;

let sentimentCategoryChart = null;


// ======================================================
// LOAD ANALYTICS
// ======================================================

async function loadAnalytics() {

    try {

        const response =
            await fetch(
                "/api/analytics"
            );


        if (!response.ok) {

            throw new Error(
                "Analytics API failed"
            );

        }


        const data =
            await response.json();


        console.log(
            "Analytics data:",
            data
        );


        if (!data.success) {

            throw new Error(
                "Analytics data unavailable"
            );

        }


        // Create charts

        createSentimentChart(
            data.sentiment
        );


        createEmotionChart(
            data.emotion
        );


        createCategoryChart(
            data.category
        );


        createSentimentCategoryChart(
            data.sentiment_by_category
        );


        // Summary

        createSummary(data);


    } catch (error) {

        console.error(
            "Analytics error:",
            error
        );


        document.getElementById(
            "analyticsSummary"
        ).innerHTML = `

            <p style="
                color:#dc2626;
                padding:20px;
            ">

                Unable to load analytics data.

            </p>

        `;

    }

}


// ======================================================
// SENTIMENT
// ======================================================

function createSentimentChart(data) {

    const canvas =
        document.getElementById(
            "analyticsSentimentChart"
        );


    if (!canvas) return;


    if (sentimentChart) {

        sentimentChart.destroy();

    }


    sentimentChart =
        new Chart(canvas, {

            type: "pie",

            data: {

                labels:
                    Object.keys(data || {}),

                datasets: [{

                    data:
                        Object.values(data || {})

                }]

            },

            options: {

                responsive: true,

                maintainAspectRatio: false,

                plugins: {

                    legend: {

                        position: "bottom"

                    }

                }

            }

        });

}


// ======================================================
// EMOTION
// ======================================================

function createEmotionChart(data) {

    const canvas =
        document.getElementById(
            "analyticsEmotionChart"
        );


    if (!canvas) return;


    if (emotionChart) {

        emotionChart.destroy();

    }


    emotionChart =
        new Chart(canvas, {

            type: "bar",

            data: {

                labels:
                    Object.keys(data || {}),

                datasets: [{

                    label:
                        "Emotion Count",

                    data:
                        Object.values(data || {})

                }]

            },

            options: {

                responsive: true,

                maintainAspectRatio: false,

                scales: {

                    y: {

                        beginAtZero: true

                    }

                }

            }

        });

}


// ======================================================
// CATEGORY
// ======================================================

function createCategoryChart(data) {

    const canvas =
        document.getElementById(
            "analyticsCategoryChart"
        );


    if (!canvas) return;


    if (categoryChart) {

        categoryChart.destroy();

    }


    categoryChart =
        new Chart(canvas, {

            type: "bar",

            data: {

                labels:
                    Object.keys(data || {}),

                datasets: [{

                    label:
                        "Feedback Count",

                    data:
                        Object.values(data || {})

                }]

            },

            options: {

                responsive: true,

                maintainAspectRatio: false,

                scales: {

                    y: {

                        beginAtZero: true

                    }

                }

            }

        });

}


// ======================================================
// SENTIMENT BY CATEGORY
// ======================================================

function createSentimentCategoryChart(data) {

    const canvas =
        document.getElementById(
            "analyticsSentimentCategoryChart"
        );


    if (!canvas) return;


    if (sentimentCategoryChart) {

        sentimentCategoryChart.destroy();

    }


    const categories =
        Object.keys(data || {});


    const positive =
        categories.map(
            category =>
                data[category].positive || 0
        );


    const neutral =
        categories.map(
            category =>
                data[category].neutral || 0
        );


    const negative =
        categories.map(
            category =>
                data[category].negative || 0
        );


    sentimentCategoryChart =
        new Chart(canvas, {

            type: "bar",

            data: {

                labels: categories,

                datasets: [

                    {

                        label:
                            "Positive",

                        data:
                            positive

                    },

                    {

                        label:
                            "Neutral",

                        data:
                            neutral

                    },

                    {

                        label:
                            "Negative",

                        data:
                            negative

                    }

                ]

            },

            options: {

                responsive: true,

                maintainAspectRatio: false,

                scales: {

                    y: {

                        beginAtZero: true

                    }

                }

            }

        });

}


// ======================================================
// SUMMARY
// ======================================================

function createSummary(data) {

    const container =
        document.getElementById(
            "analyticsSummary"
        );


    const positive =
        data.positive_percentage;


    const neutral =
        data.neutral_percentage;


    const negative =
        data.negative_percentage;


    container.innerHTML = `

        <table class="analytics-table">

            <tr>

                <th>
                    Metric
                </th>

                <th>
                    Value
                </th>

            </tr>

            <tr>

                <td>
                    Total Feedback
                </td>

                <td>
                    ${data.total}
                </td>

            </tr>

            <tr>

                <td>
                    Positive Feedback
                </td>

                <td>
                    ${data.positive}
                    (${positive}%)
                </td>

            </tr>

            <tr>

                <td>
                    Neutral Feedback
                </td>

                <td>
                    ${data.neutral}
                    (${neutral}%)
                </td>

            </tr>

            <tr>

                <td>
                    Negative Feedback
                </td>

                <td>
                    ${data.negative}
                    (${negative}%)
                </td>

            </tr>

        </table>

    `;

}


// ======================================================
// START
// ======================================================

document.addEventListener(
    "DOMContentLoaded",
    function () {

        loadAnalytics();

    }
);