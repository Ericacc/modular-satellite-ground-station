# Modular Satellite Ground Station

Software implementation of a modular ground station for CubeSat communication and telemetry processing.

The system is designed to run on a Raspberry Pi and combines software-defined radio reception, satellite pass prediction, telemetry processing, data storage and visualisation. Satellite-specific decoding can be integrated through external tools such as `gr-satellites`, while the remaining components are kept independent from a specific mission.

## Main Components

- Satellite catalogue and reception profiles
- Pass prediction using TLE data
- RTL-SDR receiver control
- RF measurements and signal monitoring
- Doppler correction support
- KISS and AX.25 frame handling
- Integration with GNU Radio and `gr-satellites`
- Telemetry ingestion and storage
- InfluxDB integration
- Open MCT visualisation
- Reception scheduling
- Simulation and laboratory testing
- Automated software tests and RTL-SDR hardware checks


## Architecture

The software separates satellite reception, decoding, storage and visualisation.

    Satellite
        |
        v
    RTL-SDR
        |
        v
    GNU Radio / gr-satellites
        |
        v
    KISS / Decoded Telemetry
        |
        v
    Ground Station API
        |
        +----> InfluxDB
        |
        +----> Open MCT

The reception core can operate independently of a satellite-specific telemetry parser. Raw frames can therefore be preserved when decoded telemetry is not available.

## Requirements

The software is intended for Linux systems, including Raspberry Pi OS and Debian-based distributions.

Main software dependencies:

- Python 3
- RTL-SDR tools
- GNU Radio
- gr-satellites
- Docker
- InfluxDB
- Node.js
- Open MCT



## Installation

Create the Python environment:

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e ".[test]"

Create the local configuration:

    cp .env.example .env

The .env file contains the local ground-station configuration and is excluded from version control.

## Configuration

General configuration is provided through the .env file. It includes station coordinates, receiver settings, Doppler correction, catalogue sources, InfluxDB connection and API settings.

Satellite reception profiles are stored in config/satellites.json. Reception targets are selected in config/reception_targets.json.

## Running the Ground Station

Start the API directly with:

    source .venv/bin/activate
    uvicorn aegissat.api:app --host 0.0.0.0 --port 8000

Alternatively, start the configured ground-station services with:

    ./start_ground_station.sh

Systemd service templates can be installed with:

    ./scripts/install_services.sh

## Open MCT

Install and start the visualisation interface with:

    cd openmct
    npm install
    npm start

By default, Open MCT connects to the API at http://127.0.0.1:8000. A different API address can be configured in openmct/.env.

## Tests

Run the Python test suite with:

    .venv/bin/python -m pytest -q

Run the complete project validation with:

    ./run_all_tests.sh

An RTL-SDR hardware check can be included when `rtl_test` is available:

    ./run_all_tests.sh --hardware

Generated test reports are excluded from version control.

## Recorded-Signal Validation

Previously recorded satellite signals can be used to test the reception and decoding chain without requiring a live pass. The recording is processed with `gr-satellites` and the resulting frames are passed to the ground-station processing chain.

Recordings can be placed in `data/recordings/` or provided using their full path.

    ./run_recording_test.sh /path/to/recording.wav "FUNcube-1" ao-73

Known recording profiles can be defined in `config/recording_tests.json`, allowing the decoder and satellite identifier to be selected from the recording filename. Recordings, decoded data and generated test outputs are excluded from version control.


## Laboratory Simulation

A laboratory telemetry simulation is included to test the processing chain without a satellite signal. The current simulation uses a provisional telemetry format and is kept separate from the generic reception workflow.

## Project Structure

    aegissat/       Ground-station Python package
    config/         Reception and satellite configuration
    deployment/     Systemd service templates
    openmct/        Visualisation interface
    radio/          Radio and modem utilities
    scripts/        Installation, reception and validation tools
    tests/          Automated tests

Runtime data, recordings, logs, local environment files and generated outputs are excluded from version control.
