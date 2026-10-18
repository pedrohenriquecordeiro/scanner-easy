"use strict";

// A small fake browser for the Node harnesses: a DOM built from the elements with an id in index.html (keeping which
// of them contains which), elements created by the scripts, key and click dispatch with capture and bubbling, the
// native button activation by Enter and Space, a modal <dialog>, focus with blur, timers that only run when a test
// asks, a localStorage (or one that refuses to work), and a fetch that records each request and answers what the
// scenario scripted.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const STATIC_DIRECTORY = path.resolve(__dirname, "..", "..", "src", "digitalizadora", "web", "static");
const PAGE_SCRIPT_FILE_NAMES = [
  "scan-trigger-policy.js",
  "error-banner.js",
  "document-page-policy.js",
  "document-panel.js",
  "application.js",
];
const TAG_PATTERN = /<(\/?)([a-z][a-z0-9]*)\b([^>]*)>/g;
const IDENTIFIER_ATTRIBUTE_PATTERN = /\bid="([^"]+)"/;
const VALUE_ATTRIBUTE_PATTERN = /\bvalue="([^"]*)"/;
const VOID_TAG_NAMES = new Set(["meta", "link", "input", "img", "br", "hr"]);
const DIALOG_TAG_NAME = "DIALOG";
const BUTTON_TAG_NAME = "BUTTON";
const FLUSH_ROUNDS = 10;
const ENTER_KEY_CODES = ["Enter", "NumpadEnter"];
const SPACE_KEY_CODE = "Space";
const ESCAPE_KEY_CODE = "Escape";
const KEYBOARD_CLICK_DETAIL = 0;
const POINTER_CLICK_DETAIL = 1;
const DEFAULT_TILE_BOX = Object.freeze({ left: 0, top: 0, width: 100, height: 140 });

class FakeClassList {
  constructor() {
    this.names = new Set();
  }

  add(...class_names) {
    class_names.forEach((class_name) => this.names.add(class_name));
  }

  remove(...class_names) {
    class_names.forEach((class_name) => this.names.delete(class_name));
  }

  toggle(class_name, should_have) {
    const will_have = should_have ?? !this.names.has(class_name);
    if (will_have) {
      this.names.add(class_name);
    } else {
      this.names.delete(class_name);
    }
    return will_have;
  }

  contains(class_name) {
    return this.names.has(class_name);
  }
}

function build_event(event_type, properties) {
  return {
    type: event_type,
    bubbles: true,
    detail: 0,
    repeat: false,
    code: "",
    clientX: 0,
    defaultPrevented: false,
    propagation_stopped: false,
    preventDefault() {
      this.defaultPrevented = true;
    },
    stopPropagation() {
      this.propagation_stopped = true;
    },
    ...properties,
  };
}

class FakeEventTarget {
  constructor() {
    this.registered_listeners = [];
  }

  addEventListener(event_type, listener, options) {
    const capture = options === true || options?.capture === true;
    const once = options?.once === true;
    this.registered_listeners.push({ event_type, listener, capture, once });
  }

  run_listeners(event, phase_filter) {
    for (const registration of [...this.registered_listeners]) {
      if (registration.event_type !== event.type || !phase_filter(registration)) {
        continue;
      }
      if (registration.once) {
        this.registered_listeners = this.registered_listeners.filter((candidate) => candidate !== registration);
      }
      registration.listener(event);
      if (event.propagation_stopped) {
        return;
      }
    }
  }

  count_listeners(event_type) {
    return this.registered_listeners.filter((registration) => registration.event_type === event_type).length;
  }
}

class FakeElement extends FakeEventTarget {
  constructor(tag_name, page_document) {
    super();
    this.tagName = tag_name;
    this.page_document = page_document;
    this.parent = null;
    this.children = [];
    this.dataset = {};
    this.attributes = {};
    this.classList = new FakeClassList();
    this.textContent = "";
    this.hidden = false;
    this.disabled = false;
    this.value = "";
    this.checked = false;
    this.title = "";
    this.src = "";
    this.alt = "";
    this.draggable = false;
    this.isContentEditable = false;
    this.is_text_selected = false;
    this.box = DEFAULT_TILE_BOX;
  }

  setAttribute(attribute_name, attribute_value) {
    this.attributes[attribute_name] = String(attribute_value);
  }

  getAttribute(attribute_name) {
    return this.attributes[attribute_name] ?? null;
  }

  focus() {
    // Browsers never focus a disabled control.
    if (!this.disabled) {
      this.page_document.move_focus_to(this);
    }
  }

  blur() {
    if (this.page_document.activeElement === this) {
      this.page_document.move_focus_to(this.page_document.body);
    }
  }

  select() {
    this.is_text_selected = true;
  }

  append(...child_elements) {
    child_elements.forEach((child_element) => {
      child_element.parent = this;
      this.children.push(child_element);
    });
  }

  replaceChildren(...child_elements) {
    this.children.forEach((child_element) => {
      child_element.parent = null;
    });
    this.children = [];
    this.append(...child_elements);
  }

  contains(other_element) {
    for (let node = other_element; node !== null; node = node.parent) {
      if (node === this) {
        return true;
      }
    }
    return false;
  }

  getBoundingClientRect() {
    return this.box;
  }
}

class FakeDialog extends FakeElement {
  constructor(page_document) {
    super(DIALOG_TAG_NAME, page_document);
    this.open = false;
    this.returnValue = "";
  }

  showModal() {
    this.open = true;
  }

  close(return_value) {
    if (!this.open) {
      return;
    }
    this.open = false;
    if (return_value !== undefined) {
      this.returnValue = return_value;
    }
    this.run_listeners(build_event("close", { target: this, bubbles: false }), () => true);
  }
}

class FakeDocument extends FakeEventTarget {
  constructor(page_markup) {
    super();
    this.body = new FakeElement("BODY", this);
    this.activeElement = this.body;
    this.elements = new Map();
    this.build_elements(page_markup);
  }

  build_elements(page_markup) {
    const open_elements = [];
    for (const [, closing_slash, tag_name, attributes] of page_markup.matchAll(TAG_PATTERN)) {
      if (closing_slash === "/") {
        open_elements.pop();
        continue;
      }
      const identifier_match = IDENTIFIER_ATTRIBUTE_PATTERN.exec(attributes);
      const nearest_parent = [...open_elements].reverse().find((element) => element !== null) ?? null;
      let element = null;
      if (identifier_match !== null) {
        element = this.createElement(tag_name);
        element.value = VALUE_ATTRIBUTE_PATTERN.exec(attributes)?.[1] ?? "";
        if (nearest_parent !== null) {
          nearest_parent.append(element);
        }
        this.elements.set(identifier_match[1], element);
      }
      if (!VOID_TAG_NAMES.has(tag_name)) {
        open_elements.push(element);
      }
    }
  }

  createElement(tag_name) {
    const upper_tag_name = tag_name.toUpperCase();
    return upper_tag_name === DIALOG_TAG_NAME ? new FakeDialog(this) : new FakeElement(upper_tag_name, this);
  }

  getElementById(element_identifier) {
    return this.elements.get(element_identifier) ?? null;
  }

  move_focus_to(element) {
    const previous_element = this.activeElement;
    if (previous_element === element) {
      return;
    }
    this.activeElement = element;
    previous_element.run_listeners(build_event("blur", { target: previous_element, bubbles: false }), () => true);
  }

  find_open_dialog() {
    return [...this.elements.values()].find((element) => element.tagName === DIALOG_TAG_NAME && element.open) ?? null;
  }

  dispatch(target, event) {
    event.target = target;
    const ancestors = [];
    for (let node = target.parent; node !== null; node = node.parent) {
      ancestors.unshift(node);
    }
    for (const node of [this, ...ancestors]) {
      node.run_listeners(event, (registration) => registration.capture);
      if (event.propagation_stopped) {
        return event;
      }
    }
    target.run_listeners(event, () => true);
    if (!event.bubbles || event.propagation_stopped) {
      return event;
    }
    for (const node of [...ancestors.reverse(), this]) {
      node.run_listeners(event, (registration) => !registration.capture);
      if (event.propagation_stopped) {
        return event;
      }
    }
    return event;
  }
}

class FakeTimers {
  constructor() {
    this.pending = new Map();
    this.next_handle = 1;
  }

  setTimeout(callback, delay_milliseconds) {
    const handle = this.next_handle;
    this.next_handle += 1;
    this.pending.set(handle, { callback, delay_milliseconds });
    return handle;
  }

  clearTimeout(handle) {
    this.pending.delete(handle);
  }

  run_pending_with_delay(delay_milliseconds) {
    for (const [handle, timer] of [...this.pending]) {
      if (timer.delay_milliseconds === delay_milliseconds) {
        this.pending.delete(handle);
        timer.callback();
      }
    }
  }
}

class FakeStorage {
  constructor(stored_values) {
    this.stored_values = new Map(Object.entries(stored_values ?? {}));
  }

  getItem(key) {
    return this.stored_values.get(key) ?? null;
  }

  setItem(key, value) {
    this.stored_values.set(key, String(value));
  }
}

class BlockedStorage {
  getItem() {
    throw new Error("The browser blocks the storage of this page.");
  }

  setItem() {
    throw new Error("The browser blocks the storage of this page.");
  }
}

// Read and compiled once per harness run; each scenario only runs them in a fresh context.
const PAGE_MARKUP = fs.readFileSync(path.join(STATIC_DIRECTORY, "index.html"), "utf8");
function compile_page_script(file_name) {
  return new vm.Script(fs.readFileSync(path.join(STATIC_DIRECTORY, file_name), "utf8"), { filename: file_name });
}

const PAGE_SCRIPTS = PAGE_SCRIPT_FILE_NAMES.map(compile_page_script);

function build_json_response(status_code, body) {
  return { ok: status_code >= 200 && status_code < 300, status: status_code, json: async () => body };
}

function build_deferred_response() {
  const deferred = {};
  deferred.promise = new Promise((resolve) => {
    deferred.answer = resolve;
  });
  return deferred;
}

class BrowserPage {
  constructor(responses, storage) {
    this.responses = responses;
    this.storage = storage ?? new FakeStorage();
    this.requests = [];
    this.timers = new FakeTimers();
    this.document = new FakeDocument(PAGE_MARKUP);
    const browser_window = {
      setTimeout: (callback, delay_milliseconds) => this.timers.setTimeout(callback, delay_milliseconds),
      clearTimeout: (handle) => this.timers.clearTimeout(handle),
      localStorage: this.storage,
    };
    const context = vm.createContext({
      document: this.document,
      window: browser_window,
      fetch: (request_path, options) => this.fetch(request_path, options),
    });
    PAGE_SCRIPTS.forEach((script) => script.runInContext(context));
    this.context = context;
  }

  fetch(request_path, options) {
    const request_key = `${options.method} ${request_path}`;
    const body = options.body === undefined ? null : JSON.parse(options.body);
    this.requests.push({ key: request_key, headers: { ...options.headers }, body });
    const scripted = this.responses[request_key];
    // An array answers in turn and keeps repeating its last answer.
    const response = Array.isArray(scripted) ? (scripted.length > 1 ? scripted.shift() : scripted[0]) : scripted;
    // A request without a scripted answer stays pending, like a printer that has not answered yet.
    if (response === undefined) {
      return new Promise(() => {});
    }
    return response.promise ?? Promise.resolve(response);
  }

  async load() {
    this.document.run_listeners(build_event("DOMContentLoaded", { target: this.document }), () => true);
    await this.flush();
  }

  async flush() {
    for (let round = 0; round < FLUSH_ROUNDS; round += 1) {
      await new Promise((resolve) => setImmediate(resolve));
    }
  }

  element(element_identifier) {
    return this.document.getElementById(element_identifier);
  }

  active_element() {
    return this.document.activeElement;
  }

  dispatch_key(event_type, key_press) {
    const { code, target, repeat } = key_press;
    return this.document.dispatch(target, build_event(event_type, { code, repeat: repeat === true }));
  }

  async key_down(code) {
    return this.dispatch_key_down({ code, target: this.document.activeElement, repeat: false });
  }

  async repeat_key_down(code) {
    // What a held key sends after its first keydown.
    return this.dispatch_key_down({ code, target: this.document.activeElement, repeat: true });
  }

  async dispatch_key_down(key_press) {
    const { code, target } = key_press;
    const key_event = this.dispatch_key("keydown", key_press);
    if (!key_event.defaultPrevented && ENTER_KEY_CODES.includes(code) && target.tagName === BUTTON_TAG_NAME) {
      this.activate(target, KEYBOARD_CLICK_DETAIL);
    }
    const open_dialog = this.document.find_open_dialog();
    if (!key_event.defaultPrevented && code === ESCAPE_KEY_CODE && open_dialog !== null) {
      open_dialog.close();
    }
    await this.flush();
    return key_event;
  }

  async key_up(code, key_down_event) {
    const target = this.document.activeElement;
    const key_event = this.dispatch_key("keyup", { code, target, repeat: false });
    const is_activation = code === SPACE_KEY_CODE && target.tagName === BUTTON_TAG_NAME;
    if (is_activation && !key_event.defaultPrevented && !key_down_event.defaultPrevented) {
      this.activate(target, KEYBOARD_CLICK_DETAIL);
    }
    await this.flush();
    return key_event;
  }

  async press_key(code) {
    const key_down_event = await this.key_down(code);
    await this.key_up(code, key_down_event);
    return key_down_event;
  }

  activate(element, click_detail) {
    // Browsers never deliver a click to a disabled button.
    if (!element.disabled) {
      this.document.dispatch(element, build_event("click", { detail: click_detail }));
    }
  }

  async click(element) {
    element.focus();
    this.activate(element, POINTER_CLICK_DETAIL);
    await this.flush();
  }

  async press_with_keyboard(element) {
    element.focus();
    await this.press_key("Enter");
  }

  async drag_and_drop(drag_parts) {
    const { dragged_element, target_element, pointer_horizontal_position } = drag_parts;
    const transferred_data = new Map();
    const data_transfer = {
      effectAllowed: "",
      dropEffect: "",
      setData: (format, value) => transferred_data.set(format, value),
      getData: (format) => transferred_data.get(format) ?? "",
    };
    const pointer = { clientX: pointer_horizontal_position, dataTransfer: data_transfer };
    this.document.dispatch(dragged_element, build_event("dragstart", pointer));
    this.document.dispatch(target_element, build_event("dragover", pointer));
    this.document.dispatch(target_element, build_event("drop", pointer));
    this.document.dispatch(dragged_element, build_event("dragend", pointer));
    await this.flush();
  }

  dispatch_simple_event(element, event_type) {
    this.document.dispatch(element, build_event(event_type, { bubbles: false }));
  }

  count_requests(request_key) {
    return this.requests.filter((request) => request.key === request_key).length;
  }

  find_request(request_key) {
    return this.requests.find((request) => request.key === request_key) ?? null;
  }

  evaluate(expression) {
    return vm.runInContext(expression, this.context);
  }
}

module.exports = {
  BlockedStorage,
  BrowserPage,
  FakeDocument,
  FakeElement,
  FakeStorage,
  FakeTimers,
  build_deferred_response,
  build_event,
  build_json_response,
};
