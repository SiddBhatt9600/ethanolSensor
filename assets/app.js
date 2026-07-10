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

function refreshDashboard(){

    loadLiveData();

    loadButtonCapture();

}

refreshDashboard();

setInterval(refreshDashboard,1000);