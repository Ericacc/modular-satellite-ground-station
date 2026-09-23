import openmct from 'openmct';
import './node_modules/openmct/dist/snowTheme.css';
import GroundStationPlugin from './aegissat-plugin.js';

const apiBase =
  import.meta.env.VITE_GROUND_STATION_API ||
  'http://127.0.0.1:8000';

openmct.install(openmct.plugins.LocalStorage());
openmct.install(openmct.plugins.MyItems());
openmct.install(openmct.plugins.UTCTimeSystem());

openmct.install(openmct.plugins.LADTable());
openmct.install(openmct.plugins.TelemetryTable());
openmct.install(openmct.plugins.Plot());

// Tema claro
openmct.install(openmct.plugins.Snow());

openmct.install(GroundStationPlugin(apiBase));

const thirtyMinutes = 30 * 60 * 1000;

openmct.time.setTimeSystem('utc');
openmct.time.setClock('local');

openmct.time.setClockOffsets({
  start: -thirtyMinutes,
  end: 0
});

openmct.start(document.getElementById('openmct'));