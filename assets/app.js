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
 * Turbidity card — shows the AI model's own calibrated turbidity
 * feature (sensorManager.calibrate_turbidity()), not the raw board
 * index. On this scale LOW = clean, HIGH = dirty, matching the
 * bands the model was trained on: clean ~0-6, suspect ~12-30,
 * adulterated ~40-100 (see calibrate_turbidity()'s docstring).
 *
 *****************************************************************/

const TURBIDITY_CLEAN_MAX = 12;
const TURBIDITY_SUSPECT_MAX = 40;

function updateTurbidityCard(value) {

    const el = document.getElementById("turbidityValue");

    el.classList.remove(
        "verdict-good-text", "verdict-suspect-text", "verdict-bad-text"
    );

    if (typeof value !== "number") {
        el.innerHTML = "--";
        return;
    }

    el.innerHTML = display(value);

    if (value <= TURBIDITY_CLEAN_MAX) el.classList.add("verdict-good-text");
    else if (value <= TURBIDITY_SUSPECT_MAX) el.classList.add("verdict-suspect-text");
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
            await fetch("/api/sensors", { cache: "no-store" });

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

// Tracks the most recently DISPLAYED capture's timestamp, and
// whether we're mid-capture after a trigger, so loadButtonCapture()
// can tell "brand new data landed" apart from "still the same old
// capture from before the button was pressed" and never re-show
// stale numbers as if they were the new reading. The panel itself is
// always visible now (never hidden). It shows placeholders until the
// first real reading, then updates in place; a "pending" state just
// dims the details section briefly instead of hiding anything, so it
// never looks broken or frozen while a fresh reading comes in. The
// 5-sample table and the average-of-5 stats used to both show here
// too, but the average is exactly what the 5 cards further down the
// page already show, so that duplicate block was dropped and the raw
// samples now live behind a collapsed "show details" toggle instead
// of always taking up space.
let lastSeenCaptureTimestamp = null;
let capturePending = false;
let pendingSinceTimestamp = null;
let lastCaptureLandedAt = null;

function capturePlaceholderRowsHtml()
{
    let rows = "";
    for (let i = 1; i <= 5; i++)
    {
        rows += `<tr><td>${i}</td><td>--</td><td>--</td><td>--</td><td>--</td><td>--</td></tr>`;
    }
    return rows;
}

async function triggerCapture()
{

    const btn = document.getElementById("captureNowBtn");
    const result = document.getElementById("captureTriggerResult");
    const details = document.getElementById("captureDetails");

    // Dim the panel immediately (don't wait for the next 1s poll) so
    // it's obvious a fresh reading is on the way, but keep the last
    // known numbers on screen instead of hiding/blanking them.
    capturePending = true;
    pendingSinceTimestamp = lastSeenCaptureTimestamp;
    details.classList.add("pending");
    document.getElementById("captureStatus").innerHTML =
        "Taking a fresh reading…";

    btn.disabled = true;
    result.innerHTML = "Taking a fresh reading…";

    try
    {

        const response =
            await fetch("/api/button_capture/trigger", { method: "POST", cache: "no-store" });

        const data =
            await response.json();

        if (data.capture_started === false)
        {
            result.innerHTML =
                "Already taking a reading, one moment.";
        }
        else
        {
            result.innerHTML =
                "Reading started. This updates on its own in a " +
                "couple of seconds.";
        }

    }

    catch(err)
    {

        console.error("Capture trigger API:", err);
        result.innerHTML = "Couldn't start the reading. Please try again.";

        // The trigger itself failed, so nothing is actually in
        // progress, don't get stuck dimming the panel forever.
        capturePending = false;
        loadButtonCapture();

    }

    setTimeout(() => { btn.disabled = false; }, 2000);

}

async function loadButtonCapture()
{

    try
    {

        const response =
            await fetch("/api/button_capture", { cache: "no-store" });

        const capture =
            await response.json();

        const details =
            document.getElementById(
                "captureDetails"
            );

        const tbody =
            document.querySelector(
                "#captureTable tbody"
            );

        const lastUpdateEl =
            document.getElementById(
                "captureLastUpdate"
            );

        const isEmpty =

            !capture ||

            !capture.samples ||

            capture.samples.length === 0;

        // Still the pre-trigger capture (or nothing yet), a new one
        // is running but hasn't landed. Leave whatever is already on
        // screen as-is (placeholders or the last real reading) and
        // just keep it dimmed, instead of clearing it.
        const stillPending =

            capturePending &&

            (isEmpty || capture.timestamp === pendingSinceTimestamp);

        if (stillPending)
        {

            document.getElementById(
                "captureStatus"
            ).innerHTML = "Taking a fresh reading…";

            return;

        }

        details.classList.remove("pending");

        if (isEmpty)
        {

            // Never taken a reading yet, show placeholders instead
            // of an empty box, same idea as the "--" on the cards
            // above.
            capturePending = false;

            tbody.innerHTML = capturePlaceholderRowsHtml();

            document.getElementById(
                "captureStatus"
            ).innerHTML =

            "No reading yet. Press \"Capture Now\" below to take one.";

            lastUpdateEl.innerHTML = "";

            return;

        }

        capturePending = false;

        // Only reset the "landed at" clock when this is genuinely a
        // different capture than the one already on screen, polling
        // re-runs this branch every second even when nothing changed,
        // and resetting the clock every time would make "Updated Xs
        // ago" freeze at "just now" forever instead of counting up.
        if (capture.timestamp !== lastSeenCaptureTimestamp)
        {
            lastCaptureLandedAt = Date.now();
        }

        lastSeenCaptureTimestamp = capture.timestamp;

        document.getElementById(
            "captureStatus"
        ).innerHTML =

        `Latest: ${capture.average.temp}°C, ` +
        `${capture.average.ethanol}% ethanol, ` +
        `${capture.average.density} kg/m³ density, ` +
        `water ${capture.average.wif}, ` +
        `turbidity ${capture.average.turbidity_raw}`;

        tbody.innerHTML = "";

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

        const secondsAgo = Math.round((Date.now() - lastCaptureLandedAt) / 1000);

        lastUpdateEl.innerHTML =
            secondsAgo <= 1 ? "Updated just now" : `Updated ${secondsAgo}s ago`;

    }

    catch(err)
    {

        console.error(err);

        document.getElementById(
            "captureStatus"
        ).innerHTML = "Couldn't reach the device. Retrying…";

    }

}

/*****************************************************************
 *
 * Measured Density (user input — no board density sensor)
 *
 *****************************************************************/

async function loadDensityStatus() {

    try {

        const response = await fetch("/api/user/density", { cache: "no-store" });
        const d = await response.json();

        const statusEl = document.getElementById("densityStatus");

        if (!d || d.density === null || d.density === undefined) {

            statusEl.innerHTML =
            "No density entered yet, needed before a result can show.";

            return;

        }

        const setTime = new Date(d.timestamp).toLocaleTimeString();

        statusEl.innerHTML =
        `Current: <b>${d.density} kg/m³</b> (set ${setTime})`;

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

        const response = await fetch(
            `/api/user/density?density=${encodeURIComponent(value)}`, {

            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({density: value}),
            cache: "no-store"

        });

        const d = await response.json();

        if (d.error) {

            result.innerHTML = `Failed: ${d.error}`;
            return;

        }

        if (d.detail) {
            const firstIssue = Array.isArray(d.detail) ? d.detail[0] : d.detail;
            result.innerHTML =
                `Failed: the device rejected the request ` +
                `(${firstIssue && firstIssue.msg ? firstIssue.msg : JSON.stringify(d.detail)}).`;
            return;

        }

        // Don't trust the POST response body alone for what actually
        // took effect — some backends ack a POST without echoing the
        // real state, which is how a submission that silently failed
        // to parse ends up showing "Density set to undefined kg/m³"
        // even though nothing changed. Re-read the device's own
        // current density (the same GET the dashboard already trusts
        // after a restart) and confirm it actually matches what was
        // just typed before calling this a success.
        const check = await fetch("/api/user/density", { cache: "no-store" });
        const current = await check.json();

        if (current && typeof current.density === "number"
                && Math.abs(current.density - value) < 0.01) {

            result.innerHTML = `Density set to ${current.density} kg/m³.`;

        }

        else {

            result.innerHTML =
            `Submitted ${value} kg/m³, but the device still reports ` +
            `${current && current.density !== undefined
                ? current.density : "no density"} kg/m³. The ` +
            `submission may not have been received. Check the device ` +
            `log for a "set_user_density called" line.`;

        }

        loadDensityStatus();

    }

    catch(err) {

        console.error("Density submit API:", err);
        result.innerHTML = "Submit failed. See console.";

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

const PARAM_NAMES = {
    temp: "Fuel temperature",
    ethanol: "Ethanol level",
    wif: "Water level",
    turbidity: "Cloudiness",
    density: "Density",
};

function friendlyParamName(parameter) {
    return PARAM_NAMES[parameter] || parameter;
}

// Turns the raw GOOD/SUSPECT/ADULTERATED percentage breakdown into a
// plain sentence. When the call was clear-cut (top result well ahead
// of the rest) the confidence number above already says enough, so
// this stays empty rather than repeating it. It only speaks up when
// there was a real second-place contender, which is the case worth
// knowing about.
function describeProbs(probs, verdict) {

    if (!probs) return "";

    const entries = Object.entries(probs)
        .sort((a, b) => b[1] - a[1]);

    const [, topShare] = entries[0];
    const [runnerUp, runnerUpShare] = entries[1];

    if (runnerUpShare < 0.2 || topShare - runnerUpShare > 0.4) {
        return "";
    }

    return `It was a close call. Some signs also pointed toward ` +
           `${runnerUp} (${(runnerUpShare * 100).toFixed(0)}%).`;

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

        const response = await fetch("/api/ai/current", { cache: "no-store" });
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
        ? "We don't have a density reading for this yet. Enter one " +
          "above, then take a new reading to see your fuel quality " +
          "result."
        : `${(v.confidence * 100).toFixed(0)}% confident`;

        // A plain sentence instead of a raw per-class percentage
        // breakdown — only worth showing when it wasn't a clear-cut
        // call, so a close second place is visible instead of buried
        // in three side-by-side numbers.
        probsEl.innerHTML = describeProbs(v.probs, v.verdict);

        if (v.blend) {

            blendEl.innerHTML = v.blend.in_spec

            ? `Fuel type: ${v.blend.nearest} (${v.blend.measured}% ` +
              `ethanol, right where it should be) ✓`

            : `⚠ Ethanol reading (${v.blend.measured}%) doesn't match ` +
              `any standard fuel type (closest is ${v.blend.nearest})`;

        }

        else {

            blendEl.innerHTML = "";

        }

        if (v.mileage) {

            const m = v.mileage;

            mileageEl.innerHTML =

            `<b>${m.estimated_kmpl} km/l</b> estimated ` +
            `(normally ${m.baseline_kmpl} km/l, ` +
            `${m.total_penalty_pct}% lower)<br>` +

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

            "<b>⚠ What we noticed:</b><br>" +

            v.anomalies.map(a =>

                a.type === "quality"
                ? a.reason
                : `${friendlyParamName(a.parameter)} just changed a lot. ` +
                  `It's now ${a.value}, usually around ${a.baseline_mean}.`

            ).join("<br>");

        }

        else {

            anomEl.style.display = "none";

            anomEl.innerHTML = "";

        }

        updateWaterCard(v);
        updateTurbidityCard(v.reading ? v.reading.turbidity : null);
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

// Browsers throttle setInterval timers hard while a tab is in the
// background (sometimes down to once a minute or less), which made
// the dashboard look frozen after switching away and back — force an
// immediate refresh the moment this tab becomes visible again instead
// of waiting for the next throttled tick.
document.addEventListener("visibilitychange", () => {

    if (document.visibilityState === "visible") {
        refreshDashboard();
    }

});

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
            await fetch("/api/heartbeat", { cache: "no-store" });

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
            await fetch("/api/imu_capture", { cache: "no-store" });

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