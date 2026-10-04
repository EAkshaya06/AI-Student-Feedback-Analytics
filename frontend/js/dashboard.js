// ======================================================
// AI STUDENT FEEDBACK ANALYTICS
// DASHBOARD JAVASCRIPT
// ======================================================


let sentimentChart = null;
let emotionChart = null;
let categoryChart = null;
let sentimentCategoryChart = null;


// ======================================================
// LOAD DASHBOARD
// ======================================================

async function loadDashboard() {

    const status =
        document.getElementById("dashboardStatus");

    try {

        status.textContent =
            "Loading dashboard data...";


        // ----------------------------------------------
        // GET ANALYTICS
        // ----------------------------------------------

        const analyticsResponse =
            await fetch("/api/analytics");

        if (!analyticsResponse.ok) {

            throw new Error(
                "Unable to load analytics"
            );
        }


        const analytics =
            await analyticsResponse.json();


        console.log(
            "Analytics:",
            analytics
        );


        if (!analytics.success) {

            throw new Error(
                "Analytics API returned an error"
            );
        }


        // ----------------------------------------------
        // UPDATE STATISTICS
        // ----------------------------------------------

        document.getElementById(
            "totalFeedback"
        ).textContent =
            analytics.total;


        document.getElementById(
            "positiveFeedback"
        ).textContent =
            analytics.positive_percentage + "%";


        document.getElementById(
            "neutralFeedback"
        ).textContent =
            analytics.neutral_percentage + "%";


        document.getElementById(
            "negativeFeedback"
        ).textContent =
            analytics.negative_percentage + "%";


        document.getElementById(
            "datasetRecords"
        ).textContent =
            analytics.total;


        // ----------------------------------------------
        // CREATE CHARTS
        // ----------------------------------------------

        createSentimentChart(
            analytics.sentiment
        );


        createEmotionChart(
            analytics.emotion
        );


        createCategoryChart(
            analytics.category
        );


        createSentimentCategoryChart(
            analytics.sentiment_by_category
        );


        // ----------------------------------------------
        // LOAD FEEDBACK
        // ----------------------------------------------

        await loadFeedback();


        // ----------------------------------------------
        // LOAD RECOMMENDATIONS
        // ----------------------------------------------

        await loadRecommendations();


        status.textContent =
            "Dashboard updated successfully.";


    } catch (error) {

        console.error(
            "Dashboard error:",
            error
        );

        status.textContent =
            "Unable to load dashboard data. Check the browser console.";

        status.classList.add("error");
    }
}


// ======================================================
// SENTIMENT CHART
// ======================================================

function createSentimentChart(data) {

    const canvas =
        document.getElementById(
            "sentimentChart"
        );

    if (!canvas) return;


    if (sentimentChart) {

        sentimentChart.destroy();

    }


    const labels =
        Object.keys(data || {});


    const values =
        Object.values(data || {});


    sentimentChart =
        new Chart(canvas, {

            type: "doughnut",

            data: {

                labels: labels,

                datasets: [{

                    data: values

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
// EMOTION CHART
// ======================================================

function createEmotionChart(data) {

    const canvas =
        document.getElementById(
            "emotionChart"
        );

    if (!canvas) return;


    if (emotionChart) {

        emotionChart.destroy();

    }


    const labels =
        Object.keys(data || {});


    const values =
        Object.values(data || {});


    emotionChart =
        new Chart(canvas, {

            type: "bar",

            data: {

                labels: labels,

                datasets: [{

                    label: "Feedback Count",

                    data: values

                }]

            },

            options: {

                responsive: true,

                maintainAspectRatio: false,

                scales: {

                    y: {

                        beginAtZero: true

                    }

                },

                plugins: {

                    legend: {

                        display: false

                    }

                }

            }

        });
}


// ======================================================
// CATEGORY CHART
// ======================================================

function createCategoryChart(data) {

    const canvas =
        document.getElementById(
            "categoryChart"
        );

    if (!canvas) return;


    if (categoryChart) {

        categoryChart.destroy();

    }


    const labels =
        Object.keys(data || {});


    const values =
        Object.values(data || {});


    categoryChart =
        new Chart(canvas, {

            type: "bar",

            data: {

                labels: labels,

                datasets: [{

                    label: "Feedback Count",

                    data: values

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
            "sentimentCategoryChart"
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

                        label: "Positive",

                        data: positive

                    },

                    {

                        label: "Neutral",

                        data: neutral

                    },

                    {

                        label: "Negative",

                        data: negative

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
// LOAD FEEDBACK
// ======================================================

async function loadFeedback() {

    const container =
        document.getElementById(
            "feedbackTableContainer"
        );


    try {

        const response =
            await fetch("/api/feedback");


        const result =
            await response.json();


        console.log(
            "Feedback:",
            result
        );


        if (
            !result.success ||
            !result.data ||
            result.data.length === 0
        ) {

            container.innerHTML =
                "<p>No feedback records found.</p>";

            return;
        }


        // Show latest/sample 10 records

        const records =
            result.data.slice(0, 10);


        let html = `

            <div style="overflow-x:auto;">

                <table style="
                    width:100%;
                    border-collapse:collapse;
                    font-size:14px;
                ">

                    <thead>

                        <tr>

                            <th style="
                                text-align:left;
                                padding:12px;
                                border-bottom:1px solid #ddd;
                            ">
                                Feedback
                            </th>

                            <th style="
                                text-align:left;
                                padding:12px;
                                border-bottom:1px solid #ddd;
                            ">
                                Category
                            </th>

                            <th style="
                                text-align:left;
                                padding:12px;
                                border-bottom:1px solid #ddd;
                            ">
                                Sentiment
                            </th>

                            <th style="
                                text-align:left;
                                padding:12px;
                                border-bottom:1px solid #ddd;
                            ">
                                Emotion
                            </th>

                        </tr>

                    </thead>

                    <tbody>
        `;


        records.forEach(
            record => {

                const text =
                    record.text ||
                    record.feedback_text ||
                    "";


                const category =
                    record.category ||
                    "Unknown";


                const sentiment =
                    record.sentiment ||
                    "neutral";


                const emotion =
                    record.emotion ||
                    "Neutral";


                html += `

                    <tr>

                        <td style="
                            padding:12px;
                            border-bottom:1px solid #eee;
                            max-width:450px;
                        ">
                            ${escapeHTML(text)}
                        </td>

                        <td style="
                            padding:12px;
                            border-bottom:1px solid #eee;
                        ">
                            ${escapeHTML(category)}
                        </td>

                        <td style="
                            padding:12px;
                            border-bottom:1px solid #eee;
                        ">
                            ${escapeHTML(sentiment)}
                        </td>

                        <td style="
                            padding:12px;
                            border-bottom:1px solid #eee;
                        ">
                            ${escapeHTML(emotion)}
                        </td>

                    </tr>

                `;
            }
        );


        html += `

                    </tbody>

                </table>

            </div>

            <p style="
                margin-top:15px;
                color:#64748b;
                font-size:13px;
            ">
                Showing 10 sample records from
                ${result.count} total feedback records.
            </p>

        `;


        container.innerHTML = html;


    } catch (error) {

        console.error(
            "Feedback error:",
            error
        );

        container.innerHTML =
            "<p>Unable to load feedback.</p>";
    }
}


// ======================================================
// LOAD RECOMMENDATIONS
// ======================================================

async function loadRecommendations() {

    const container =
        document.getElementById(
            "recommendations"
        );


    try {

        const response =
            await fetch(
                "/api/recommendations"
            );


        const result =
            await response.json();


        console.log(
            "Recommendations:",
            result
        );


        if (
            !result.success ||
            !result.recommendations ||
            result.recommendations.length === 0
        ) {

            container.innerHTML =
                "<p>No recommendations available.</p>";

            return;
        }


        container.innerHTML = "";


        result.recommendations.forEach(
            recommendation => {

                const div =
                    document.createElement(
                        "div"
                    );


                div.className =
                    "insight-item";


                div.innerHTML = `

                    <span>💡</span>

                    <p>
                        ${escapeHTML(
                            recommendation
                        )}
                    </p>

                `;


                container.appendChild(div);

            }
        );


    } catch (error) {

        console.error(
            "Recommendation error:",
            error
        );

        container.innerHTML =
            "<p>Unable to load recommendations.</p>";
    }
}


// ======================================================
// HTML ESCAPE
// ======================================================

function escapeHTML(value) {

    const div =
        document.createElement(
            "div"
        );

    div.textContent =
        value;

    return div.innerHTML;
}


// ======================================================
// START DASHBOARD
// ======================================================

document.addEventListener(
    "DOMContentLoaded",
    function () {

        loadDashboard();

    }
);