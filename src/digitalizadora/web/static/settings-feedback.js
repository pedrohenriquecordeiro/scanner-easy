"use strict";

// What the person sees when a setting is saved: the busy state of the folder Save button, the green confirmation that
// lasts a few seconds and the red message of a refusal. application.js hands it the elements and a scheduler
// ({ set_timeout, clear_timeout }), so a test decides when the confirmation ends.

const FOLDER_SAVE_READY_LABEL = "Salvar";
const FOLDER_SAVE_BUSY_LABEL = "Salvando…";
const FOLDER_SAVED_TEXT = "✔ Pasta salva";
const ADJUSTMENT_SAVED_TEXT = "✔ Ajuste salvo";
const CONFIRMATION_VISIBLE_MILLISECONDS = 4000;

class SettingsFeedback {
  constructor(elements, scheduler) {
    this.elements = elements;
    this.scheduler = scheduler;
    this.confirmation_timer = null;
  }

  begin_folder_save() {
    this.hide_confirmation();
    this.hide_error();
    this.render_folder_save_button(true);
  }

  finish_folder_save() {
    this.render_folder_save_button(false);
    this.show_confirmation(FOLDER_SAVED_TEXT);
  }

  fail_folder_save(message) {
    this.render_folder_save_button(false);
    this.elements.output_folder_message.textContent = message;
    this.elements.output_folder_message.hidden = false;
  }

  confirm_adjustment_saved() {
    this.show_confirmation(ADJUSTMENT_SAVED_TEXT);
  }

  render_folder_save_button(is_busy) {
    const { output_folder_save_button } = this.elements;
    output_folder_save_button.disabled = is_busy;
    output_folder_save_button.setAttribute("aria-busy", String(is_busy));
    output_folder_save_button.textContent = is_busy ? FOLDER_SAVE_BUSY_LABEL : FOLDER_SAVE_READY_LABEL;
  }

  show_confirmation(text) {
    this.scheduler.clear_timeout(this.confirmation_timer);
    this.elements.settings_confirmation.textContent = text;
    this.elements.settings_confirmation.hidden = false;
    this.confirmation_timer = this.scheduler.set_timeout(
      () => this.hide_confirmation(),
      CONFIRMATION_VISIBLE_MILLISECONDS,
    );
  }

  hide_confirmation() {
    this.scheduler.clear_timeout(this.confirmation_timer);
    this.confirmation_timer = null;
    this.elements.settings_confirmation.textContent = "";
    this.elements.settings_confirmation.hidden = true;
  }

  hide_error() {
    this.elements.output_folder_message.textContent = "";
    this.elements.output_folder_message.hidden = true;
  }
}
