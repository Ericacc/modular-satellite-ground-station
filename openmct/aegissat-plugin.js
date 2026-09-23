export default function GroundStationPlugin(
  apiBase = 'http://127.0.0.1:8000'
) {
  return function install(openmct) {
    const namespace = 'groundstation';
    const rootKey = 'ground-station';
    const telemetryType = 'groundstation.telemetry';
    const groupType = 'groundstation.group';

    const groups = [
      {
        key: 'ground-station-rf',
        name: 'Ground Station RF',
        matches(measurementKey) {
          return [
            'signal_power_dbfs',
            'snr_db',
            'frequency_offset_hz'
          ].includes(measurementKey);
        }
      },
      {
        key: 'reception-session',
        name: 'Reception Session',
        matches(measurementKey) {
          return (
            measurementKey.startsWith('frames_') ||
            measurementKey === 'decode_errors' ||
            measurementKey === 'database_errors'
          );
        }
      },
      {
        key: 'packet-header',
        name: 'Packet Header',
        matches(measurementKey) {
          return measurementKey.startsWith('header.');
        }
      },
      {
        key: 'eps',
        name: 'EPS',
        matches(measurementKey) {
          return measurementKey.startsWith('eps.');
        }
      },
      {
        key: 'adcs',
        name: 'ADCS',
        matches(measurementKey) {
          return measurementKey.startsWith('adcs.');
        }
      },
      {
        key: 'obc',
        name: 'OBC',
        matches(measurementKey) {
          return measurementKey.startsWith('obc.');
        }
      },
      {
        key: 'communications',
        name: 'Communications',
        matches(measurementKey) {
          return measurementKey.startsWith('comms.');
        }
      },
      {
        key: 'payload',
        name: 'Payload',
        matches(measurementKey) {
          return measurementKey.startsWith('payload.');
        }
      },
      {
        key: 'weather',
        name: 'Weather',
        matches(measurementKey) {
          return measurementKey.startsWith('weather.');
        }
      },
      {
        key: 'orbit',
        name: 'Orbit',
        matches(measurementKey) {
          return measurementKey.startsWith('orbit.');
        }
      },
      {
        key: 'flags',
        name: 'Flags',
        matches(measurementKey) {
          return measurementKey.startsWith('flags.');
        }
      },
      {
        key: 'external-satellites',
        name: 'External Satellites',
        matches(measurementKey) {
          return measurementKey.startsWith('external.');
        }
      }
    ];

    function getDictionary() {
      return fetch(`${apiBase}/openmct/dictionary`)
        .then(function (response) {
          if (!response.ok) {
            throw new Error(
              `Dictionary request failed: HTTP ${response.status}`
            );
          }

          return response.json();
        });
    }

    function findGroup(groupKey) {
      return groups.find(function (group) {
        return group.key === groupKey;
      });
    }

    function findMeasurementGroup(measurementKey) {
      return groups.find(function (group) {
        return group.matches(measurementKey);
      });
    }

    openmct.types.addType(telemetryType, {
      name: 'Ground Station Telemetry',
      description:
        'Telemetry received from the modular ground station',
      cssClass: 'icon-telemetry'
    });

    openmct.types.addType(groupType, {
      name: 'Telemetry Group',
      description: 'Group of telemetry parameters',
      cssClass: 'icon-folder'
    });

    openmct.objects.addRoot({
      namespace: namespace,
      key: rootKey
    });

    openmct.objects.addProvider(namespace, {
      get(identifier) {
        if (identifier.key === rootKey) {
          return Promise.resolve({
            identifier: identifier,
            name: 'Modular Ground Station',
            type: 'folder',
            location: 'ROOT'
          });
        }

        const group = findGroup(identifier.key);

        if (group) {
          return Promise.resolve({
            identifier: identifier,
            name: group.name,
            type: groupType,
            location: `${namespace}:${rootKey}`
          });
        }

        return getDictionary()
          .then(function (dictionary) {
            const measurements =
              Array.isArray(dictionary.measurements)
                ? dictionary.measurements
                : [];

            const measurement = measurements.find(
              function (item) {
                return item.key === identifier.key;
              }
            );

            if (!measurement) {
              return undefined;
            }

            const measurementGroup =
              findMeasurementGroup(measurement.key);

            let location = `${namespace}:${rootKey}`;

            if (measurementGroup) {
              location =
                `${namespace}:${measurementGroup.key}`;
            }

            return {
              identifier: identifier,
              name: measurement.name,
              type: telemetryType,
              telemetry: {
                values: [
                  {
                    key: 'utc',
                    source: 'timestamp',
                    name: 'Time',
                    format: 'utc',
                    hints: {
                      domain: 1
                    }
                  },
                  {
                    key: 'value',
                    name: measurement.name,
                    units: measurement.units,
                    format: 'float',
                    hints: {
                      range: 1
                    }
                  }
                ]
              },
              location: location
            };
          });
      }
    });

    openmct.composition.addProvider({
      appliesTo(domainObject) {
        return (
          domainObject.identifier.namespace === namespace &&
          (
            domainObject.identifier.key === rootKey ||
            domainObject.type === groupType
          )
        );
      },

      load(domainObject) {
        if (domainObject.identifier.key === rootKey) {
          return Promise.resolve(
            groups.map(function (group) {
              return {
                namespace: namespace,
                key: group.key
              };
            })
          );
        }

        const group = findGroup(
          domainObject.identifier.key
        );

        if (!group) {
          return Promise.resolve([]);
        }

        return getDictionary()
          .then(function (dictionary) {
            const measurements =
              Array.isArray(dictionary.measurements)
                ? dictionary.measurements
                : [];

            return measurements
              .filter(function (item) {
                return group.matches(item.key);
              })
              .map(function (item) {
                return {
                  namespace: namespace,
                  key: item.key
                };
              });
          });
      }
    });

openmct.composition.addPolicy(function (parent, child) {
  if (parent.type === 'LadTable') {
    console.log('LAD Table parent:', parent);
    console.log('Dragged child:', child);
    console.log(
      'Is telemetry object:',
      openmct.telemetry.isTelemetryObject(child)
    );
    console.log('Telemetry metadata:', child.telemetry);
  }

  return true;
});

    openmct.telemetry.addProvider({
      supportsRequest(domainObject) {
        return domainObject.type === telemetryType;
      },

      request(domainObject, options) {
        const query = new URLSearchParams({
          key: domainObject.identifier.key,
          start: String(options.start),
          end: String(options.end)
        });

        return fetch(
          `${apiBase}/openmct/history?${query.toString()}`
        )
          .then(function (response) {
            if (!response.ok) {
              throw new Error(
                `History request failed: HTTP ${response.status}`
              );
            }

            return response.json();
          })
          .then(function (data) {
            const records =
              Array.isArray(data)
                ? data
                : data.data || [];

            return records
              .map(function (record) {
                let timestamp = record.timestamp;

                if (typeof timestamp === 'string') {
                  timestamp = new Date(timestamp).getTime();
                }

                return {
                  utc: timestamp,
                  timestamp: timestamp,
                  value: record.value
                };
              })
              .filter(function (record) {
                return (
                  Number.isFinite(record.timestamp) &&
                  record.value !== undefined &&
                  record.value !== null
                );
              });
          });
      },

      supportsSubscribe(domainObject) {
        return domainObject.type === telemetryType;
      },

      subscribe(domainObject, callback) {
        const measurementKey =
          domainObject.identifier.key;

        let requestInProgress = false;
        let subscriptionActive = true;

        const updateTelemetry = function () {
          if (requestInProgress || !subscriptionActive) {
            return;
          }

          requestInProgress = true;

          fetch(`${apiBase}/openmct/realtime`)
            .then(function (response) {
              if (!response.ok) {
                throw new Error(
                  `Realtime request failed: HTTP ${response.status}`
                );
              }

              return response.json();
            })
            .then(function (data) {
              if (!subscriptionActive) {
                return;
              }

              const value = data.values
                ? data.values[measurementKey]
                : undefined;

              if (value === undefined || value === null) {
                return;
              }

              let timestamp = data.timestamp;

              if (typeof timestamp === 'string') {
                timestamp = new Date(timestamp).getTime();
              }

              if (!Number.isFinite(timestamp)) {
                return;
              }

              callback({
                utc: timestamp,
                timestamp: timestamp,
                value: value
              });
            })
            .catch(function (error) {
              console.error(
                'Ground station telemetry error:',
                error
              );
            })
            .finally(function () {
              requestInProgress = false;
            });
        };

        updateTelemetry();

        const timer = setInterval(
          updateTelemetry,
          1000
        );

        return function unsubscribe() {
          subscriptionActive = false;
          clearInterval(timer);
        };
      }
    });
  };
}
