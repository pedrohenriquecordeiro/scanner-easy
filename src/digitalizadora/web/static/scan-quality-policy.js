"use strict";

// Pure rules for the quality settings (no DOM); application.js and document-panel.js wire them to the page.
// index.html loads this file right after scan-trigger-policy.js.

const DEFAULT_DOTS_PER_INCH = 300;
const SLOW_SCAN_DOTS_PER_INCH = 600;
const VERY_SLOW_SCAN_DOTS_PER_INCH = 1200;
// Measured on the printer up to 600 dpi (Gate 0); 400 and 1200 dpi are estimates by area.
const EXPECTED_SCAN_DURATIONS = Object.freeze([
  { up_to_dots_per_inch: 300, text: "cerca de 15 s" },
  { up_to_dots_per_inch: 400, text: "cerca de 30 s" },
  { up_to_dots_per_inch: SLOW_SCAN_DOTS_PER_INCH, text: "cerca de 75 s" },
  { up_to_dots_per_inch: Infinity, text: "vários minutos" },
]);
const SLOW_SCAN_WARNING_TEXT = "600 dpi leva cerca de 75 s por página e gera arquivos grandes.";
const VERY_SLOW_SCAN_WARNING_TEXT = "1200 dpi pode levar vários minutos e gerar arquivos muito grandes.";

function describe_expected_scan_duration(dots_per_inch) {
  // A server from before the resolution setting sends none: the text for the usual 300 dpi applies.
  const known_dots_per_inch = dots_per_inch ?? DEFAULT_DOTS_PER_INCH;
  return EXPECTED_SCAN_DURATIONS.find((duration) => known_dots_per_inch <= duration.up_to_dots_per_inch).text;
}

function describe_resolution_warning(dots_per_inch) {
  if (dots_per_inch >= VERY_SLOW_SCAN_DOTS_PER_INCH) {
    return VERY_SLOW_SCAN_WARNING_TEXT;
  }
  return dots_per_inch >= SLOW_SCAN_DOTS_PER_INCH ? SLOW_SCAN_WARNING_TEXT : null;
}
