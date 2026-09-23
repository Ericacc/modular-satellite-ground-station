# Open MCT integration

This directory is a complete minimal Open MCT application. It displays generic
RF metrics and explicitly labelled AegisSat simulation fields.

```bash
npm install
npm start
```

The default backend is `http://127.0.0.1:8000`. To use a different backend,
copy the example environment file and set the API address:

```bash
cp .env.example .env
```

```env
VITE_GROUND_STATION_API=http://127.0.0.1:8000
```

Real satellite frames are never decoded with the simulated AegisSat protocol.
