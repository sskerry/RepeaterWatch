var PiCpuChart = (function () {
    var chart = null;

    var TT = { trigger: 'axis', backgroundColor: 'rgba(30,30,50,0.95)', borderColor: '#555', textStyle: { color: '#e0e0e0' } };
    var AX = { axisLine: { lineStyle: { color: '#888' } }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } } };

    function init(el) {
        chart = echarts.init(el);
        chart.setOption({
            backgroundColor: 'transparent',
            tooltip: TT,
            legend: {
                data: ['CPU %', 'Load 1m', 'Load 5m', 'Load 15m'],
                textStyle: { fontSize: 11, color: '#aaa' },
                top: 0,
            },
            xAxis: { type: 'time', axisLine: AX.axisLine },
            yAxis: [
                { type: 'value', name: '%', max: 100, nameTextStyle: { color: '#888' }, axisLine: AX.axisLine, splitLine: AX.splitLine },
                { type: 'value', name: 'Load', nameTextStyle: { color: '#888' }, axisLine: AX.axisLine, splitLine: { show: false } },
            ],
            dataZoom: [
                { type: 'inside', xAxisIndex: 0 },
                { type: 'slider', xAxisIndex: 0, height: 20, bottom: 5 },
            ],
            series: [
                { name: 'CPU %', type: 'line', smooth: true, symbol: 'none', yAxisIndex: 0, areaStyle: { opacity: 0.3 }, lineStyle: { width: 2, color: '#00b4d8' }, itemStyle: { color: '#00b4d8' }, data: [] },
                { name: 'Load 1m', type: 'line', smooth: true, symbol: 'none', yAxisIndex: 1, lineStyle: { width: 1.5, color: '#ffd166' }, itemStyle: { color: '#ffd166' }, data: [] },
                { name: 'Load 5m', type: 'line', smooth: true, symbol: 'none', yAxisIndex: 1, lineStyle: { width: 1.5, color: '#06d6a0' }, itemStyle: { color: '#06d6a0' }, data: [] },
                { name: 'Load 15m', type: 'line', smooth: true, symbol: 'none', yAxisIndex: 1, lineStyle: { width: 1.5, color: '#ef476f' }, itemStyle: { color: '#ef476f' }, data: [] },
            ],
            grid: { left: 50, right: 50, top: 30, bottom: 50 },
        });
    }

    function update(data) {
        if (!chart || !data.timestamps.length) return;
        var cpu = [], l1 = [], l5 = [], l15 = [];
        for (var i = 0; i < data.timestamps.length; i++) {
            var t = data.timestamps[i] * 1000;
            cpu.push([t, data.cpu_percent[i]]);
            l1.push([t, data.load_1[i]]);
            l5.push([t, data.load_5[i]]);
            l15.push([t, data.load_15[i]]);
        }
        chart.setOption({ series: [{ data: cpu }, { data: l1 }, { data: l5 }, { data: l15 }] });
    }

    return { init: init, update: update, resize: function () { if (chart) chart.resize(); } };
})();

var PiMemoryChart = (function () {
    var chart = null;

    var TT = { trigger: 'axis', backgroundColor: 'rgba(30,30,50,0.95)', borderColor: '#555', textStyle: { color: '#e0e0e0' }, valueFormatter: function (v) { return v != null ? v + '%' : '--'; } };
    var AX = { axisLine: { lineStyle: { color: '#888' } }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } } };

    function init(el) {
        chart = echarts.init(el);
        chart.setOption({
            backgroundColor: 'transparent',
            tooltip: TT,
            legend: {
                data: ['RAM %', 'Swap %'],
                textStyle: { fontSize: 11, color: '#aaa' },
                top: 0,
            },
            xAxis: { type: 'time', axisLine: AX.axisLine },
            yAxis: { type: 'value', name: '%', max: 100, nameTextStyle: { color: '#888' }, axisLine: AX.axisLine, splitLine: AX.splitLine },
            dataZoom: [
                { type: 'inside', xAxisIndex: 0 },
                { type: 'slider', xAxisIndex: 0, height: 20, bottom: 5 },
            ],
            series: [
                { name: 'RAM %', type: 'line', smooth: true, symbol: 'none', areaStyle: { opacity: 0.3 }, lineStyle: { width: 2, color: '#06d6a0' }, itemStyle: { color: '#06d6a0' }, data: [] },
                { name: 'Swap %', type: 'line', smooth: true, symbol: 'none', areaStyle: { opacity: 0.2 }, lineStyle: { width: 2, color: '#ffd166' }, itemStyle: { color: '#ffd166' }, data: [] },
            ],
            grid: { left: 50, right: 16, top: 30, bottom: 50 },
        });
    }

    function update(data) {
        if (!chart || !data.timestamps.length) return;
        var ram = [], swap = [];
        for (var i = 0; i < data.timestamps.length; i++) {
            var t = data.timestamps[i] * 1000;
            ram.push([t, data.mem_percent[i]]);
            var swapPct = (data.swap_total_mb[i] > 0)
                ? Math.round(data.swap_used_mb[i] / data.swap_total_mb[i] * 100 * 10) / 10
                : 0;
            swap.push([t, swapPct]);
        }
        chart.setOption({ series: [{ data: ram }, { data: swap }] });
    }

    return { init: init, update: update, resize: function () { if (chart) chart.resize(); } };
})();

var PiTempChart = (function () {
    var chart = null;

    var TT = { trigger: 'axis', backgroundColor: 'rgba(30,30,50,0.95)', borderColor: '#555', textStyle: { color: '#e0e0e0' } };
    var AX = { axisLine: { lineStyle: { color: '#888' } }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } } };

    function init(el) {
        chart = echarts.init(el);
        chart.setOption({
            backgroundColor: 'transparent',
            tooltip: TT,
            xAxis: { type: 'time', axisLine: AX.axisLine },
            yAxis: { type: 'value', name: '\u00b0C', nameTextStyle: { color: '#888' }, axisLine: AX.axisLine, splitLine: AX.splitLine },
            dataZoom: [
                { type: 'inside', xAxisIndex: 0 },
                { type: 'slider', xAxisIndex: 0, height: 20, bottom: 5 },
            ],
            series: [{
                name: 'CPU Temp',
                type: 'line',
                smooth: true,
                symbol: 'none',
                areaStyle: { opacity: 0.2, color: '#ef476f' },
                lineStyle: { width: 2, color: '#ef476f' },
                itemStyle: { color: '#ef476f' },
                data: [],
            }],
            grid: { left: 50, right: 16, top: 20, bottom: 50 },
        });
    }

    function update(data) {
        if (!chart || !data.timestamps.length) return;
        var series = [];
        for (var i = 0; i < data.timestamps.length; i++) {
            series.push([data.timestamps[i] * 1000, data.cpu_temp[i]]);
        }
        chart.setOption({ series: [{ data: series }] });
    }

    return { init: init, update: update, resize: function () { if (chart) chart.resize(); } };
})();

var PiDiskChart = (function () {
    var chart = null;

    var TT = { trigger: 'axis', backgroundColor: 'rgba(30,30,50,0.95)', borderColor: '#555', textStyle: { color: '#e0e0e0' }, valueFormatter: function (v) { return v != null ? v + '%' : '--'; } };
    var AX = { axisLine: { lineStyle: { color: '#888' } }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } } };

    function init(el) {
        chart = echarts.init(el);
        chart.setOption({
            backgroundColor: 'transparent',
            tooltip: TT,
            xAxis: { type: 'time', axisLine: AX.axisLine },
            yAxis: { type: 'value', name: '%', max: 100, nameTextStyle: { color: '#888' }, axisLine: AX.axisLine, splitLine: AX.splitLine },
            dataZoom: [
                { type: 'inside', xAxisIndex: 0 },
                { type: 'slider', xAxisIndex: 0, height: 20, bottom: 5 },
            ],
            series: [{
                name: 'Disk Usage',
                type: 'line',
                smooth: true,
                symbol: 'none',
                areaStyle: { opacity: 0.3, color: '#ffd166' },
                lineStyle: { width: 2, color: '#ffd166' },
                itemStyle: { color: '#ffd166' },
                data: [],
            }],
            grid: { left: 50, right: 16, top: 20, bottom: 50 },
        });
    }

    function update(data) {
        if (!chart || !data.timestamps.length) return;
        var series = [];
        for (var i = 0; i < data.timestamps.length; i++) {
            series.push([data.timestamps[i] * 1000, data.disk_percent[i]]);
        }
        chart.setOption({ series: [{ data: series }] });
    }

    return { init: init, update: update, resize: function () { if (chart) chart.resize(); } };
})();

var PiDiskIoChart = (function () {
    var chart = null;

    var TT = { trigger: 'axis', backgroundColor: 'rgba(30,30,50,0.95)', borderColor: '#555', textStyle: { color: '#e0e0e0' }, valueFormatter: function (v) { return v != null ? v + ' KB/s' : '--'; } };
    var AX = { axisLine: { lineStyle: { color: '#888' } }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } } };

    function init(el) {
        chart = echarts.init(el);
        chart.setOption({
            backgroundColor: 'transparent',
            tooltip: TT,
            legend: {
                data: ['Read', 'Write'],
                textStyle: { fontSize: 11, color: '#aaa' },
                top: 0,
            },
            xAxis: { type: 'time', axisLine: AX.axisLine },
            yAxis: { type: 'value', name: 'KB/s', nameTextStyle: { color: '#888' }, axisLine: AX.axisLine, splitLine: AX.splitLine },
            dataZoom: [
                { type: 'inside', xAxisIndex: 0 },
                { type: 'slider', xAxisIndex: 0, height: 20, bottom: 5 },
            ],
            series: [
                { name: 'Read', type: 'line', smooth: true, symbol: 'none', lineStyle: { width: 2, color: '#06d6a0' }, itemStyle: { color: '#06d6a0' }, data: [] },
                { name: 'Write', type: 'line', smooth: true, symbol: 'none', lineStyle: { width: 2, color: '#ef476f' }, itemStyle: { color: '#ef476f' }, data: [] },
            ],
            grid: { left: 50, right: 16, top: 30, bottom: 50 },
        });
    }

    function update(data) {
        if (!chart || !data.timestamps.length) return;
        var rd = [], wr = [];
        for (var i = 0; i < data.timestamps.length; i++) {
            var t = data.timestamps[i] * 1000;
            rd.push([t, data.read_kbs[i]]);
            wr.push([t, data.write_kbs[i]]);
        }
        chart.setOption({ series: [{ data: rd }, { data: wr }] });
    }

    return { init: init, update: update, resize: function () { if (chart) chart.resize(); } };
})();

var PiNetworkChart = (function () {
    var chart = null;

    var TT = { trigger: 'axis', backgroundColor: 'rgba(30,30,50,0.95)', borderColor: '#555', textStyle: { color: '#e0e0e0' }, valueFormatter: function (v) { return v != null ? v + ' KB/s' : '--'; } };
    var AX = { axisLine: { lineStyle: { color: '#888' } }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } } };

    function init(el) {
        chart = echarts.init(el);
        chart.setOption({
            backgroundColor: 'transparent',
            tooltip: TT,
            legend: {
                data: ['Sent', 'Received'],
                textStyle: { fontSize: 11, color: '#aaa' },
                top: 0,
            },
            xAxis: { type: 'time', axisLine: AX.axisLine },
            yAxis: { type: 'value', name: 'KB/s', nameTextStyle: { color: '#888' }, axisLine: AX.axisLine, splitLine: AX.splitLine },
            dataZoom: [
                { type: 'inside', xAxisIndex: 0 },
                { type: 'slider', xAxisIndex: 0, height: 20, bottom: 5 },
            ],
            series: [
                { name: 'Sent', type: 'line', smooth: true, symbol: 'none', lineStyle: { width: 2, color: '#00b4d8' }, itemStyle: { color: '#00b4d8' }, data: [] },
                { name: 'Received', type: 'line', smooth: true, symbol: 'none', lineStyle: { width: 2, color: '#ffd166' }, itemStyle: { color: '#ffd166' }, data: [] },
            ],
            grid: { left: 50, right: 16, top: 30, bottom: 50 },
        });
    }

    function update(data) {
        if (!chart || !data.timestamps.length) return;
        var sent = [], recv = [];
        for (var i = 0; i < data.timestamps.length; i++) {
            var t = data.timestamps[i] * 1000;
            sent.push([t, data.sent_kbs[i]]);
            recv.push([t, data.recv_kbs[i]]);
        }
        chart.setOption({ series: [{ data: sent }, { data: recv }] });
    }

    return { init: init, update: update, resize: function () { if (chart) chart.resize(); } };
})();
