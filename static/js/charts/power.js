var PowerCharts = (function () {
    var voltageChart = null;
    var currentChart = null;
    var powerChart = null;

    var CH_COLORS = ['#ffd166', '#00b4d8'];
    var CH_NAMES = ['Solar', 'Repeater'];

    var TT = { trigger: 'axis', backgroundColor: 'rgba(30,30,50,0.95)', borderColor: '#555', textStyle: { color: '#e0e0e0' } };
    var AX = { axisLine: { lineStyle: { color: '#888' } }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } } };

    function makeOption(yName) {
        return {
            backgroundColor: 'transparent',
            tooltip: TT,
            legend: {
                data: CH_NAMES,
                textStyle: { fontSize: 11, color: '#aaa' },
                top: 0,
            },
            xAxis: { type: 'time', axisLine: AX.axisLine },
            yAxis: { type: 'value', name: yName, nameTextStyle: { color: '#888' }, axisLine: AX.axisLine, splitLine: AX.splitLine },
            dataZoom: [
                { type: 'inside', xAxisIndex: 0 },
                { type: 'slider', xAxisIndex: 0, height: 20, bottom: 5 },
            ],
            series: CH_NAMES.map(function (name, i) {
                return {
                    name: name,
                    type: 'line',
                    smooth: true,
                    symbol: 'none',
                    lineStyle: { width: 2, color: CH_COLORS[i] },
                    itemStyle: { color: CH_COLORS[i] },
                    data: [],
                };
            }),
            grid: { left: 50, right: 16, top: 30, bottom: 50 },
        };
    }

    function init(voltageEl, currentEl, powerEl) {
        voltageChart = echarts.init(voltageEl);
        currentChart = echarts.init(currentEl);
        powerChart = echarts.init(powerEl);
        voltageChart.setOption(makeOption('V'));
        currentChart.setOption(makeOption('mA'));
        powerChart.setOption(makeOption('mW'));
    }

    function update(data) {
        if (!voltageChart) return;
        if (!data.timestamps.length) return;

        // Solar = ch1 (device channel 2), Repeater = ch2 (device channel 3)
        var voltageSeries = [[], []];
        var currentSeries = [[], []];
        var powerSeries = [[], []];

        for (var i = 0; i < data.timestamps.length; i++) {
            var t = data.timestamps[i] * 1000;
            voltageSeries[0].push([t, data.ch2_voltage[i]]);
            voltageSeries[1].push([t, data.ch1_voltage[i]]);
            currentSeries[0].push([t, data.ch2_current[i]]);
            currentSeries[1].push([t, data.ch1_current[i]]);
            powerSeries[0].push([t, data.ch2_power[i]]);
            powerSeries[1].push([t, data.ch1_power[i]]);
        }

        voltageChart.setOption({
            series: voltageSeries.map(function (d) { return { data: d }; }),
        });
        currentChart.setOption({
            series: currentSeries.map(function (d) { return { data: d }; }),
        });
        powerChart.setOption({
            series: powerSeries.map(function (d) { return { data: d }; }),
        });
    }

    function resize() {
        if (voltageChart) voltageChart.resize();
        if (currentChart) currentChart.resize();
        if (powerChart) powerChart.resize();
    }

    return { init: init, update: update, resize: resize };
})();
