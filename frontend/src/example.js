export const EXAMPLE_INPUT = {
  initial: { time: "64800", azimuth: "180", elevation: "45" },
  azimuth_speed: "2",
  elevation_speed: "1",
  targets: [
    { id: "M31", azimuth: "200", elevation: "60", duration: "600", window_start: "66000", window_end: "72000", priority: "9", mandatory: true },
    { id: "CAS-A", azimuth: "120", elevation: "30", duration: "450", window_start: "64800", window_end: "70000", priority: "7", mandatory: false },
    { id: "CYG-A", azimuth: "260", elevation: "50", duration: "300", window_start: "68000", window_end: "76000", priority: "8", mandatory: true },
    { id: "PULSAR-1", azimuth: "150", elevation: "70", duration: "240", window_start: "70000", window_end: "80000", priority: "5", mandatory: false },
    { id: "QUASAR-3C273", azimuth: "300", elevation: "25", duration: "500", window_start: "66000", window_end: "74000", priority: "6", mandatory: false },
    { id: "SAT-CAL", azimuth: "90", elevation: "15", duration: "180", window_start: "64800", window_end: "86399", priority: "3", mandatory: false },
  ],
};

export const EMPTY_TARGET = {
  id: "",
  azimuth: "0",
  elevation: "45",
  duration: "300",
  window_start: "0",
  window_end: "86399",
  priority: "1",
  mandatory: false,
};
