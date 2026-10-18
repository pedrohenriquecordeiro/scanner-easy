"use strict";

// Runs the real static scripts in the fake browser of fake-browser.js (fake DOM, timers and fetch), plays each
// scenario and prints one JSON object with what the page did. tests/web/test_scan_page_behaviour.py asserts on it.

const { BrowserPage, build_json_response } = require("./fake-browser.js");

const ACTIVE_POLL_DELAY_MILLISECONDS = 500;
const PRINTER_POLL_DELAY_MILLISECONDS = 15000;
const POST_SCAN_PRINTER_DELAY_MILLISECONDS = 6000;
const BYTE_COUNTS = [0, 999, 1000, 999949, 999950, 1234567, 5e9];
const PAGE_COUNTS = [0, 1, 1234];

const SETTINGS = {
  output_folder: "/Users/teste/Digitalizadora",
  output_format: "pdf",
  dots_per_inch: 300,
  color_mode: "color",
  scan_preset: "document",
  capture_mode: "single",
  rotation_degrees: 0,
  auto_crop: false,
};
const OLD_SERVER_SETTINGS = {
  output_folder: "/Users/teste/Digitalizadora",
  output_format: "pdf",
  scan_preset: "document",
};
const CUSTOM_SETTINGS = { ...SETTINGS, dots_per_inch: 400, scan_preset: null };
const TURNED_SETTINGS = {
  ...SETTINGS,
  dots_per_inch: 1200,
  color_mode: "grayscale",
  scan_preset: null,
  rotation_degrees: 90,
  auto_crop: true,
};
const INVALID_SETTINGS_BODY = { code: "invalid_settings", message: "A resolução escolhida não é aceita." };
const AVAILABLE_STORAGE = { free_space_in_bytes: 12e9, estimated_pages_remaining: 4000, output_folder_available: true };
const LOW_STORAGE = { free_space_in_bytes: 1e9, estimated_pages_remaining: 300, output_folder_available: true };
const UNAVAILABLE_STORAGE = { free_space_in_bytes: 0, estimated_pages_remaining: 0, output_folder_available: false };
const CONFLICT_BODY = { code: "scan_already_running", message: "Já existe uma digitalização em andamento." };
const FINISHED_SCAN_RESULT = { file_name: "2026-10-17_00001.pdf", size_in_bytes: 1234567, scanned_at: "2026-10-17T10:00:00" };

function build_default_responses() {
  return {
    "GET /api/settings": build_json_response(200, SETTINGS),
    "GET /api/state": build_json_response(200, build_state("idle", AVAILABLE_STORAGE)),
    "GET /api/printer": build_json_response(200, build_printer("usb")),
  };
}

function build_state(scan_phase, storage, settings) {
  return {
    scan_phase,
    scans_completed: 0,
    last_result: null,
    last_error: null,
    settings: settings ?? SETTINGS,
    storage,
  };
}

function build_printer(route) {
  return { connected: true, display_name: "DeskJet 2800", scanner_state: "idle", route, error: null };
}

class PageUnderTest extends BrowserPage {
  constructor(response_overrides) {
    super({ ...build_default_responses(), ...response_overrides });
  }

  async press_space(target, repeat) {
    const key_event = this.dispatch_key("keydown", { code: "Space", target, repeat });
    await this.flush();
    return key_event;
  }

  async choose_option(element_identifier, option_value) {
    const select = this.element(element_identifier);
    select.focus();
    select.value = option_value;
    this.dispatch_simple_event(select, "change");
    await this.flush();
  }

  async set_auto_crop(is_checked) {
    const checkbox = this.element("auto-crop-checkbox");
    checkbox.focus();
    checkbox.checked = is_checked;
    this.dispatch_simple_event(checkbox, "change");
    await this.flush();
  }

  read_settings_controls() {
    return {
      preset: this.element("preset-select").value,
      custom_option_hidden: this.element("preset-custom-option").hidden,
      resolution: this.element("resolution-select").value,
      color_mode: this.element("color-mode-select").value,
      rotation: this.element("rotation-select").value,
      auto_crop: this.element("auto-crop-checkbox").checked,
      warning_hidden: this.element("resolution-warning").hidden,
      warning_text: this.element("resolution-warning-text").textContent,
    };
  }

  settings_request_body() {
    return this.find_request("PUT /api/settings").body;
  }

  count_scan_requests() {
    return this.count_requests("POST /api/scans");
  }
}

const SCAN_STATE_OVERRIDES = { "GET /api/state": build_json_response(200, build_state("scanning", AVAILABLE_STORAGE)) };

async function load_page(response_overrides) {
  const page = new PageUnderTest(response_overrides);
  await page.load();
  return page;
}

async function change_setting_through(control_identifier, control_change) {
  const page = await load_page({ "PUT /api/settings": build_json_response(200, SETTINGS) });
  await control_change(page);
  return {
    settings_request_body: page.settings_request_body(),
    scan_button_focused: page.active_element() === page.element("scan-button"),
    control_focused: page.active_element() === page.element(control_identifier),
  };
}

async function count_scans_after_space_on(element_identifier) {
  const page = await load_page({});
  const key_event = await page.press_space(page.element(element_identifier), false);
  return { scan_requests: page.count_scan_requests(), default_prevented: key_event.defaultPrevented };
}

const SCENARIOS = {
  async space_on_the_page_body() {
    const page = await load_page({});
    const key_event = await page.press_space(page.document.body, false);
    return { scan_requests: page.count_scan_requests(), default_prevented: key_event.defaultPrevented };
  },
  space_on_the_scan_button: () => count_scans_after_space_on("scan-button"),
  space_in_the_folder_field: () => count_scans_after_space_on("output-folder-input"),
  space_on_the_preset_select: () => count_scans_after_space_on("preset-select"),
  space_on_a_format_option: () => count_scans_after_space_on("output-format-jpg"),
  space_on_the_folder_save_button: () => count_scans_after_space_on("output-folder-save-button"),
  space_on_the_resolution_select: () => count_scans_after_space_on("resolution-select"),
  space_on_the_color_mode_select: () => count_scans_after_space_on("color-mode-select"),
  space_on_the_rotation_select: () => count_scans_after_space_on("rotation-select"),
  space_on_the_auto_crop_checkbox: () => count_scans_after_space_on("auto-crop-checkbox"),
  change_the_resolution: () => change_setting_through("resolution-select", (page) => page.choose_option("resolution-select", "600")),
  change_the_color_mode: () => change_setting_through("color-mode-select", (page) => page.choose_option("color-mode-select", "grayscale")),
  change_the_rotation: () => change_setting_through("rotation-select", (page) => page.choose_option("rotation-select", "180")),
  turn_auto_crop_on: () => change_setting_through("auto-crop-checkbox", (page) => page.set_auto_crop(true)),
  choose_a_preset: () => change_setting_through("preset-select", (page) => page.choose_option("preset-select", "photo")),
  async rotation_value_that_is_not_an_angle() {
    const page = await load_page({ "PUT /api/settings": build_json_response(200, SETTINGS) });
    await page.choose_option("rotation-select", "45");
    return page.settings_request_body().rotation_degrees;
  },
  async default_settings_controls() {
    const page = await load_page({});
    return page.read_settings_controls();
  },
  async custom_combination_controls() {
    const page = await load_page({ "GET /api/settings": build_json_response(200, CUSTOM_SETTINGS) });
    return page.read_settings_controls();
  },
  async slow_and_turned_controls() {
    const page = await load_page({ "GET /api/settings": build_json_response(200, TURNED_SETTINGS) });
    return page.read_settings_controls();
  },
  async old_server_controls() {
    const page = await load_page({ "GET /api/settings": build_json_response(200, OLD_SERVER_SETTINGS) });
    return page.read_settings_controls();
  },
  async refused_resolution_focus() {
    const page = await load_page({ "PUT /api/settings": build_json_response(422, INVALID_SETTINGS_BODY) });
    await page.choose_option("resolution-select", "600");
    return { control_focused: page.active_element() === page.element("resolution-select") };
  },
  async refused_resolution() {
    const page = await load_page({ "PUT /api/settings": build_json_response(422, INVALID_SETTINGS_BODY) });
    await page.choose_option("resolution-select", "600");
    return {
      banner_text: page.element("error-banner-text").textContent,
      controls: page.read_settings_controls(),
    };
  },
  async rotation_hint_in_quick_mode() {
    const page = await load_page({});
    return { hint_hidden: page.element("rotation-document-hint").hidden };
  },
  async scanning_at_a_high_resolution() {
    const page = await load_page({
      "GET /api/state": build_json_response(200, build_state("scanning", AVAILABLE_STORAGE, TURNED_SETTINGS)),
    });
    return { status_text: page.element("status-line").textContent };
  },
  async repeated_space_only() {
    const page = await load_page({});
    const key_event = await page.press_space(page.document.body, true);
    return { scan_requests: page.count_scan_requests(), default_prevented: key_event.defaultPrevented };
  },
  async held_space() {
    const page = await load_page({});
    await page.press_space(page.document.body, false);
    await page.press_space(page.document.body, true);
    await page.press_space(page.document.body, true);
    return { scan_requests: page.count_scan_requests() };
  },
  async double_click_while_the_request_is_pending() {
    const page = await load_page({});
    await page.click(page.element("scan-button"));
    await page.click(page.element("scan-button"));
    return { scan_requests: page.count_scan_requests(), button_disabled: page.element("scan-button").disabled };
  },
  async start_scan_called_twice_while_pending() {
    const page = await load_page({});
    const scan_page = page.evaluate("build_scan_page(collect_elements())");
    scan_page.start_scan();
    scan_page.start_scan();
    await page.flush();
    return { scan_requests: page.count_scan_requests() };
  },
  async space_during_a_scan() {
    const page = await load_page(SCAN_STATE_OVERRIDES);
    await page.press_space(page.document.body, false);
    return { scan_requests: page.count_scan_requests(), button_disabled: page.element("scan-button").disabled };
  },
  async idle_page() {
    const page = await load_page({});
    return {
      button_disabled: page.element("scan-button").disabled,
      status_text: page.element("status-line").textContent,
    };
  },
  async scanning_page() {
    const page = await load_page(SCAN_STATE_OVERRIDES);
    return { status_text: page.element("status-line").textContent };
  },
  async printer_poll_during_a_scan() {
    const page = await load_page(SCAN_STATE_OVERRIDES);
    const printer_requests_before = page.count_requests("GET /api/printer");
    page.timers.run_pending_with_delay(PRINTER_POLL_DELAY_MILLISECONDS);
    await page.flush();
    return { extra_printer_requests: page.count_requests("GET /api/printer") - printer_requests_before };
  },
  async printer_after_a_scan() {
    const page = await load_page(SCAN_STATE_OVERRIDES);
    const finished_state = { ...build_state("idle", AVAILABLE_STORAGE), scans_completed: 1, last_result: FINISHED_SCAN_RESULT };
    page.responses["GET /api/state"] = build_json_response(200, finished_state);
    // Gate 0: the printer still reports Processing for 4 to 5 s after it delivers the page.
    page.responses["GET /api/printer"] = build_json_response(200, { ...build_printer("usb"), scanner_state: "processing" });
    const printer_requests_before = page.count_requests("GET /api/printer");
    page.timers.run_pending_with_delay(ACTIVE_POLL_DELAY_MILLISECONDS);
    await page.flush();
    const immediate_printer_requests = page.count_requests("GET /api/printer") - printer_requests_before;
    const chip_text_right_after = page.element("printer-status-text").textContent;
    page.responses["GET /api/printer"] = build_json_response(200, build_printer("usb"));
    page.timers.run_pending_with_delay(POST_SCAN_PRINTER_DELAY_MILLISECONDS);
    await page.flush();
    return {
      immediate_printer_requests,
      chip_text_right_after,
      delayed_printer_requests: page.count_requests("GET /api/printer") - printer_requests_before,
      chip_text_after_the_delay: page.element("printer-status-text").textContent,
    };
  },
  async scan_request_headers() {
    const page = await load_page({});
    await page.click(page.element("scan-button"));
    const scan_request = page.requests.find((request) => request.key === "POST /api/scans");
    return { headers: scan_request.headers };
  },
  async conflict_answer() {
    const page = await load_page({ "POST /api/scans": build_json_response(409, CONFLICT_BODY) });
    await page.click(page.element("scan-button"));
    return {
      banner_hidden: page.element("error-banner-content").hidden,
      banner_text: page.element("error-banner-text").textContent,
    };
  },
  async unavailable_output_folder() {
    const page = await load_page({
      "GET /api/state": build_json_response(200, build_state("idle", UNAVAILABLE_STORAGE)),
    });
    return {
      storage_text: page.element("storage-line").textContent,
      warning_hidden: page.element("storage-warning").hidden,
    };
  },
  async low_free_space() {
    const page = await load_page({ "GET /api/state": build_json_response(200, build_state("idle", LOW_STORAGE)) });
    return { warning_hidden: page.element("storage-warning").hidden };
  },
  async printer_on_usb() {
    const page = await load_page({});
    return { chip_text: page.element("printer-status-text").textContent };
  },
  async printer_on_wifi() {
    const page = await load_page({ "GET /api/printer": build_json_response(200, build_printer("network")) });
    return { chip_text: page.element("printer-status-text").textContent };
  },
  async byte_counts() {
    const page = new PageUnderTest({});
    return Object.fromEntries(BYTE_COUNTS.map((count) => [count, page.evaluate(`format_byte_count(${count})`)]));
  },
  async page_counts() {
    const page = new PageUnderTest({});
    return Object.fromEntries(PAGE_COUNTS.map((count) => [count, page.evaluate(`describe_pages_remaining(${count})`)]));
  },
};

async function main() {
  const results = {};
  for (const [scenario_name, play_scenario] of Object.entries(SCENARIOS)) {
    results[scenario_name] = await play_scenario();
  }
  process.stdout.write(JSON.stringify(results));
}

main().catch((error) => {
  process.stderr.write(`${error.stack}\n`);
  process.exitCode = 1;
});
