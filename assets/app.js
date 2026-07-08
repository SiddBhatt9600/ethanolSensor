async function loadData() {
    const response = await fetch("/api/sensors");
    const data = await response.json();

    const tbody = document.querySelector("#sensorTable tbody");
    tbody.innerHTML = "";

    data.forEach(sensor => {

        const readings = sensor.sensorReadings;

        const temp = readings.temp.at(-1);
        const ethanol = readings.ethanolLevels.at(-1);
        const density = readings.density.at(-1);
        const water = readings.wif.at(-1);

        tbody.innerHTML += `
        <tr>
            <td>${sensor.timestamp}</td>
            <td>${ethanol}</td>
            <td>${temp}</td>
            <td>${density}</td>
            <td>${water}</td>
        </tr>`;
    });
}

loadData();
setInterval(loadData, 1000);