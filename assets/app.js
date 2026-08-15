/*****************************************************************
 *
 * Dashboard State
 *
 *****************************************************************/

let lastHeartbeat = "--";

/*****************************************************************
 *
 * Helpers
 *
 *****************************************************************/
function display(value, unit = "")
{
    return value == null ? "--" : value + unit;
}

function updateLastUpdate()
{
    document.getElementById("lastUpdate").innerHTML =
        "Last Update : " +
        new Date().toLocaleTimeString();
}

function setConnected(state)
{
    const connection =
        document.getElementById("connectionStatus");

    if(state)
    {
        connection.innerHTML = "● Connected";
        connection.style.color = "#22c55e";
    }
    else
    {
        connection.innerHTML = "● Disconnected";
        connection.style.color = "#ef4444";
    }
}

/*****************************************************************
 *
 * Turbidity card — field calibration (2 Aug 2026 observations):
 * raw sensor index >= 35 clean, 30-35 suspicious, < 30 adulterated.
 * This is the RAW board index, not the AI model's internal
 * turbidity feature (sensorManager.calibrate_turbidity() remaps it
 * onto an inverted 0-100 scale for the model — showing that number
 * here would look backwards against these field bands, since a
 * clean sample reads near 0 on the model's scale but 35+ here).
 *
 *****************************************************************/

const TURBIDITY_CLEAN = 35;
const TURBIDITY_SUSPECT = 30;

function updateTurbidityCard(raw) {

    const el = document.getElementById("turbidityValue");

    el.classList.remove(
        "verdict-good-text", "verdict-suspect-text", "verdict-bad-text"
    );

    if (typeof raw !== "number") {
        el.innerHTML = "--";
        return;
    }

    el.innerHTML = display(raw);

    if (raw >= TURBIDITY_CLEAN) el.classList.add("verdict-good-text");
    else if (raw >= TURBIDITY_SUSPECT) el.classList.add("verdict-suspect-text");
    else el.classList.add("verdict-bad-text");

}

/*****************************************************************
 *
 * Live Sensor Data
 *
 *****************************************************************/

async function loadSensorData()
{

    try
    {

        const response =
            await fetch("/api/sensors");

        const data =
            await response.json();

        const tbody =
            document.querySelector(
                "#sensorTable tbody"
            );

        tbody.innerHTML = "";

        if(data.length === 0)
        {

            document.getElementById(
                "liveStatus"
            ).style.display = "block";

            document.getElementById(
                "sensorTable"
            ).style.display = "none";

            setConnected(true);

            return;
        }

        document.getElementById(
            "liveStatus"
        ).style.display = "none";

        document.getElementById(
            "sensorTable"
        ).style.display = "table";

        // This table is a raw, continuous diagnostic feed only.
        // The dashboard cards (Ethanol/Temp/Density/Water/Turbidity)
        // and the AI verdict are populated exclusively from the
        // latest button-press capture — see updateCardsFromReading()
        // in loadAiVerdict() — so they intentionally do NOT read
        // from `data` here anymore.

        /*****************************************************
         * Table
         *****************************************************/

        data.forEach(sensor=>{

            tbody.innerHTML +=

            `

            <tr>

                <td>${sensor.timestamp}</td>

                <td>${sensor.temp}</td>

                <td>${sensor.ethanol}</td>

                <td>${sensor.density}</td>

                <td>${sensor.wif}</td>

                <td>${sensor.turbidity_raw}</td>

            </tr>

            `;

        });

        updateLastUpdate();

        setConnected(true);

    }

    catch(err)
    {

        console.error(err);

        setConnected(false);

    }

}

/*****************************************************************
 *
 * Button Capture
 *
 *****************************************************************/

async function loadButtonCapture()
{

    try
    {

        const response =
            await fetch("/api/button_capture");

        const capture =
            await response.json();

        const table =
            document.getElementById(
                "captureTable"
            );

        const average =
            document.getElementById(
                "average"
            );

        const tbody =
            document.querySelector(
                "#captureTable tbody"
            );

        tbody.innerHTML = "";

        if(

            !capture ||

            !capture.samples ||

            capture.samples.length === 0

        )
        {

            document.getElementById(
                "captureStatus"
            ).innerHTML =

            "Press the button to take 5 fresh readings on the spot. " +
            "The AI Fuel Quality Verdict above updates automatically " +
            "as soon as this capture finishes (a couple of seconds).";

            table.style.display = "none";

            average.style.display = "none";

            return;

        }

        table.style.display = "table";

        average.style.display = "block";

        document.getElementById(
            "captureStatus"
        ).innerHTML =

        "Latest Button Capture";

        capture.samples.forEach((sample,index)=>{

            tbody.innerHTML +=

            `

            <tr>

                <td>${index+1}</td>

                <td>${sample.temp}</td>

                <td>${sample.ethanol}</td>

                <td>${sample.density}</td>

                <td>${sample.wif}</td>

                <td>${sample.turbidity_raw}</td>

            </tr>

            `;

        });

        average.innerHTML =

        `

        <b>Temperature</b> : ${capture.average.temp} °C<br><br>

        <b>Ethanol</b> : ${capture.average.ethanol} %<br><br>

        <b>Density</b> : ${capture.average.density}<br><br>

        <b>Water</b> : ${capture.average.wif}<br><br>

        <b>Turbidity</b> : ${capture.average.turbidity_raw}

        `;

    }

    catch(err)
    {

        console.error(err);

    }

}

/*****************************************************************
 *
 * Measured Density (user input — no board density sensor)
 *
 *****************************************************************/

async function loadDensityStatus() {

    try {

        const response = await fetch("/api/user/density");
        const d = await response.json();

        const statusEl = document.getElementById("densityStatus");

        if (!d || d.density === null || d.density === undefined) {

            statusEl.innerHTML =
            "No density entered yet — enter a hydrometer/measured " +
            "reading below. The AI verdict will not appear until " +
            "this is set (there is no density sensor on the board).";

            return;

        }

        statusEl.innerHTML =
        `Current density in use: <b>${d.density} kg/m³</b> ` +
        `(set ${d.timestamp})`;

    }

    catch(err) {

        console.error("Density status API:", err);

    }

}

async function submitDensity() {

    const input = document.getElementById("densityInput");
    const result = document.getElementById("densityResult");

    const value = parseFloat(input.value);

    if (isNaN(value)) {

        result.innerHTML = "Enter a numeric density value first.";
        return;

    }

    result.innerHTML = "Submitting…";

    try {

        const response = await fetch("/api/user/density", {

            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({density: value})

        });

        const d = await response.json();

        if (d.error) {

            result.innerHTML = `Failed: ${d.error}`;
            return;

        }

        result.innerHTML =
        `Density set to ${d.density} kg/m³. Press the button to ` +
        `take a new reading and get a verdict with it.`;

        loadDensityStatus();

    }

    catch(err) {

        console.error("Density submit API:", err);
        result.innerHTML = "Submit failed — see console.";

    }

}

/*****************************************************************
 *
 * AI Verdict Section
 *
 *****************************************************************/

function verdictClass(verdict){

    if (verdict === "GOOD")        return "verdict-good";
    if (verdict === "SUSPECT")     return "verdict-suspect";
    if (verdict === "ADULTERATED") return "verdict-bad";

    return "verdict-unknown";

}

function verdictLabel(verdict){

    if (verdict === "AWAITING_DENSITY") return "ENTER DENSITY";

    return verdict;

}

/*****************************************************************
 *
 * Water In Fuel card — driven by the AI verdict's anomalies list
 * rather than its own fixed wif threshold, since the anomalies
 * panel (fuelQualityModel._signals(), wired through per-blend
 * water-saturation logic) is the source of truth for whether a
 * given water reading is actually suspicious for that ethanol
 * blend. The card just shows the live number, colored by whatever
 * the anomalies say.
 *
 *****************************************************************/

function waterAnomalySeverity(anomalies) {

    if (!anomalies) return "normal";

    let severity = "normal";

    for (const a of anomalies) {

        const reason = (a.type === "quality" ? a.reason : "") || "";
        const isWifDrift = a.type === "drift" && a.parameter === "wif";

        if (reason.toLowerCase().includes("free water")) {
            return "critical";
        }

        if (isWifDrift || reason.toLowerCase().includes("water")) {
            severity = "warning";
        }

    }

    return severity;

}

/*****************************************************************
 *
 * Ethanol / Temp / Density cards — like Water and Turbidity above,
 * these now come exclusively from the latest button-press capture
 * (v.reading, embedded in the AI verdict response) rather than the
 * separate continuous sensor feed, so every number on the dashboard
 * always describes the exact same 5-reading batch.
 *
 *****************************************************************/

function updateCardsFromReading(reading) {

    const ethanolEl = document.getElementById("ethanolValue");
    const tempEl = document.getElementById("temperatureValue");
    const densityEl = document.getElementById("densityValue");

    if (!reading) {
        ethanolEl.innerHTML = "-- %";
        tempEl.innerHTML = "-- °C";
        densityEl.innerHTML = "--";
        return;
    }

    ethanolEl.innerHTML = display(reading.ethanol, " %");
    tempEl.innerHTML = display(reading.temp, " °C");
    densityEl.innerHTML = display(reading.density);

}

function updateWaterCard(v) {

    const waterEl = document.getElementById("waterValue");

    waterEl.classList.remove(
        "verdict-good-text", "verdict-suspect-text", "verdict-bad-text"
    );

    if (!v || !v.reading || typeof v.reading.wif !== "number") {
        waterEl.innerHTML = "--";
        return;
    }

    waterEl.innerHTML = display(v.reading.wif, " %");

    const severity = waterAnomalySeverity(v.anomalies);

    if (severity === "critical")     waterEl.classList.add("verdict-bad-text");
    else if (severity === "warning") waterEl.classList.add("verdict-suspect-text");
    else                              waterEl.classList.add("verdict-good-text");

}

async function loadAiVerdict() {

    try {

        const response = await fetch("/api/ai/current");
        const v = await response.json();

        const card = document.getElementById("aiCard");
        const verdictEl = document.getElementById("aiVerdict");
        const confEl = document.getElementById("aiConfidence");
        const probsEl = document.getElementById("aiProbs");
        const blendEl = document.getElementById("aiBlend");
        const anomEl = document.getElementById("aiAnomalies");
        const mileageEl = document.getElementById("mileageCard");

        if (!v || !v.verdict || v.verdict === "UNKNOWN") {

            card.className = "verdict-unknown";

            verdictEl.innerHTML = "WAITING…";

            confEl.innerHTML =
            "Press the button to take your first reading.";

            probsEl.innerHTML = "";
            blendEl.innerHTML = "";
            anomEl.innerHTML = "";
            mileageEl.innerHTML = "Waiting for first verdict…";

            updateWaterCard(null);
            updateTurbidityCard(null);
            updateCardsFromReading(null);

            return;

        }

        card.className = verdictClass(v.verdict);

        verdictEl.innerHTML = verdictLabel(v.verdict);

        confEl.innerHTML =
        v.verdict === "AWAITING_DENSITY"
        ? "This capture has no density yet — enter a reading below, " +
          "then press the button again to get an AI verdict."
        : `Confidence : ${(v.confidence * 100).toFixed(1)} %`;

        probsEl.innerHTML =

        `GOOD ${(v.probs.GOOD * 100).toFixed(1)} % · ` +
        `SUSPECT ${(v.probs.SUSPECT * 100).toFixed(1)} % · ` +
        `ADULTERATED ${(v.probs.ADULTERATED * 100).toFixed(1)} %`;

        if (v.blend) {

            blendEl.innerHTML = v.blend.in_spec

            ? `Blend check : ${v.blend.nearest} — measured ` +
              `${v.blend.measured} % ethanol (within band) ✓`

            : `⚠ Blend check : measured ${v.blend.measured} % ` +
              `ethanol — OFF-SPEC (nearest ${v.blend.nearest})`;

        }

        else {

            blendEl.innerHTML = "";

        }

        if (v.mileage) {

            const m = v.mileage;

            mileageEl.innerHTML =

            `<b>${m.estimated_kmpl} km/l</b> estimated ` +
            `(baseline ${m.baseline_kmpl} km/l, ` +
            `${m.total_penalty_pct}% impact)<br>` +

            `Ethanol blend: -${m.breakdown.ethanol_blend_pct}% · ` +
            `Fuel quality: -${m.breakdown.fuel_quality_pct}% · ` +
            `Driving style: -${m.breakdown.driving_behavior_pct}%<br>` +

            `<span class="mileageNote">${m.notes.join(" ")}</span><br>` +
            `<span class="mileageNote">${m.disclaimer}</span>`;

        }

        else {

            mileageEl.innerHTML = "";

        }

        if (v.anomalies && v.anomalies.length > 0) {

            anomEl.style.display = "block";

            anomEl.innerHTML =

            "<b>⚠ Anomalies / quality flags:</b><br>" +

            v.anomalies.map(a =>

                a.type === "quality"
                ? a.reason
                : `drift — ${a.parameter}: ${a.value} vs baseline ` +
                  `${a.baseline_mean} (z = ${a.z_score})`

            ).join("<br>");

        }

        else {

            anomEl.style.display = "none";

            anomEl.innerHTML = "";

        }

        updateWaterCard(v);
        updateTurbidityCard(v.reading ? v.reading.turbidity_raw : null);
        updateCardsFromReading(v.reading);

    }

    catch(err){

        console.error("AI current API:",err);

    }

}

/*****************************************************************
 *
 * Polling
 *
 *****************************************************************/

async function refreshDashboard()
{
    await loadHeartbeat();

    await loadSensorData();

    await loadButtonCapture();

    loadDensityStatus();

    loadAiVerdict();

}

refreshDashboard();

setInterval(

    refreshDashboard,

    1000

);

/*****************************************************************
 *
 * Startup
 *
 *****************************************************************/

console.log("Fuel Quality Dashboard Started");

/*****************************************************************
 *
 * IMU Charts
 *
 *****************************************************************/

const MAX_POINTS = 200;

let accelChart = null;
let gyroChart = null;

const accelData = {
    labels: [],
    x: [],
    y: [],
    z: []
};

const gyroData = {
    labels: [],
    x: [],
    y: [],
    z: []
};

/*****************************************************************
 *
 * Create Charts
 *
 *****************************************************************/

function createCharts()
{

    const accelCtx =
        document
        .getElementById("accelChart")
        .getContext("2d");

    accelChart = new Chart(accelCtx,{

        type:"line",

        data:{

            labels:[],

            datasets:[

                {

                    label:"Accel X",

                    data:[],

                    borderColor:"#ef4444",

                    tension:0.2,

                    pointRadius:0

                },

                {

                    label:"Accel Y",

                    data:[],

                    borderColor:"#22c55e",

                    tension:0.2,

                    pointRadius:0

                },

                {

                    label:"Accel Z",

                    data:[],

                    borderColor:"#3b82f6",

                    tension:0.2,

                    pointRadius:0

                }

            ]

        },

        options:{

            animation:false,

            responsive:true,

            maintainAspectRatio:false,

            scales:{

                x:{

                    display:false

                }

            }

        }

    });

    const gyroCtx =
        document
        .getElementById("gyroChart")
        .getContext("2d");

    gyroChart = new Chart(gyroCtx,{

        type:"line",

        data:{

            labels:[],

            datasets:[

                {

                    label:"Gyro X",

                    data:[],

                    borderColor:"#ef4444",

                    tension:0.2,

                    pointRadius:0

                },

                {

                    label:"Gyro Y",

                    data:[],

                    borderColor:"#22c55e",

                    tension:0.2,

                    pointRadius:0

                },

                {

                    label:"Gyro Z",

                    data:[],

                    borderColor:"#3b82f6",

                    tension:0.2,

                    pointRadius:0

                }

            ]

        },

        options:{

            animation:false,

            responsive:true,

            maintainAspectRatio:false,

            scales:{

                x:{

                    display:false

                }

            }

        }

    });

}

/*****************************************************************
 *
 * Push New Sample
 *
 *****************************************************************/

function pushSample(sample)
{

    const label =
        "";

    accelChart.data.labels.push(label);

    accelChart.data.datasets[0].data.push(sample.ax);
    accelChart.data.datasets[1].data.push(sample.ay);
    accelChart.data.datasets[2].data.push(sample.az);

    gyroChart.data.labels.push(label);

    gyroChart.data.datasets[0].data.push(sample.gx);
    gyroChart.data.datasets[1].data.push(sample.gy);
    gyroChart.data.datasets[2].data.push(sample.gz);

    if(accelChart.data.labels.length>MAX_POINTS)
    {

        accelChart.data.labels.shift();

        accelChart.data.datasets.forEach(d=>d.data.shift());

    }

    if(gyroChart.data.labels.length>MAX_POINTS)
    {

        gyroChart.data.labels.shift();

        gyroChart.data.datasets.forEach(d=>d.data.shift());

    }

    accelChart.update("none");

    gyroChart.update("none");

}

async function loadHeartbeat()
{
    try
    {
        const response =
            await fetch("/api/heartbeat");

        const hb =
            await response.json();

        document.getElementById(
            "heartbeatValue"
        ).innerHTML =
        "HB : " + hb.heartbeat;

        if(hb.missed > 0)
        {
            console.log(
                "Missed Heartbeats : " + hb.missed
            );
        }
    }
    catch(err)
    {
        console.error(err);
    }
}

/*****************************************************************
 *
 * Poll IMU REST API
 *
 *****************************************************************/

async function loadImu()
{

    try
    {

        const response =
            await fetch("/api/imu_capture");

        const data =
            await response.json();

        if(data.length===0)
            return;

        accelChart.data.labels=[];

        gyroChart.data.labels=[];

        accelChart.data.datasets.forEach(d=>d.data=[]);

        gyroChart.data.datasets.forEach(d=>d.data=[]);

        data.forEach(sample=>{

            pushSample(sample);

        });

    }

    catch(err)
    {

        console.error(err);

    }

}

/*****************************************************************
 *
 * WebSocket (if supported)
 *
 *****************************************************************/

try
{

    if(window.WebUI)
    {

        WebUI.onMessage("imu_sample",(sample)=>{

            pushSample(sample);

        });

        console.log(
            "Using WebSocket IMU stream."
        );

    }

}
catch(e)
{

    console.log(
        "WebSocket unavailable, using REST."
    );

}

/*****************************************************************
 *
 * Initialise
 *
 *****************************************************************/

if(window.Chart)
{

    createCharts();

    loadImu();

    setInterval(loadImu,200);

    console.log(
        "IMU Dashboard Ready."
    );

}
else
{

    console.log(
        "Chart.js not loaded (offline?) — IMU charts disabled."
    );

}