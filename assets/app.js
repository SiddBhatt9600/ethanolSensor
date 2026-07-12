async function loadLiveData() {

    try {

        const response = await fetch("/api/sensors");
        const data = await response.json();

        const liveStatus = document.getElementById("liveStatus");
        const table = document.getElementById("sensorTable");
        const tbody = document.querySelector("#sensorTable tbody");

        tbody.innerHTML = "";

        if (!data || data.length === 0) {

            liveStatus.style.display = "block";
            liveStatus.innerHTML = "Waiting for first sensor reading...";

            table.style.display = "none";

            return;
        }

        liveStatus.style.display = "none";
        table.style.display = "table";

        data.forEach(sensor => {

            tbody.innerHTML += `

            <tr>

                <td>${sensor.timestamp}</td>

                <td>${sensor.temp}</td>

                <td>${sensor.ethanol}</td>

                <td>${sensor.density}</td>

                <td>${sensor.wif}</td>

                <td>${sensor.turbidity}</td>

            </tr>

            `;

        });

    }

    catch(err){

        console.error("Live API:",err);

    }

}

async function loadButtonCapture() {

    try {

        const response = await fetch("/api/button_capture");
        const capture = await response.json();

        const captureStatus =
            document.getElementById("captureStatus");

        const captureTable =
            document.getElementById("captureTable");

        const average =
            document.getElementById("average");

        const tbody =
            document.querySelector("#captureTable tbody");

        tbody.innerHTML = "";

        if (

            !capture ||

            !capture.samples ||

            capture.samples.length === 0

        ){

            captureStatus.innerHTML =
            "Press the button to record the average of the next 5 readings.";

            captureTable.style.display = "none";

            average.style.display = "none";

            return;

        }

        captureStatus.innerHTML =
        "Latest Button Capture";

        captureTable.style.display = "table";

        average.style.display = "block";

        capture.samples.forEach((sample,index)=>{

            tbody.innerHTML += `

            <tr>

                <td>${index+1}</td>

                <td>${sample.temp}</td>

                <td>${sample.ethanol}</td>

                <td>${sample.density}</td>

                <td>${sample.wif}</td>

                <td>${sample.turbidity}</td>

            </tr>

            `;

        });

        average.innerHTML =

        `

        <b>Temperature</b> : ${capture.average.temp} °C<br><br>

        <b>Ethanol</b> : ${capture.average.ethanol} %<br><br>

        <b>Density</b> : ${capture.average.density}<br><br>

        <b>Water</b> : ${capture.average.wif}<br><br>

        <b>Turbidity</b> : ${capture.average.turbidity}

        `;

    }

    catch(err){

        console.error("Capture API:",err);

    }

}

/* ==========================================================
   AI Verdict Section
   ========================================================== */

function verdictClass(verdict){

    if (verdict === "GOOD")        return "verdict-good";
    if (verdict === "SUSPECT")     return "verdict-suspect";
    if (verdict === "ADULTERATED") return "verdict-bad";

    return "verdict-unknown";

}

async function loadAiVerdict() {

    try {

        const response = await fetch("/api/ai/current");
        const v = await response.json();

        const card = document.getElementById("aiCard");
        const verdictEl = document.getElementById("aiVerdict");
        const confEl = document.getElementById("aiConfidence");
        const probsEl = document.getElementById("aiProbs");
        const signalsEl = document.getElementById("aiSignals");
        const anomEl = document.getElementById("aiAnomalies");

        if (!v || !v.verdict || v.verdict === "UNKNOWN") {

            card.className = "verdict-unknown";

            verdictEl.innerHTML = "WAITING…";

            confEl.innerHTML =
            "First verdict arrives within ~10 seconds.";

            probsEl.innerHTML = "";
            signalsEl.innerHTML = "";
            anomEl.innerHTML = "";

            return;

        }

        card.className = verdictClass(v.verdict);

        verdictEl.innerHTML = v.verdict;

        confEl.innerHTML =
        `Confidence : ${(v.confidence * 100).toFixed(1)} %`;

        probsEl.innerHTML =

        `GOOD ${(v.probs.GOOD * 100).toFixed(1)} % · ` +
        `SUSPECT ${(v.probs.SUSPECT * 100).toFixed(1)} % · ` +
        `ADULTERATED ${(v.probs.ADULTERATED * 100).toFixed(1)} %`;

        signalsEl.innerHTML =

        "<b>Why:</b> " + v.explain.signals.join(" · ") +
        `<br><b>Density @15°C:</b> ${v.explain.density15} kg/m³ ` +
        `(physics expects ${v.explain.expected_density15} ` +
        `for ${v.reading ? v.reading.ethanol : "?"}% ethanol, ` +
        `residual ${v.explain.rho_residual})`;

        if (v.anomalies && v.anomalies.length > 0) {

            anomEl.style.display = "block";

            anomEl.innerHTML =

            "<b>⚠ Drift alert (possible refuel / quality change):</b><br>" +

            v.anomalies.map(a =>

                `${a.parameter}: ${a.value} vs baseline ` +
                `${a.baseline_mean} (z = ${a.z_score})`

            ).join("<br>");

        }

        else {

            anomEl.style.display = "none";

            anomEl.innerHTML = "";

        }

    }

    catch(err){

        console.error("AI current API:",err);

    }

}

async function loadAiHistory() {

    try {

        const response = await fetch("/api/ai/verdicts");
        const data = await response.json();

        const table = document.getElementById("aiTable");
        const tbody = document.querySelector("#aiTable tbody");

        if (!data || data.length === 0) {

            table.style.display = "none";

            return;

        }

        table.style.display = "table";

        tbody.innerHTML = "";

        data.slice().reverse().forEach(v => {

            const anomalies =

                (v.anomalies && v.anomalies.length > 0)

                ? v.anomalies.map(a => a.parameter).join(", ")

                : "—";

            tbody.innerHTML += `

            <tr>

                <td>${v.timestamp}</td>

                <td class="${verdictClass(v.verdict)}-text">
                    ${v.verdict}
                </td>

                <td>${(v.confidence * 100).toFixed(1)} %</td>

                <td>${v.explain.density15}</td>

                <td>${v.explain.expected_density15}</td>

                <td>${v.explain.rho_residual}</td>

                <td>${anomalies}</td>

            </tr>

            `;

        });

    }

    catch(err){

        console.error("AI history API:",err);

    }

}

async function analyzeCapture() {

    const out = document.getElementById("captureVerdict");

    out.style.display = "block";

    out.innerHTML = "Analyzing…";

    try {

        const response = await fetch("/api/ai/capture_verdict");
        const v = await response.json();

        if (v.error) {

            out.innerHTML =
            "No capture available yet — press the button first.";

            return;

        }

        out.className = verdictClass(v.verdict);

        out.innerHTML =

        `<b>${v.verdict}</b> ` +
        `(confidence ${(v.confidence * 100).toFixed(1)} %)<br>` +
        v.explain.signals.join(" · ");

    }

    catch(err){

        console.error("Capture verdict API:",err);

        out.innerHTML = "Analysis failed — see console.";

    }

}

function refreshDashboard(){

    loadLiveData();

    loadButtonCapture();

    loadAiVerdict();

    loadAiHistory();

}

refreshDashboard();

setInterval(refreshDashboard,1000);