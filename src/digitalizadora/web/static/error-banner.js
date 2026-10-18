"use strict";

// The single red banner. ScanPage and DocumentPanel both report to it, so its state lives here and neither of them
// depends on the other to show an error.

class ErrorBanner {
  constructor(elements) {
    this.elements = elements;
    this.connection_error_message = null;
    this.action_error_message = null;
    this.scan_error_message = null;
  }

  report_action_error(message) {
    this.action_error_message = message;
    this.render();
  }

  set_scan_error(message) {
    this.scan_error_message = message;
    this.render();
  }

  set_connection_error(message) {
    this.connection_error_message = message;
    this.render();
  }

  choose_message() {
    return this.connection_error_message ?? this.action_error_message ?? this.scan_error_message;
  }

  render() {
    const message = this.choose_message();
    this.elements.error_banner_content.hidden = message === null;
    this.elements.error_banner_text.textContent = message ?? "";
  }
}
