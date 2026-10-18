# Achados da revisão adversarial do plano (2026-10-13)

Seis revisores independentes (cinco por faixa de tarefas e um global) leram o plano com quatro lentes: L1 correção técnica e APIs, L2 conformidade com o spec, L3 regras do usuário e qualidade dos testes, L4 modos de falha e segurança. **Nada abaixo foi aplicado ao plano.** O texto dos achados está em inglês, como foi entregue.

Total: 65 achados (2 bloqueantes, 15 graves, 48 menores). Os graves incluem 2 repetições entre revisores (T11 e T12), então são 13 distintos.

`owner_part` indica qual parte do plano deve mudar: **a** = T0–T3; **b** = T4, T5, T9; **c** = T6–T8; **d** = T10–T11; **e** = T12–T14.

## Resumo de cada revisor

**Revisor a.** Tasks 0-3 are mostly sound. I rebuilt the code from part-a.md in a scratch project and ran it with pytest 9.1.1. Every test count matches the plan: 8, 100 and 155 passed, with the one install-metadata test failing only because nothing is pip-installed there. I also ran the probe script against a stdlib mock printer, and its XML is byte-identical to build_scan_settings_xml for 300 dpi colour. There is one blocker: the T3 Step 18 test uses `Callable` without importing it, so the whole test file fails at collection. The other findings are one contract leak (ACC-3, an exception escaping a parser), a few real-world robustness gaps, and test-quality or doc issues. I found no extra impact from ACC-1, 5, 6, 8 or 9 in this range beyond the items the fixer already knows.

**Revisor b.** I rebuilt the final state of Tasks 4, 5 and 9 in a scratch project (stdlib, httpx 0.27.2, fastapi, Pillow, plus the plan's own domain and escl_protocol code from part-a). I ran the tests with a small pytest shim, since pytest is not installed. All final suites pass: 34 for T4, 50 for T5, 19 + 29 for T9 (the 7 pure-function zeroconf tests and the 2 signature tests could not run because zeroconf is not installed). The cycle-by-cycle failed/passed counts are right except one. I found two real defects. 1) Blocker: `_is_local_network_blocked` walks only `__cause__`, but real httpx 0.27.2/httpcore 1.0.5 chains link the OSError through `__context__`, so errno 65 never becomes `local_network_blocked` in production. The hand-built test chains hide this. 2) Major: the Expected output of T5 Passo 6 is wrong (2 failed, 9 passed, not 4 failed, 7 passed), because the gateway's colour-mode check duplicates what T3's `build_scan_settings_xml` already does. Three more majors are in the findings list. The most important is that the zeroconf constructor can raise RuntimeError on an offline Mac, and `check_connection` does not catch it.

**Revisor c.** Tasks 6, 7 and 8 are in very good shape. I extracted all plan code and tests into a scratch project and ran them with pytest 9.1.1, img2pdf 0.6.3, pikepdf 10.17.0 and Pillow 10.4 and 12.3.0 (sources fetched read-only from PyPI and GitHub, nothing installed). All 274 tests passed, also with -W error, with no test above about 50 ms. The step counts (22, 11, 11, 15, 59, 20, 12, 19, 84, 14, 23, 32) and most of the "failing run" expectations match what I measured. The failing runs I re-ran by swapping in the earlier-cycle implementation (JPEG cycle 1 vs 2, AtomicFileWriter cycle 1 vs 2, output repository cycle 3 vs 4) gave exactly the counts and error messages the plan states. I found no blocker. The one real contract gap is the ACC-9 follow-up in T8, where the free-space reader must also turn PermissionError and other OSError into OutputFolderUnavailableError. The rest are robustness and test-quality items: JPEG fill bytes, an uncaught DecompressionBombError, a test that cannot detect draft-after-load, an uncovered Review Focus case (PDF from a JPEG with no JFIF), the fixed .part name racing, a blocking call on the event loop, and fake duplication.

**Revisor d.** Tasks 10 and 11 are in good shape. I extracted every code block of part-d (plus the part-a domain code and minimal stubs for T8/T9 symbols) and ran all of its tests against the installed fastapi 0.136.3, starlette 0.52.1 and httpx 0.27.2 with a small pytest-compatible shim, because pytest is not installed. All counts match the plan: 23+7+26+6=62 in T10, and 28+17+22+7+30+21=125 in T11. The ScanService concurrency tests (asyncio.Event, begin_scan outside the try, to_thread) have no deadlock or flakiness, and the guard, handlers, StaticFiles, lifespan and BackgroundTasks behave as the plan assumes. No blocker found. The real defects are: framework and unexpected errors escape the {code,message} contract (major), a TypeVar function that ruff UP047 flags (minor), and extra impacts of ACC-8 on T11 call sites and prose (major). The rest is smaller.

**Revisor e.** Tasks 12-14 are mostly solid. node --check passes, format_byte_count gives the stated pt-BR output, the HTML/JS ids match, make -n prints the 11 stated lines, zsh -n passes, and the TestClient/ASGITransport pattern runs without event-loop problems. Real defects found: the launcher treats a half-installed .venv as ready, so a failed first-run setup is never retried. The 409 integration fixture can race the printer request (main finding). T12 has no behavioural test for the Space/repeat logic that Review Focus 2 relies on. The composition test needs a discovery seam that ACC-12 does not provide, and the composition root's HTTP timeouts deviate from the spec and are overridden by the gateway anyway. There is one lint failure at 121 columns and some smaller issues in the launcher, logging, README and checklist.

**Revisor f (GLOBAL REVIEWER).** I found no blocker. The plan is coherent. Every `from digitalizadora.* / tests.*` import resolves to a module created by the same or a lower-numbered task, and every imported name is defined somewhere in the plan. Every `Files` list matches the task's `git add` (apart from the ACC-8 preparer file, which the fixer will add). Layering, `Clock` and `sleep` injection, and the Makefile targets and environment variable names are consistent across tasks. I ran the Task 0 probe script against a fake eSCL server, and its XML is byte-identical to the Task 3 builder. I found seven real defects: ACC-8 breaks one more test fixture; the first-run Local Network case is not detected; `dns-sd` blocks the Gate 0 commands; the browser side of failure mode 2 is not really tested; and the T0 expected output, the PHOTO 400 dpi note and the 121-character line need correcting. The rest are minor consistency items. I do not dispute any ACC item. ACC-8, ACC-9, ACC-11 and ACC-12 have the extra impacts listed in the findings.

## Bloqueantes

### F-01 · Task 3 · L1 · revisor a · parte a

**Onde:** Task 3, Passo 18(b): `def test_parsers_refuse_documents_that_declare_entities(parser: Callable[[bytes], object],) -> None:` with the note "(o bloco de imports não muda)"; the import block of Passo 14(a) has no `Callable`

**Problema:** The Cycle 5 test annotates a parameter with `Callable`, but the import block that stays in force (Passo 14(a), kept in Passo 18) never imports it. The module has no `from __future__ import annotations`, so the annotation is evaluated at function definition and raises NameError during collection. Passo 19 ("5 failed, 50 passed") and Passo 21 ("55 passed") can never be observed as written, and the executing agent has to improvise.

**Evidência:** Reproduced by assembling the file exactly as the plan's edit steps say and running pytest: `ERROR tests/infrastructure/test_escl_protocol.py - NameError: name 'Callable' is not defined` and `1 error during collection`. Adding `from collections.abc import Callable` to the header gives 57 passed in tests/infrastructure (55 from this file plus 2 clock tests) and 155 in the whole suite, matching the plan.

**Correção sugerida:** In Passo 18 add a step (c) that replaces the import block again, or better add `from collections.abc import Callable` right after `import dataclasses` in the import blocks of Passo 10(a) and Passo 14(a), so that it is present at the end. Alternatively drop the annotation and use `parser: object` plus `# type: ignore`. Keep the Passo 19 expected counts as they are.

### F-02 · Task 5 · L4 · revisor b · parte b

**Onde:** Task 5, Passo 11, `_is_local_network_blocked` (loop `cause = error.__cause__ ... cause = cause.__cause__`) and the Passo 9 tests `test_host_unreachable_cause_means_local_network_blocked` / `..._found_deeper_in_the_cause_chain_...`; the Passo 9 text claiming 'httpx.ConnectError <- httpcore.ConnectError <- OSError' via causes

**Problema:** The errno 65 detection never fires with a real httpx client, so Rede Local blocked becomes plain `scanner_unreachable` and the dedicated message and guidance are never shown. In httpx 0.27.2 with httpcore 1.0.5 the link httpcore.ConnectError -> OSError is `__context__` (cause is None), not `__cause__`. The tests assign `__cause__` by hand, so they pass while production fails.

**Evidência:** I patched the selector loop's `sock_connect` to raise OSError(errno.EHOSTUNREACH) and walked the chain of a real httpx.AsyncClient.get: `httpx ConnectError | cause: ConnectError`, then `httpcore ConnectError | cause: NoneType | context: OSError`, then `OSError (All connection attempts failed) | cause: OSError`, then `OSError errno=65`. Running the plan's EsclScannerGateway.read_status against the same patched loop gave 'GATEWAY RAISES: ScannerUnreachableError The scanner could not be reached: All connection attempts failed', not LocalNetworkBlockedError. The chain also needs `__context__` through anyio's OSError('All connection attempts failed'), and with a hostname that resolves to several addresses anyio raises an ExceptionGroup.

**Correção sugerida:** Rewrite `_is_local_network_blocked` to traverse `error.__cause__ or error.__context__` iteratively, with a visited-id set to stop cycles, and to descend into `BaseExceptionGroup.exceptions`. Replace the two chain tests with a realistic chain built by raising inside `try/except`, for example `try: raise OSError(errno.EHOSTUNREACH, 'No route to host')`, then `except OSError: raise httpx.ConnectError('x') from None`. Add a test that mimics httpx/httpcore/anyio with `__context__` links only. Correct the Passo 9 paragraph, which says the chain is built with causes.

## Graves

### F-03 · Task 3 · L4 · revisor a · parte a

**Onde:** Task 3, Passo 20(b) `_parse_document`: `except ElementTree.ParseError as error: raise ScanFailedError(...)`; spec 6.2: "nenhum ParseError/ValueError escapa delas"

**Problema:** The two parse functions still let exceptions other than ParseError escape. A document whose XML declaration names an unknown encoding makes expat raise `LookupError`, which is not caught, so the caller gets `unexpected_error` instead of `scan_failed`. No test covers this. The spec (ACC-3) states that nothing escapes.

**Evidência:** Run against the plan's code: `parse_scanner_status(b'<?xml version="1.0" encoding="foo"?><ScannerStatus/>')` -> `LEAK LookupError unknown encoding: foo`, and `parse_scanner_capabilities` does the same. Invalid UTF-8 bytes and empty or HTML input are correctly turned into ScanFailedError.

**Correção sugerida:** Catch `(ElementTree.ParseError, LookupError, ValueError)` in `_parse_document` and raise ScanFailedError with the same "not valid XML" message. Add a test `test_parsers_reject_an_unknown_encoding_declaration`, parametrized over both parsers, with the document above and `match="not valid XML"`.

### F-04 · Task 5 · L1 · revisor b · parte b

**Onde:** Task 5, Passo 6 'Expected: resumo `4 failed, 7 passed`' plus Passo 7 `_ensure_color_mode_is_supported` and `ESCL_COLOR_MODE_BY_COLOR_MODE`

**Problema:** The Expected output is wrong, and two of the new tests cannot fail in the stated red phase. With the cycle-1 gateway, `scan_page` calls `_post_job`, which calls T3's `build_scan_settings_xml`. That function already raises `ScanRejectedError` for an unsupported colour mode before any request. So `test_unsupported_color_mode_is_rejected` and `..._sends_no_scan_job` already pass. The real result is 2 failed, 9 passed, and the executor will see a mismatch. The new gateway check also duplicates the colour-mode map and the check that T3 already owns (DRY). The stated error 'ParseError' is also wrong: T3 raises `ScanFailedError` (ACC-3).

**Evidência:** I ran the cycle-1 gateway from Passo 3 against the full test file. The failure list contains `test_status_answer_other_than_200_means_unreachable` and `test_capabilities_answer_other_than_200_means_unreachable` (both raise `ScanFailedError: The eSCL document is not valid XML: no element found`), and neither colour-mode test appears. `escl_protocol.py` (T3 step 20) already defines `ESCL_COLOR_MODE_BY_COLOR_MODE` and raises `ScanRejectedError` in `build_scan_settings_xml`.

**Correção sugerida:** Change Passo 6 Expected to `2 failed, 9 passed` and the error to `ScanFailedError`. Drop the local map and import `ESCL_COLOR_MODE_BY_COLOR_MODE` from escl_protocol. Move the two colour-mode tests to cycle 4 (readiness wait) and make them discriminating: with `initial_state='Processing'` and an unsupported colour mode, assert `ScanRejectedError`, `harness.sleep.delays == []` and no STATUS request. Those fail until `_ensure_color_mode_is_supported` runs before `_wait_until_ready`. Alternatively, delete the redundant check and tests and rely on T3.

### F-05 · Task 9 · L4 · revisor b · parte b

**Onde:** Task 9, Passo 15 `ZeroconfServiceRecordSource.collect_records` (`AsyncZeroconf(ip_version=IPVersion.V4Only)`), Passo 27 `check_connection` (`except ScannerUnreachableError` only), Passo 23 `_connect_to_discovered`

**Problema:** Failure mode 1 (printer offline or Mac off the network) can end in `unexpected_error` or a 500 on GET /api/printer instead of `scanner_unreachable`. `check_connection` is documented as 'nunca levanta', but it only catches `ScannerUnreachableError`. Two other errors escape. (a) `AsyncZeroconf` is built with the default `interfaces=InterfaceChoice.All`, and python-zeroconf raises `RuntimeError` in `normalize_interface_choice` when no IPv4 interface exists (Wi-Fi off, no network), and `OSError` on socket bind or multicast errors. (b) `read_status` can raise `ScanFailedError` (ACC-3: the parser rejects a non-eSCL 200 body), which aborts the candidate loop and escapes `check_connection`.

**Evidência:** zeroconf 0.151.5 `_utils/net.py`: 'normalize_interface_choice raises RuntimeError when the choice is InterfaceChoice.All and no interfaces match the requested IP version', and `new_socket` propagates OSError. `asyncio.py`: `AsyncZeroconf.__init__(self, interfaces=InterfaceChoice.All, unicast=False, ip_version=None, ...)` builds `Zeroconf(...)` synchronously. `PrinterConnectionService.check_connection` has a single `except ScannerUnreachableError`. `escl_protocol._parse_document` raises ScanFailedError for non-XML or non-eSCL bodies.

**Correção sugerida:** In `collect_records`, wrap the creation of AsyncZeroconf and the browser in `try/except (RuntimeError, OSError)`, log a warning and return `[]` (or raise `ScannerUnreachableError`, or `LocalNetworkBlockedError` when `errno == errno.EHOSTUNREACH`). In `PrinterConnectionService._verify`, convert `ScanFailedError` from `read_status` into `ScannerUnreachableError(...) from error`. Add tests for 'discovery source raises RuntimeError' and 'gateway.read_status raises ScanFailedError', both expecting `scanner_unreachable` from `check_connection` and a continued search over the remaining candidates.

### F-06 · Task 9 · L2 · revisor b · parte b

**Onde:** Task 9, Passo 27 `refresh` (`self._connection = None; self._endpoint_repository.clear(); return await self.check_connection()`) and tests `test_refresh_clears_the_stored_endpoint`, `test_refresh_reports_when_nothing_is_found`

**Problema:** Spec 6.4 says `refresh` 'esquece o gateway em memória e procura de novo'. It does not say to delete the saved endpoint. The plan clears the repository before searching, so `_ensure_connection` then calls `_connect_to_discovered(None, None)`. (1) The stored-UUID preference is lost on refresh, so with two eSCL devices the first one by name wins. (2) A refresh while the printer is asleep or offline permanently erases the saved endpoint, including a manual address the user typed, and the next start has nothing to try. The test pins this behaviour.

**Evidência:** Code in Passo 27: `refresh` calls `self._endpoint_repository.clear()` before `check_connection()`. In Passo 23 `_ensure_connection` loads the stored endpoint (now None) and passes `None` to `_prefer_stored_identity`, which returns the discovered list unchanged. The `test_refresh_reports_when_nothing_is_found` test with a stored endpoint ends with the repository emptied.

**Correção sugerida:** Make `refresh` do `self._connection = None`, load the stored endpoint, call `await self._connect_to_discovered(stored_endpoint, None)` inside a try/except that builds the failure state (the same mapping as `check_connection`), and call `save` only on success. Never call `clear()` in the service. Replace the test with `test_refresh_keeps_the_stored_endpoint_when_nothing_is_found` and add one where the stored UUID is preferred after a refresh.

### F-07 · Task 8 · L4 · revisor c · parte c

**Onde:** Task 8, Passo 3/7/11 read_free_space_in_bytes (`while not nearest_existing_folder.exists()` ... `shutil.disk_usage`) plus ACC-9 ("raises OutputFolderUnavailableError when the folder does not exist")

**Problema:** ACC-9 as worded maps only a missing folder to OutputFolderUnavailableError. A folder that exists but cannot be inspected (macOS Files and Folders/TCC denial for ~/Documents, ~/Desktop or a removable volume, a parent without search permission, an input/output error on a half-ejected disk) still escapes the reader as a raw PermissionError or OSError. ApplicationStateService.build_state catches only OutputFolderUnavailableError, so every GET /api/state poll (0.5 to 2 s) would answer 500 and the UI would stop working. ensure_capacity is only partly protected, because prepare_output_folder runs first under ACC-8.

**Evidência:** python3: Path('/private/var/root/x').exists() -> PermissionError [Errno 13]; shutil.disk_usage('/private/var/root/x') -> PermissionError. Path.exists() ignores only ENOENT, ENOTDIR, EBADF and ELOOP. Also shutil.disk_usage(<existing regular file>) succeeds and reports free space, so a folder setting that points at a file passes the guard.

**Correção sugerida:** Write the ACC-9 reader as: `try: if not folder.is_dir(): raise OutputFolderUnavailableError(...); return shutil.disk_usage(folder).free  except OSError as error: raise OutputFolderUnavailableError(f"Cannot read the free space of {folder}: {error}") from error` (keep the first raise outside the OSError handler or re-raise it). Add boundary tests for: missing folder, folder that is a file, and PermissionError (monkeypatch shutil.disk_usage in the module). Update the T8 notes paragraph that still says the reader climbs to the nearest parent. State in the ACC-9 text that every OSError maps to OutputFolderUnavailableError, so T10's `build_state` test also needs a case where the reader raises it for a non-missing reason.

### F-08 · Task 11 · L4 · revisor d · parte d

**Onde:** application_factory.py create_application (only RequestValidationError is registered) and application_settings_service.parse_output_folder / prepare_output_folder

**Problema:** Spec 6.5 says every error response is {"code","message"}, and 4.4 has `unexpected_error` for any other failure. Nothing in T11 produces that shape for unexpected exceptions, unknown routes or wrong methods. A bad `output_folder` in PUT /api/settings can also escape the domain errors and end as a plain-text 500.

**Evidência:** Ran the plan's create_application with TestClient(raise_server_exceptions=False). PUT /api/settings with output_folder "~nouserxyz/x" gives `500 text/plain Internal Server Error`. Path('~nouserxyz/x').expanduser() raises RuntimeError('Could not determine home directory.'), and Path('/tmp/a\0b').mkdir() raises ValueError('embedded null byte'); neither is an OSError, so `except OSError` in prepare_output_folder does not catch them. GET /api/nothing gives `404 {"detail":"Not Found"}`, POST /api/health gives `{"detail":"Method Not Allowed"}`, and the thumbnail 404 has an empty body. The page's `response.json()` then gets text or a different shape.

**Correção sugerida:** In T11 add (a) `parse_output_folder` wrapping `expanduser()` in `try/except RuntimeError` and raising InvalidSettingsError, plus rejecting a path containing '\0' with InvalidSettingsError, each with a test; and (b) in create_application a handler for `Exception` (and for `starlette.exceptions.HTTPException`) that answers `{"code":"unexpected_error","message": web_configuration.error_message_catalog.message_for("unexpected_error")}` with 500 (or the original status for HTTPException). Add factory tests for an unknown route and a raising controller, using `TestClient(..., raise_server_exceptions=False)`.

### F-09 · Task 11 · L1 · revisor d · parte d

**Onde:** test_scan_controller.py fixture `client`: `ApplicationSettingsService(InMemoryApplicationSettingsRepository(SETTINGS))`; and the ACC-8 text in the Files, Interfaces, Coverage, Step 7, Step 8 and Step 26 of T11

**Problema:** Extra impact of ACC-8 beyond the listed changes. Once `folder_preparer` has no default, the call in test_scan_controller.py raises TypeError at fixture time and all 6 scan-controller tests error. Several other pieces of T11 prose and numbers also go stale.

**Evidência:** The plan's current signature is `folder_preparer: Callable[[Path], None] = prepare_output_folder`, and only test_scan_controller.py builds the service with one argument; the other tests pass a preparer. The Interfaces 'Produces' line lists `prepare_output_folder(folder)` and `WRITE_PROBE_FILE_NAME` in application_settings_service.py. The Coverage paragraph claims the prepare_output_folder cases (existing folder created, no permission, path under a file). Step 8 says `28 passed` and Step 26 says `125 passed`. The 9 `test_prepare_output_folder_*` and `test_probe_file_name_is_hidden` tests (9 of the 28) move to T7.

**Correção sugerida:** When applying ACC-8: pass a no-op preparer (e.g. `lambda folder: None`, as the factory test already does) in test_scan_controller.py. Remove `prepare_output_folder`, `WRITE_PROBE_FILE_NAME` and the 9 preparer tests from T11, and change Step 8 to 19 passed. Recompute Step 26 to 116 passed, assuming no other test changes (ACC-9/ACC-11 tests will shift it again). Drop the preparer sentence from Coverage and Interfaces, and remove the `Callable`/`Path` imports from the service only if they become unused (Path stays for `parse_output_folder`).

### F-10 · Task 12 · L3 · revisor e · parte e

**Onde:** tests/web/test_static_assets.py: `test_script_ignores_repeated_key_presses` (`"event.repeat" in read_static_file("application.js")`) and Step 7 marked 'opcional'

**Problema:** Review Focus 2 (repeated Space, double click) names T12 as the task whose test locks that behaviour. The only automated checks are substring greps, so a script that mentions `event.repeat` in a comment or never calls start_scan from the key handler still passes. Neither Space handling, button disabling, nor format_byte_count is exercised. The one executable check (Step 7 with node) is optional and not committed. Space reservation for inputs and selects is also unchecked.

**Evidência:** All 27 tests are regex or substring matches. I ran the plan's JS under node: format_byte_count and describe_pages_remaining work, but nothing in the pytest suite would notice if they broke (e.g. 999950 -> '1,0 MB' boundary).

**Correção sugerida:** Add a pytest module that runs node: pure functions (format_byte_count boundaries 0, 999, 1000, 999949, 999950, 1234567, 5e9; describe_pages_remaining 0/1/N) plus a vm-context stub DOM that fires keydown events (Space with repeat=false then repeat=true, Space inside INPUT, a second Space while pending) and counts calls to POST /api/scans via a stub fetch. Skip with an explicit reason only when `shutil.which('node')` is None. Each run is about 50 ms.

### F-11 · Task 13 · L4 · revisor e · parte e

**Onde:** iniciar-digitalizadora.command: `if [[ ! -x .venv/bin/python ]]; then ... make setup ...`

**Problema:** The launcher decides setup is done by checking only that .venv/bin/python exists. `make setup` creates the venv first and installs afterwards. If the first run is offline or pip fails, `.venv/bin/python` stays behind and the next double-click skips setup. It then starts `python -m digitalizadora` with no dependencies and no installed package, so the user only sees 'O Digitalizadora fechou logo depois de abrir' and never recovers short of deleting .venv by hand. The failure message also blames the internet even when the real cause is Python 3.9 failing `requires-python >=3.12`.

**Evidência:** Makefile setup runs `$(PYTHON) -m venv .venv`, then `pip install --upgrade pip`, then `pip install -e .`. If any later step fails, the first step's .venv/bin/python is already executable. `python -m digitalizadora` runs from the project root, but the package lives in src/, so it is not importable without the editable install and fails with ModuleNotFoundError.

**Correção sugerida:** Replace the condition with `if [[ ! -x .venv/bin/python ]] || ! .venv/bin/python -c 'import digitalizadora, fastapi, uvicorn' 2>/dev/null; then`, so a half-built venv re-runs `make setup`. Also change the failure message to 'Não consegui preparar o ambiente. Confira a internet e se `python3 --version` é 3.12 ou mais novo (use make setup PYTHON=python3.12).' Document the PYTHON override in the README.

### F-12 · Task 13 · L2 · revisor e · parte e

**Onde:** tests/test_composition_root.py: fixture `record_source` (`monkeypatch.setattr(composition_root, "ZeroconfServiceRecordSource", lambda: source)`) and `test_serving_state_never_contacts_the_scanner_or_discovery`

**Problema:** ACC-12 removes monkeypatching of composition_root and offers only ContainerOverrides(scanner_transport, gateway_timing, free_space_reader). There is no seam for the discovery record source, so after the fixer pass `record_source` and its `collect_count == 0` assertion cannot be written without a new contract. Every composition test takes this fixture, so the omission affects the whole file, not one test.

**Evidência:** Spec 6.5 ContainerOverrides has three fields, none for ServiceRecordSource. The fixture is requested by all 11 composition-root tests.

**Correção sugerida:** Either add `service_record_source: ServiceRecordSource | None = None` to ContainerOverrides in spec 6.5 first (ACC-12 extension), or drop the discovery half of the test. If dropped, remove the fixture and keep only the `request_count == 0` assertion on RecordingScannerTransport, which the existing raise-on-request transport already enforces. Real ZeroconfServiceRecordSource() construction does no I/O (network starts in collect_records), so no seam is needed for the other tests.

### F-13 · Task 14 · L1 · revisor e · parte e

**Onde:** running_scan fixture: `await wait_for_state_asynchronously(client, is_scan_running)` followed by `test_rejected_second_request_does_not_start_another_job` (`len(job_requests) == 1`)

**Problema:** The fixture yields as soon as `/api/state` reports a phase other than idle. The phase turns PREPARING in begin_scan, before ensure_capacity, acquire_gateway (status request), capabilities and POST ScanJobs. The test then counts requests ending in /ScanJobs immediately after the 409. If the state poll lands during PREPARING, the count is 0 and `== 1` fails. In my replica the poll happened to see 'scanning' with all requests already issued, but nothing in the plan guarantees that ordering. Sync endpoints and to_thread give the poll real suspension points, so the test can fail intermittently. The same weakness applies to the other two 409 tests, which assume the scan is already held at NextDocument.

**Evidência:** ScanService order (spec 6.4): begin_scan -> ensure_capacity -> acquire_gateway -> mark_scanning -> scan_page. `is_scan_running` is `phase != 'idle'`. The gate only blocks paths ending in /NextDocument, which come after POST ScanJobs. Experiment review-e/exp1.py confirmed that httpx.ASGITransport.post only returns after the BackgroundTask ends, so `first_request` stays pending as intended; only the readiness condition is racy.

**Correção sugerida:** Make the fixture wait for a deterministic condition: poll `scan_environment.scanner_app.received_paths` (yielding with `await asyncio.sleep(0)`) until some path ends with DOCUMENT_PATH_SUFFIX, i.e. the scan is parked at the gate. Alternatively add an `asyncio.Event` `document_requested` that InstrumentedScannerApp sets when it first sees NextDocument, and `await` it (with `asyncio.wait_for`). Drop the real `asyncio.sleep(0.01)` polling.

### F-14 · Task 0 · L1 · revisor f (GLOBAL REVIEWER) · parte a

**Onde:** T0 `docs/spike-0/README.md` section 0.7 (the block `sleep 600 / dns-sd -B _uscan._tcp local. / curl ... / scripts/probe-printer.sh ...`) and the `dns-sd` block in 0.2

**Problema:** `dns-sd -B` and `dns-sd -L` never exit on their own. In the 0.7 block the commands after `dns-sd -B` (the `curl` and the probe script) only run if the user presses Ctrl-C. Ctrl-C also discards the buffered lines of a pasted block, so the later commands are lost. Step 13 says to 'run the commands of section 0.7', so a literal run stalls at `dns-sd`. In 0.2 the three `dns-sd -B` lines in one block have the same problem.

**Evidência:** The macOS `dns-sd -B` browses until interrupted. The README text 'Cada comando fica rodando; aperte Ctrl-C' applies to 0.2 only, and 0.7 puts the command in the middle of a sequence.

**Correção sugerida:** Bound each `dns-sd` call, for example `dns-sd -B _uscan._tcp local. & browse_pid=$!; sleep 5; kill $browse_pid`. Do the same for `-L` and for the `_uscans`/`_ipp` browses. Alternatively, split 0.7 into separate blocks, each marked 'Ctrl-C after 5 s'. Keep the commands of Passos 8 and 13 consistent with the README.

### F-15 · Task 9 · L4 · revisor f (GLOBAL REVIEWER) · parte b

**Onde:** T9 `ZeroconfServiceRecordSource.collect_records` and `PrinterConnectionService.acquire_gateway` (first-run path with no saved endpoint)

**Problema:** The Local Network case is only detected when a saved endpoint exists. With no saved endpoint, or after `refresh()` clears it, the only network activity is Bonjour. `collect_records` has no OSError/errno 65 handling, and the zeroconf library most likely only logs a failed multicast send. An empty discovery then raises a plain `ScannerUnreachableError` (`scanner_unreachable`, no mention of Terminal.app). The Local Network case is most likely on the first run from the wrong terminal, which is where the orientation message is needed most.

**Evidência:** The only errno-65 tests are `test_blocked_local_network_error_survives_an_empty_discovery` (a stored endpoint whose status call raises) and `test_check_connection_reports_a_blocked_local_network`. Both start from a stored endpoint. `grep EHOSTUNREACH|errno` over lines 8379-9522 finds no handling in the zeroconf source. T5 only maps `httpx.ConnectError` to errno 65 for unicast requests. I did not run zeroconf; the claim that it only logs the failed send is reasoned, not verified.

**Correção sugerida:** Choose one and pin it with a test. Option A: let `ZeroconfServiceRecordSource` or `BonjourScannerDiscovery` surface an `OSError` with errno `EHOSTUNREACH` as `LocalNetworkBlockedError`, and have `acquire_gateway` re-raise it when discovery is empty. Option B: document in the T9 notes and the README that the first run from the wrong terminal shows `scanner_unreachable`, and add the Terminal.app hint to the `printer_detail` text. The Review Focus line 'Rede Local bloqueada (T5, T9)' must then say which case is covered. Edit part-b (T9); if the catalog text changes, also part-d (T11) and the spec.

### F-16 · Task 11 · L1 · revisor f (GLOBAL REVIEWER) · parte d

**Onde:** T11 `tests/controllers/test_scan_controller.py` fixture `client`: `settings_service = ApplicationSettingsService(InMemoryApplicationSettingsRepository(SETTINGS))`

**Problema:** This is extra impact of ACC-8. The fixture builds `ApplicationSettingsService` with one argument and relies on the default `folder_preparer=prepare_output_folder`. ACC-8 makes `folder_preparer` mandatory and removes the default, so every test in this module fails at fixture setup with `TypeError`. The ACC table only names the settings-service tests, the settings controller and T13.

**Evidência:** `grep ApplicationSettingsService(` finds line 11909 (`ApplicationSettingsService(InMemoryApplicationSettingsRepository(SETTINGS))`) and line 14622 (`ApplicationSettingsService(repositories.settings)`). Only 14622 is covered by the ACC text. Line 12681 in the factory test already passes `lambda folder: None`.

**Correção sugerida:** In T11, Ciclo 5, `test_scan_controller.py`, build the service as `ApplicationSettingsService(InMemoryApplicationSettingsRepository(SETTINGS), lambda folder: None)`. Better, add a shared `NoOpFolderPreparer` or `StubFolderPreparer` to `controller_test_support.py` and reuse it in the settings-controller and factory tests.

### F-17 · Task 12 · L3 · revisor f (GLOBAL REVIEWER) · parte e

**Onde:** T12 `tests/web/test_static_assets.py::test_script_ignores_repeated_key_presses` (`assert "event.repeat" in read_static_file("application.js")`) plus the Review Focus line for failure mode 2 (T10, T11, T12)

**Problema:** The Review Focus lists T12 as the test that pins 'Espaço repetido / clique duplo'. The only automated browser-side check is a substring search. The string would also pass if it sat in a comment, or if `start_scan()` ignored `is_start_request_pending`. The behaviour (keydown with `repeat` ignored, button disabled while the POST is pending, Space ignored in inputs and selects, only one POST) is pinned only by a manual table (Passo 9) and checklist items A9-A11. The server-side 409 is tested, but the first line of defence in the browser is not.

**Evidência:** All 27 asset tests are file-existence, regex or substring checks. The only executable JS check is the optional `node -e` for `format_byte_count`. The plan itself shows the vm technique in Passo 7, and `node --check` and `node -e` work on this machine (node 25).

**Correção sugerida:** Add one pytest module, `tests/web/test_scan_page_behaviour.py`, that runs the real `application.js` in `node` with a tiny fake `document`/`fetch`. Skip it with `shutil.which("node")` if node is missing. Cases: (1) two `keydown` events with `repeat=true` produce one POST; (2) two `click` calls while the POST is pending produce one POST; (3) `keydown` Space with the target an INPUT produces no POST. Alternatively, state in T12 that mode 2 is covered by T10/T11 plus the manual table and drop T12 from the Review Focus line.

## Menores

### F-18 · Task 0 · L1 · revisor a · parte a

**Onde:** scripts/probe-printer.sh NextDocument loop: `elif [ "$last_http_status" = "200" ]; ... else break`

**Problema:** Any status other than 503 or 200 ends the wait, including a 404 before the first page. Spec 6.2 rule 5 says 404 before the first page means retry a few times, and the plan's own gateway will retry. The Gate 0 probe would report "ERRO: nenhuma imagem" for a printer that works, and the decision table could then wrongly conclude the printer cannot scan.

**Evidência:** Mock printer returning 404 on the first NextDocument and 503/200 afterwards: the script printed `GET NextDocument -> HTTP 404 (curl 0)`, sent the DELETE and exited without an image.

**Correção sugerida:** Treat 404 like 503 for the first few attempts (for example a named constant `NOT_FOUND_RETRY_LIMIT=5`) and keep `break` for other statuses. Mention in README 0.4 that a 404 is retried.

### F-19 · Task 0 · L2 · revisor a · parte a

**Onde:** scripts/probe-printer.sh (GET ScannerStatus result is only recorded) and README Passo 10 "DELETE ... -> HTTP 200 (ou 204)"

**Problema:** The probe reads ScannerStatus but never checks `Idle` before the POST (spec rule 3). When the printer is still Processing the POST returns 503, and the message says "Confira a porta e o caminho base", which misleads the Gate 0 user. Also, after a successful NextDocument many devices have already dropped the job, so the DELETE may return 404, but the Expected text lists only 200/204.

**Evidência:** fail_unexpected_status prints a fixed hint for every status. In the script, `scanner_state` is only passed to record_summary.

**Correção sugerida:** After reading the status, if `scanner_state` is not `Idle`, wait up to 30 s polling every 2 s (use named constants) and record it. Special-case 503 in fail_unexpected_status ("a impressora está ocupada"). Change the README and Passo 10 text to "HTTP 200, 204 ou 404 (o trabalho já terminou)".

### F-20 · Task 0 · L1 · revisor a · parte a

**Onde:** docs/spike-0/README.md section 0.7: one code block with `sleep 600`, `dns-sd -B _uscan._tcp local.`, `curl ... --connect-timeout 5`, then `scripts/probe-printer.sh`

**Problema:** `dns-sd -B` never exits by itself and needs Ctrl-C. In a pasted multi-line block, an interrupt may drop the remaining commands in the shell. The curl uses `--connect-timeout 5`, but 0.7 is meant to measure the wake-up delay of a sleeping printer, so a wake-up longer than 5 s shows as a curl error instead of a measured delay.

**Evidência:** Section 0.2 correctly tells the user to Ctrl-C each dns-sd separately. Section 0.7 mixes all four commands. The Mac and shell cannot be assumed to continue after SIGINT. I did not run an interactive zsh paste, so the first part is a risk, not a measured failure.

**Correção sugerida:** Split 0.7 into separate steps, with the dns-sd on its own line followed by "Ctrl-C depois de 5 s". Alternatively use `dns-sd -B _uscan._tcp local. & sleep 5; kill $!`. Use `--connect-timeout 30` and `--max-time 60` in the timing curl of 0.7.

### F-21 · Task 1 · L1 · revisor a · parte a

**Onde:** Task 1 Passos 9-13 (tests/test_hardware_marker.py) and tests/conftest.py

**Problema:** The tests call `pytest_collection_modifyitems` directly with fake items, so they would still pass if pytest never loaded the hook (a renamed hook, conftest in the wrong folder, an added `-p no:...`). Nothing marked `hardware` exists until Task 14, so the claim in the Interfaces ("pulado a menos que DIGITALIZADORA_HARDWARE_TESTS=1") is not verified end to end in T1. The suite could not detect that the real skip mechanism is dead.

**Evidência:** Passo 13 expects `8 passed`, with no skipped test. A skipped hardware test appears in no T1 step.

**Correção sugerida:** Add a Passo that creates a throwaway marked test (for example `tests/hardware/test_marker_wiring.py` with `@pytest.mark.hardware def test_wiring(): assert True`) and expect `1 skipped` without the variable and `1 passed` with `DIGITALIZADORA_HARDWARE_TESTS=1`, then keep it as a committed test or delete it. Alternatively use pytester.

### F-22 · Task 2 · L3 · revisor a · parte a

**Onde:** tests/domain/test_scan_file_naming_policy.py, `test_extract_sequence_number_rejects_names_outside_the_pattern` parameters

**Problema:** ACC-6 and spec 6.1 require lowercase names only, but no case exercises that. An implementation that wrongly uses `re.IGNORECASE`, accepts `.jpeg` or accepts a trailing newline would pass every test. The boundary "exactly 5 digits" appears only as 4 digits; there is no 4/5/6-digit side by side beyond 99999 and 100000.

**Evidência:** The parameter list contains notes.txt, empty string, .png, .pdf.part, no extension, 4 digits, 00000, letters, a prefix. Reasoning: with `re.IGNORECASE` added to the pattern, every listed case still behaves identically and the whole file stays green.

**Correção sugerida:** Add rejected cases `"2026-10-13_00007.PDF"`, `"2026-10-13_00007.JPG"`, `"2026-10-13_00007.jpeg"`, `"2026-10-13_00007.pdf\n"` and `"2026-10-13_00007 .pdf"`. Add an accepted case `"2026-10-13_000007.jpg"` (6 digits).

### F-23 · Task 3 · L4 · revisor a · parte a

**Onde:** Task 3, Passo 16 `extract_job_path`: `urlsplit(location_header.strip()).path.rstrip("/")`

**Problema:** Two real-world Location shapes are handled wrongly. (1) A malformed IPv6 host makes `urlsplit` raise a raw ValueError, which is not a ScanFailedError. sane-airscan documents a Xerox firmware that returns `http://[fe80/eSCL/ScanJobs/4060`. Spec 6.2 rule 1 says "ignora o host", and spec section 8 lists "Location com host estranho" as a boundary case. (2) A relative Location without a leading slash (`ScanJobs/12`) comes back as `ScanJobs/12`, and the gateway would then build `http://hostScanJobs/12`.

**Evidência:** Run: `extract_job_path('http://[::1/eSCL')` -> ValueError: Invalid IPv6 URL. `extract_job_path('ScanJobs/12')` -> 'ScanJobs/12'. sane-airscan airscan-escl.c lines 957-980 (quirk_broken_ipv6_location) strips this host by hand. The probe script with such a Location looped until its 180 s limit, because it requested `http://127.0.0.1:18082ScanJobs/1/NextDocument`.

**Correção sugerida:** Parse without `urlsplit` host validation. Catch ValueError and fall back to cutting everything up to the first `/` after `://`. Raise ScanFailedError when the result does not start with `/`. Add parametrized cases `http://[fe80/eSCL/ScanJobs/4060` -> `/eSCL/ScanJobs/4060` and `ScanJobs/12` -> ScanFailedError (match "job location").

### F-24 · Task 3 · L4 · revisor a · parte a

**Onde:** Task 3, Passo 20(a) `ENTITY_DECLARATION_PATTERN = re.compile(rb"<!ENTITY", re.IGNORECASE)` applied to the raw bytes

**Problema:** The entity refusal is a byte-level search on the raw document, so a UTF-16 document (BOM, declared encoding="UTF-16") hides `<!ENTITY` from it and expat expands the entities. The plan states this check as the defence, and the test only uses ASCII.

**Evidência:** Run: a UTF-16 document with `<!ENTITY a "ha"><!ENTITY b "&a;&a;">` passes the refusal. `parse_scanner_status` returns `ScannerStatus(state=UNKNOWN)` without raising, and `parse_scanner_capabilities` fails only because of the root name.

**Correção sugerida:** Besides the byte regex, refuse any document that does not start as ASCII-compatible XML (reject a UTF-16/32 BOM or NUL bytes with ScanFailedError), or parse with an `XMLParser` whose `entity` handling is disabled (for example `parser.parser.EntityDeclHandler = <function that raises>`). Add a UTF-16 test case to the entity test.

### F-25 · Task 3 · L2 · revisor a · parte a

**Onde:** Task 3 fixture `scanner-capabilities-hp-deskjet-2800.xml` and parse_scanner_capabilities; Interfaces line "medida inválida"

**Problema:** The parser only understands `DiscreteResolutions`, and a platen of 0 or a negative size passes as valid. (1) sane-airscan also reads `scan:ResolutionRange` (airscan-escl.c lines 225-270). For a device that exposes only a range, `supported_resolutions` becomes `()`, and `closest_supported_resolution` returns the requested value unchecked, with no test for it. (2) The Interfaces promise ScanFailedError for "medida inválida", but only non-integers are rejected, so `MaxWidth` 0 or -5 would produce a zero-size ScanRegion. (3) sane-airscan sends `scan:DocumentFormatExt` in the request whenever the capabilities advertise it, and the synthetic fixture advertises it but build_scan_settings_xml never sends it (spec 6.2 fixes the request, so this is only to be recorded as a Gate 0 check).

**Evidência:** sane-airscan airscan-escl.c lines 886-887 (`if (src->flags & DEVCAPS_SOURCE_SCAN_DOCFMT_EXT) xml_wr_add_text(xml, "scan:DocumentFormatExt", mime)`) and lines 454-470 (min/max validation). The fixture's SettingProfile structure itself matches the sane-airscan reader (Platen/PlatenInputCaps/MinWidth/MaxWidth/SettingProfiles/SettingProfile/ColorModes/DocumentFormats/SupportedResolutions).

**Correção sugerida:** Reject `platen_maximum_width/height <= 0` with ScanFailedError (add two tests with 0 and -1). Document the ResolutionRange limitation in the T3 text, or parse `ResolutionRange/XResolutionRange/Min,Max`. In Passo 23 (comparison with the real capture) add a line to check whether the real XML contains `DocumentFormatExt` or `ResolutionRange`.

### F-26 · Task 5 · L3 · revisor b · parte b

**Onde:** Task 5, Passo 13 test `test_scanner_that_becomes_idle_just_before_the_limit_is_still_used`

**Problema:** The test is named as a boundary test but is not one. The script is busy, busy, idle, so the printer becomes ready at 4 s of a 6 s limit. A wrong comparison such as `>` instead of `>=`, or an off-by-one in the loop, would still pass.

**Evidência:** With `TEST_BUSY_WAIT_SECONDS = 6.0` and a readiness interval of 2.0, `_wait_until_ready` runs three sleeps (2, 4, 6) before raising. The script `[busy, busy, idle]` finishes after 2 sleeps.

**Correção sugerida:** Use three busy replies and then idle, with `delays == [READINESS_INTERVAL_SECONDS] * 3`, to test the exact limit. The existing 'busy past the limit' test already covers the sibling case. Rename it `..._becomes_idle_exactly_at_the_limit_is_still_used`.

### F-27 · Task 5 · L4 · revisor b · parte b

**Onde:** Task 5, Passo 21-23 (`scan_page` `finally: await self._delete_job(job_path)`), no cancellation test

**Problema:** The spec's cleanup rule (DELETE always sent) also covers cancellation, for example shutdown during a 20-60 s scan. No test pins it. `_delete_job` also swallows only `DigitalizadoraError`, so any other exception in the finally block (for example `httpx.InvalidURL` from `build_request`, outside the try) would replace the original error.

**Evidência:** I ran a MockTransport whose NextDocument handler awaits `asyncio.sleep(30)` and cancelled the task. The sequence was capabilities, status, POST, NextDocument, `DELETE /eSCL/ScanJobs/1`, so the behaviour is correct today, but nothing guards it. `_delete_job` calls `build_request` before its `try`.

**Correção sugerida:** Add a test `test_cancelled_scan_still_sends_the_delete`: run `scan_page` in a task, make the NextDocument handler block on an `asyncio.Event`, call `task.cancel()`, and assert `count(DELETE_ROUTE) == 1`. Move `build_request` inside the `try` and catch `(DigitalizadoraError, httpx.HTTPError)` in `_delete_job` (use `httpx.InvalidURL` explicitly if needed).

### F-28 · Task 6 · L1 · revisor c · parte c

**Onde:** Task 6, Passo 7, find_jfif_payload_start (`if header_end > len(jpeg_content) or jpeg_content[position] != MARKER_PREFIX_BYTE: raise ScanFailedError`)

**Problema:** The marker walk rejects a valid JPEG in which a marker is preceded by 0xFF fill bytes (ITU T.81 B.1.1.2 allows any number of fill bytes before any marker). Such a file would end as scan_failed after a 20-60 s scan that cannot be repeated for that sheet. No test covers fill bytes.

**Evidência:** Scratch run: j = build_sample_jpeg(); j[:2] + b'\xff' + j[2:] (a fill byte before the JFIF marker) -> with_resolution(..., 300) raises ScanFailedError. Without the fill byte it works.

**Correção sugerida:** At the top of the loop skip fill bytes: `while position + 1 < len(jpeg_content) and jpeg_content[position] == MARKER_PREFIX_BYTE and jpeg_content[position + 1] == MARKER_PREFIX_BYTE: position += 1` (before computing header_end), and add one parametrized test case, e.g. `START_OF_IMAGE + b'\xff' + <rest of a valid JPEG>` must be accepted, with the density rewritten and the scan data intact. Alternatively document that a fill byte is rejected on purpose and add the test that pins it.

### F-29 · Task 6 · L4 · revisor c · parte c

**Onde:** Task 6, Passo 15 ThumbnailService (`except OSError as error:`) and Passo 11 PdfAssemblyService (`except img2pdf.ImageOpenError`)

**Problema:** A JPEG header that declares an absurd size makes Pillow raise Image.DecompressionBombError, which is not an OSError, so it escapes both services. It is mapped to unexpected_error instead of scan_failed, which breaks Review Focus 4 (unexpected image becomes scan_failed).

**Evidência:** Scratch run: patching width and height to 60000 in the SOF0 segment of build_sample_jpeg() -> ThumbnailService().build_thumbnail raises PIL.Image.DecompressionBombError; its MRO is (DecompressionBombError, Exception, BaseException, object), with no OSError.

**Correção sugerida:** In ThumbnailService catch `(OSError, Image.DecompressionBombError)`. Add a test case with a SOF-patched JPEG declaring 60000x60000 pixels to test_unreadable_content_raises_scan_failed (build it in the test with bytes patching) and to test_unexpected_content_raises_scan_failed in test_scan_encoder.py.

### F-30 · Task 6 · L2 · revisor c · parte c

**Onde:** Task 6, tests/services/test_scan_encoder.py and test_pdf_assembly_service.py (no test of a PDF built from a JPEG without JFIF)

**Problema:** Review Focus 4 and spec section 8 promise a test that the PDF comes out with the right page size even when the scanner JPEG has no JFIF density. Every PDF test uses build_sample_jpeg(), which always carries a JFIF segment with unit 0 or 72 dpi. The no-JFIF case is only tested in JpegResolutionService, never through ScanEncoder with OutputFormat.PDF or JPEG.

**Evidência:** grep strip_jfif_segment: it is defined and used only in test_jpeg_resolution_service.py. test_scan_encoder.py builds all inputs with build_sample_jpeg.

**Correção sugerida:** Add to test_scan_encoder.py a helper that strips the JFIF segment (move strip_jfif_segment to tests/fakes/sample_images.py or reuse it) and two tests: `test_pdf_page_size_is_right_for_a_scan_without_jfif` (600x300 px at 600 dpi -> 72x36 pt) and `test_jpeg_output_gets_the_requested_density_when_the_scan_had_no_jfif`.

### F-31 · Task 6 · L3 · revisor c · parte c

**Onde:** Task 6, test_requests_the_jpeg_draft_mode_before_decoding (Passo 13)

**Problema:** The test name promises that draft is requested before decoding, but the recorder only stores (mode, size). An implementation that calls image.load() first and draft afterwards (a no-op in Pillow, because JpegImageFile.draft returns early once the tile is consumed) passes, so the performance contract is not pinned.

**Evidência:** The wrapper recording_draft appends (mode, size) and delegates, regardless of the image state. Pillow's JpegImageFile.draft starts with `if len(self.tile) != 1: return`, so after load() a late call is silently ignored but still recorded. Both Pillow 10.4 and 12.3 passed the test with the plan's order.

**Correção sugerida:** Record `len(image.tile)` at call time: `recorded_requests.append((mode, size, len(image.tile)))`, and assert `recorded_requests[0] == ("RGB", (100, 100), 1)`.

### F-32 · Task 7 · L4 · revisor c · parte c

**Onde:** Task 7, Passo 7 AtomicFileWriter (`temporary_path_for` gives a fixed name per destination; `_write_temporary_file` first calls `remove_temporary_file(temporary)`)

**Problema:** Two writers racing for the same final name (the case the plan itself simulates with RacingFileWriter) share one `.NAME.part` file. The second one deletes the first one's temporary file and creates its own, and the first then runs `os.link(temporary, destination)` on the second writer's path, which may be only partly written, so a partial file can end up under the final name. Focus 5 says this must never happen. The tests only cover a sequential race.

**Evidência:** Reasoning on the code: A opens .X.part (O_EXCL); B calls remove_temporary_file(.X.part) (unlink succeeds), then creates a new .X.part. A finishes and os.link(.X.part -> X) publishes B's inode before B's flush_to_disk. A's finally then unlinks the path B still needs, and B fails with FileNotFoundError.

**Correção sugerida:** Make the temporary name unique per write, ending in `.part` so the naming policy still ignores it: `f".{destination.name}.{os.getpid()}.{secrets.token_hex(4)}.part"` (or tempfile.mkstemp(dir=..., prefix='.', suffix='.part')), and drop the unlink-then-O_EXCL step. Keep the test for a stale .part by changing it to 'a stale .part does not change the result and does not break the write'. Optionally clean `.*.part` older than a day in prepare_output_folder. If the fixed name is kept on purpose (spec 4.5 shows `.part` only), document that single-process use is assumed.

### F-33 · Task 8 · L3 · revisor c · parte c

**Onde:** Task 8, tests/services/test_storage_guard_service.py vs test_scan_output_service.py (RecordingFreeSpaceReader defined twice) and `test_refusal_asks_the_reader_about_the_given_folder`

**Problema:** The same fake (RecordingFreeSpaceReader) is copied in two test modules, and a third copy exists in part-e (line 2275 region). The ACC-8/ACC-9 changes will have to be repeated in each. The test named 'refusal...' actually passes with exactly the required space, so nothing is refused and the name is wrong. test_in_memory_application_settings_repository.py also lives in tests/repositories, while the other fake tests (test_fixed_clock, test_sample_images) sit next to the fakes.

**Evidência:** Plan text: identical class bodies at Task 8 Passo 5 and Passo 13; the guard test calls `build_guard(required_free_space(COLOR_AT_300))`, which is the accept case.

**Correção sugerida:** Create tests/fakes/recording_free_space_reader.py once (listed under Files, used by both test modules and by T14) and import it. Rename the test to `test_guard_asks_the_reader_about_the_given_folder`. Move the in-memory repository test to tests/fakes/test_in_memory_settings_repository.py.

### F-34 · Task 10 · L4 · revisor c · parte d

**Onde:** part-d.md Task 10 ScanService._scan_and_store (`self._scan_output_service.ensure_capacity(job.request)`), made heavier by ACC-8

**Problema:** ensure_capacity does blocking file system work (disk_usage and, after ACC-8, mkdir plus a write probe on the output folder) directly on the event loop, while store() is correctly run via asyncio.to_thread. A sleeping external hard disk can take several seconds to answer, freezing every request (including the state poll that shows progress) for that time.

**Evidência:** part-d.md lines 999-1005: `ensure_capacity` called synchronously, `store` through `asyncio.to_thread`.

**Correção sugerida:** Use `await asyncio.to_thread(self._scan_output_service.ensure_capacity, job.request)` and add a test like test_store_runs_outside_the_event_loop_thread for the capacity check. Check that the T10 phase test (phase PREPARING during the check) still holds.

### F-35 · Task 10 · L4 · revisor d · parte d

**Onde:** scan_service._scan_and_store `self._scan_output_service.ensure_capacity(job.request)` and the `async def` handlers read_state / update_settings (build_state, settings update + prepare)

**Problema:** Blocking file-system work runs on the event loop thread. ACC-8 makes `ensure_capacity` do mkdir plus a write probe, and `update` and `build_state` also touch the disk. A sleeping or slow external disk (the main use case) freezes `/api/state` polling and any other request for the duration.

**Evidência:** `ensure_capacity` is called directly from the coroutine, while `store` already uses `asyncio.to_thread`. `read_state` is `async def` and calls `build_state()`, which does `settings_repository.load()` plus two free-space reads. `update_settings` is `async def` and calls `folder_preparer`.

**Correção sugerida:** In ScanService use `await asyncio.to_thread(self._scan_output_service.ensure_capacity, job.request)` (the existing phase test still passes because the recording fake only reads the tracker). Declare `read_state` and `update_settings` as plain `def` so Starlette runs them in its threadpool. Adjust the tracker docstring (snapshot reads from other threads are benign) or keep it and accept the stall.

### F-36 · Task 10 · L4 · revisor d · parte d

**Onde:** test_scan_service.py `test_every_gateway_error_records_its_own_code` parametrize; test_printer_controller.py; test_state_controller.py

**Problema:** The extra Local Network case is not pinned in this range. `LocalNetworkBlockedError` (code `local_network_blocked`, a subclass of ScannerUnreachableError) is never exercised through ScanService, the printer JSON or the state JSON.

**Evidência:** The parametrize list is `[ScannerBusyError, ScanFailedError, ScanTimedOutError]`. The printer tests use only `scanner_unreachable`, and the state tests only `insufficient_storage` and an unknown code. A regression to `mark_failed("scanner_unreachable")` for the subclass would pass every test.

**Correção sugerida:** Add `LocalNetworkBlockedError` and `ScannerUnreachableError` to that parametrize list. Add a printer-controller test with `error_code="local_network_blocked"` expecting the catalog message, and a state test with the same last_error_code.

### F-37 · Task 10 · L3 · revisor d · parte d

**Onde:** test_scan_service.py `test_scan_one_file_ends_idle_with_one_completed_scan` (4 asserts), `test_second_call_leaves_the_running_scan_untouched`; test_printer_controller.py `test_put_address_uses_the_manual_address_and_reports_the_connection` (3 asserts); test_catalog `len(EXPECTED_MESSAGES) == 11`; `test_probe_file_name_is_hidden`; `test_prepare_output_folder_accepts_an_existing_folder`

**Problema:** Several tests break the one-concept rule, and a few barely can fail. The `len(EXPECTED_MESSAGES) == 11` assert checks a literal against itself. The probe-name test only restates a constant. The existing-folder test passes for a function that does nothing.

**Evidência:** The first test checks phase, counter, last_result and error code in one test. The printer-address test checks status, display_name, the recorded address and check_count together. `assert tmp_path.is_dir()` is already true before the call.

**Correção sugerida:** Split the multi-concept tests into one assertion each, or turn them into small helpers. Drop the literal-length assert (the dict equality already pins the set). In the existing-folder test assert that a missing probe or no error is raised and that a pre-existing file is untouched (already covered by the keeps_existing_files test), or remove it.

### F-38 · Task 11 · L3 · revisor d · parte d

**Onde:** application_settings_service.py: `EnumMember = TypeVar("EnumMember", bound=Enum)` and `def parse_enum_member(enum_type: type[EnumMember], ...) -> EnumMember`

**Problema:** With `target-version = "py312"`, `select = [..., "UP"]` and an unpinned `ruff` dependency, `make lint` (ruff check) will flag this generic function with UP047 (non-pep695-generic-function) and fail.

**Evidência:** ruff changelog 0.12.x, 0.12.0 stabilized list: `non-pep695-generic-function (UP047)` and `non-pep695-generic-class (UP046)`. part-a pyproject has `"ruff"` without a version, and only UP042 is ignored. ruff is not installed here, so I could not run it, and I did not confirm that the rule flags a bounded TypeVar in particular.

**Correção sugerida:** Write `def parse_enum_member[EnumMember: Enum](enum_type: type[EnumMember], raw_value: str, field_label: str) -> EnumMember:` (PEP 695, Python 3.12) and delete the `TypeVar` import and the module-level TypeVar. Alternatively drop the generic and have two small parsers.

### F-39 · Task 11 · L2 · revisor d · parte d

**Onde:** local_request_guard.py FORBIDDEN_HOST / MISSING_REQUEST_HEADER messages; test_error_message_catalog `test_the_catalog_has_exactly_the_eleven_messages_of_the_specification`

**Problema:** Spec 4.4 says the Portuguese text exists only in the ErrorMessageCatalog. The guard hardcodes two Portuguese messages (forbidden_host, missing_request_header) that are in neither the spec table nor the catalog.

**Evidência:** The guard's constructor is fixed by spec 6.5 as `(app, allowed_hosts)`, so it cannot receive the catalog. The catalog test pins exactly 11 messages, so adding the two codes there would break the spec table.

**Correção sugerida:** Pick one and record it. Either add one sentence to spec 4.4 or 6.5 saying the two guard rejections are the only texts that live in the guard, or add the two codes to the spec table and the catalog and have the guard import the module-level `ERROR_MESSAGES` mapping read-only. Do not change the guard's constructor.

### F-40 · Task 11 · L3 · revisor d · parte d

**Onde:** state_controller.py `from digitalizadora.controllers.settings_controller import build_settings_body`; printer_controller.py `MANUAL_ADDRESS_REQUIRED_PREFIX` check

**Problema:** Layering and thin controllers. StateController depends on a sibling controller module, and PrinterController holds an input-validation rule (the address must start with http://) instead of delegating to a service.

**Evidência:** Spec 6.5 and the 4.1 diagram say controllers only translate HTTP to and from services. `build_settings_body` is a shared serializer, not a settings-controller concern. The prefix check is business validation, with its own 5-case test.

**Correção sugerida:** Move `build_settings_body` into a small shared module (for example `controllers/settings_body.py`, added to Files and the commit list). Leave the address rule where it is only if the spec is amended to say so; otherwise, as ACC-10 now keeps `use_manual_address` free of validation, document the controller rule in T11's Interfaces.

### F-41 · Task 11 · L4 · revisor d · parte d

**Onde:** printer_controller.py `refresh_printer` / `update_printer_address` (no scan-in-progress check)

**Problema:** The global constraint 'requisições eSCL sequenciais' is enforced only by the UI. POST /api/printer/refresh and PUT /api/printer/address run `clear()`, `use_manual_address` and `check_connection()` (a GET ScannerStatus to the printer) while a scan is polling NextDocument. The server happily forgets the saved endpoint mid-scan.

**Evidência:** PrinterController has no access to ScanService and no 409 path; spec 6.5 fixes its constructor to `(printer_connection_service, error_message_catalog)`. T12 polls /api/printer only in idle, but a user clicking a refresh or address button during a scan, or a stale tab, still reaches these routes.

**Correção sugerida:** Either confirm in T12 that the refresh and address controls are disabled while the phase is not idle, and add that to its UI test, or extend the spec 6.5 contract with a scan-state dependency and answer 409 `scan_already_running`. The first option needs no contract change.

### F-42 · Task 12 · L2 · revisor e · parte e

**Onde:** application.js `render_storage` / index.html `#storage-warning` (ACC-9 extra impact)

**Problema:** Besides the line ACC-9 asks for, the fixer must also handle the 5 GB warning. With output_folder_available false the state is StorageState(0, 0, False), so the current rule `free_space_in_bytes < 5 GB` shows 'Recomendado: use um disco externo' next to the 'Pasta de saída indisponível...' text, which is wrong for an unplugged external disk. The manual-verification table (Step 9), the asset test and checklist rows A13/B10 need the unavailable-folder message too.

**Evidência:** render_storage: `storage_warning.hidden = storage.free_space_in_bytes >= EXTERNAL_DISK_WARNING_BYTES`.

**Correção sugerida:** In render_storage, when `storage.output_folder_available === false` set storage_line to 'Pasta de saída indisponível. Se for um disco externo, confira se está conectado.' and `storage_warning.hidden = true`. Add the exact message to the string checks in test_static_assets.py and a row to Step 9 and the checklist.

### F-43 · Task 13 · L2 · revisor e · parte e

**Onde:** composition_root.py: `SCANNER_READ_TIMEOUT_SECONDS = 180.0`, `SCANNER_WRITE_TIMEOUT_SECONDS = 10.0`, `SCANNER_POOL_TIMEOUT_SECONDS = 5.0` and the comment 'NextDocument may block while the carriage moves; 600 dpi ... minute and a half'

**Problema:** Spec 6.5 fixes the production client at `httpx.Timeout(connect 5 s, read 30 s)`. The plan uses read 180 s and invents write and pool values. The justifying comment is also wrong: the gateway (T5) passes an explicit timeout on every request, with NextDocument using scan_timeout_seconds and everything else connect 5 s / read 30 s. The client-level values are therefore never used by the EsclScannerGateway.

**Evidência:** part-b line 1872: 'A requisição de NextDocument usa como tempo de leitura o próprio scan_timeout_seconds (conexão 5 s); as demais usam conexão 5 s e leitura 30 s.' I confirmed in httpx that build_request(timeout=...) overrides the client default (extensions['timeout'] = {'connect':5,'read':30,...}).

**Correção sugerida:** Use the spec values: `httpx.Timeout(connect=5.0, read=30.0)` (httpx needs write and pool too: `httpx.Timeout(30.0, connect=5.0)`), with two named constants. Delete the misleading comment. If a longer read is really wanted, change spec 6.5 first.

### F-44 · Task 13 · L4 · revisor e · parte e

**Onde:** __main__.py `uvicorn.run(application, host=..., port=..., log_level="info")` and `configure_logging`

**Problema:** Two logging problems. (1) uvicorn's default LOGGING_CONFIG gives the `uvicorn` loggers their own handlers with propagate False, so uvicorn error tracebacks never reach ~/Library/Logs/Digitalizadora/digitalizadora.log, although the UI tells users to look there. (2) With log_level info and the default access log, every /api/state poll (every 0.5-2 s) prints a line in the Terminal, burying the 'Digitalizadora pronto' instructions.

**Evidência:** uvicorn.run signature (main.py): `log_config=LOGGING_CONFIG`. Experiment: after logging.config.dictConfig with a non-propagating 'uvicorn' logger, 'uvicorn error' went to stderr only, while 'before'/'after' app lines stayed in the file.

**Correção sugerida:** Call `uvicorn.run(application, host=..., port=..., log_level="info", log_config=None, access_log=False)` so uvicorn records propagate to the root handlers (file and terminal) without access lines, and update the exact-options assertion in `test_run_application_serves_on_the_configured_loopback_port`.

### F-45 · Task 13 · L4 · revisor e · parte e

**Onde:** iniciar-digitalizadora.command readiness loop (`until curl ... /api/health`)

**Problema:** If the app is already open (port taken), the new python exits with 'A porta ... já está em uso', but the first curl succeeds against the old instance before the new process has died. The launcher then opens the page and prints 'Digitalizadora aberto...' and 'Mantenha esta janela aberta...' right below the port-in-use message, which contradicts it. The `wait` returns immediately and the window is useless.

**Evidência:** Readiness uses only /api/health, which any process on the port can answer. The kill -0 check runs only when curl fails.

**Correção sugerida:** Before starting the server, run `if curl --silent --fail "$HEALTH_ADDRESS" >/dev/null 2>&1; then open "$PAGE_ADDRESS"; echo 'O Digitalizadora já está aberto em outra janela.'; exit 0; fi`.

### F-46 · Task 13 · L2 · revisor e · parte e

**Onde:** Task 13 / ACC-9 startup preparation: `prepare_output_folder(configuration.default_output_folder)`

**Problema:** ACC-9 prepares default_output_folder at startup, but the folder actually used is the one in settings.json. After the user moves output to an external disk, every startup recreates ~/Pictures/Digitalizadora on the small internal disk for nothing, while the folder in use is never prepared or checked at startup.

**Evidência:** Spec 6.5: 'Na partida tenta prepare_output_folder(configuration.default_output_folder)'. The Json settings repository holds the real folder (T7/T11).

**Correção sugerida:** In build_container, prepare `repositories.settings.load().output_folder` (which equals the default until the user changes it), log a warning on OutputFolderUnavailableError, and update spec 6.5 accordingly.

### F-47 · Task 13 · L4 · revisor e · parte e

**Onde:** configuration.py `_read_output_folder`: `return Path(configured_folder)`

**Problema:** DIGITALIZADORA_OUTPUT_FOLDER is accepted even when relative or starting with '~'. It becomes the default settings folder and prepare_output_folder would create it relative to the current directory (the project folder after the launcher's cd), while the settings service demands absolute paths. Port is validated, the folder is not.

**Evidência:** Spec 6.4: settings folder must be an absolute path. Test `test_output_folder_can_be_overridden` only covers an absolute value.

**Correção sugerida:** After stripping, reject non-absolute values with ValueError naming DIGITALIZADORA_OUTPUT_FOLDER (or expand '~' with home_directory), and add parametrized tests for 'relative/dir' and '~/Scans'.

### F-48 · Task 13 · L4 · revisor e · parte e

**Onde:** Step 9 manual verification, make run-simulated, acceptance checklist Part A

**Problema:** The simulator runs use the user's real data directory. `use_manual_address` writes the 127.0.0.1:8080 endpoint to the real ~/Library/Application Support/Digitalizadora/scanner-endpoint.json, and every PUT /api/settings (JPG, Foto, ~/Digitalizadora-teste) persists in the real settings.json. Part B (real printer) then starts with the test folder and format. The endpoint is recovered through discovery, but the settings are not, and the DIGITALIZADORA_OUTPUT_FOLDER env var only applies when settings.json is missing.

**Evidência:** Spec 4.5 and the composition root: data_directory = home/Library/Application Support/Digitalizadora with no override; Path.home() honours $HOME.

**Correção sugerida:** Add a note to Step 9, the README simulator section and checklist A2 to run with an isolated home (`HOME=$HOME/Digitalizadora-teste-home make run-simulated`) or to delete settings.json and scanner-endpoint.json before Part B. A step in Part B should set the output folder explicitly.

### F-49 · Task 14 · L1 · revisor e · parte e

**Onde:** tests/integration/test_scan_flow.py: `job_requests = [path for path in scan_environment.scanner_app.received_paths if path.endswith(SCAN_JOBS_PATH_SUFFIX)]`

**Problema:** The line is 121 characters. After ACC-5 (ruff line-length 120) it breaks E501, so Step 6's `make lint` expecting 'All checks passed!' fails. Under the current T1 value of 100 about 45 lines in part-e (test signatures, imports) already fail, so the ACC-5 change is mandatory for this part.

**Evidência:** A length scan of part-e python blocks found a single line over 120, at 121 columns. The 109- to 116-column lines pass at 120.

**Correção sugerida:** Wrap the comprehension over two lines, e.g. `job_requests = [\n    path for path in scan_environment.scanner_app.received_paths if path.endswith(SCAN_JOBS_PATH_SUFFIX)\n]`.

### F-50 · Task 14 · L3 · revisor e · parte e

**Onde:** test_host_header_with_another_port_is_rejected (`!= 200`) in tests/test_composition_root.py

**Problema:** The assertion also passes for 404 or 500, so a wrong rejection path goes unnoticed. The guard (T11) answers exactly 403 with code forbidden_host.

**Evidência:** part-d LocalRequestGuard: `JSONResponse(status_code=HTTPStatus.FORBIDDEN, ...)`.

**Correção sugerida:** Assert `status_code == 403` (HTTPStatus.FORBIDDEN).

### F-51 · Task 14 · L2 · revisor e · parte e

**Onde:** Step 2 troubleshooting table, row 1: 'ver `contract_change_requests` deste plano'

**Problema:** There is no such section in the plan. After ACC-8 the behaviour is a spec contract (6.4 ensure_capacity), so the reference points nowhere.

**Evidência:** grep of the assembled plan shows no 'contract_change_requests' heading outside this row.

**Correção sugerida:** Replace with 'ver spec 6.4 (ScanOutputService.ensure_capacity) e 6.3 (ensure_output_folder_ready)'.

### F-52 · Task 14 · L3 · revisor e · parte e

**Onde:** acceptance checklist B3 'cerca de 216 × 297 mm (A4)' and README Makefile target `probe`

**Problema:** 216 x 297 mm is the glass size the app scans (spec 6.2 rule 2), not A4 (210 x 297), so a tester comparing to A4 can mark a correct PDF as wrong. Separately, `make probe HOST=...` cannot pass the printer port, but the probe script defaults to 8080 and the spec says never to fix the port.

**Evidência:** Spec 6.2: 'a página tem o tamanho do vidro, 216 × 297 mm'. probe-printer.sh usage `<host> [port=8080] [base_path=eSCL]`.

**Correção sugerida:** Write 'cerca de 216 × 297 mm (o vidro inteiro)' in B3. Add an optional `PORT` make variable: `scripts/probe-printer.sh $(HOST) $(PORT)` and update the -n expectation and README.

### F-53 · Task 0 · L1 · revisor f (GLOBAL REVIEWER) · parte a

**Onde:** T0 Passo 5, the `Expected:` block for `scripts/probe-printer.sh 127.0.0.1 9`

**Problema:** The expected output omits three lines the script really prints before the failing GET line.

**Evidência:** I ran the plan's script against 127.0.0.1:9. After `===== Resumo do Gate 0 =====` it prints `Capturas em: <path>`, `Host: 127.0.0.1  Porta: 9  Caminho base: eSCL`, `Data (UTC): ...` and then `GET ScannerCapabilities -> sem resposta (curl 7)`. The plan lists only the last line. The curl message also ends with 'after 0 ms: Couldn't connect to server'. The `status=2` usage case is correct.

**Correção sugerida:** Add the three lines (with `...` for the path and date) to the expected block, or rewrite the Expected as 'contains the lines ERRO..., Resumo and status=1'.

### F-54 · Task 2 · L2 · revisor f (GLOBAL REVIEWER) · parte a

**Onde:** T2 note 'se o Gate 0 decidiu limitar o preset PHOTO a 400 dpi, troque ... no Passo 3 e ... no teste do Passo 1'; T0 Passo 15 row 4

**Problema:** The 400 dpi instruction is incomplete. The value 600 dpi for Foto is also hard-coded in other places that the note does not mention, so the app would show 'Foto (600 dpi, cor)' while scanning at 400.

**Evidência:** `index.html` option text 'Foto (600 dpi, cor)' and the T12 manual table (lines 13194 and 14061); the README T13 'Foto (600 dpi, cor)'; the checklist items B6 and A8 (600 dpi); the spec 7 labels. The T2 note edits only the constant and one test row.

**Correção sugerida:** Extend the T2 note, or the T0 decision row, with the full list of places to edit when PHOTO changes: T12 `index.html` and its manual table, T13 README, T14 checklist B6. Better, derive the label from the preset (an `/api/settings` field or a data attribute) so only one value exists.

### F-55 · Task 8 · L3 · revisor f (GLOBAL REVIEWER) · parte c

**Onde:** T8 `test_storage_guard_service.py` and `test_scan_output_service.py`, T10 `test_application_state_service.py`: `class RecordingFreeSpaceReader`; T10 `test_scan_progress_tracker.py` and T11 `test_preview_controller.py`: `def build_stored_scan`

**Problema:** There are duplicated test doubles with diverging shape. `RecordingFreeSpaceReader` is defined three times, with the attribute `requested_folders` in two copies and `folders` in the third. `build_stored_scan` is defined twice with different signatures (default thumbnail versus mandatory). They are copy-paste violations of the DRY rule, and the two attribute names will trip up later tasks.

**Evidência:** Definitions at lines 7840, 8144 and 10570 (`RecordingFreeSpaceReader`) and at 9575 and 12296 (`build_stored_scan`), all in different test modules.

**Correção sugerida:** Create the double once in T8 (for example `tests/fakes/recording_free_space_reader.py`, attribute `requested_folders`) and a `tests/fakes/stored_scans.py` with `build_stored_scan` in T10. Import them in T8, T10 and T11, and list the new files under Files and in the commit steps. Edit part-c (T8) and part-d (T10, T11).

### F-56 · Task 11 · L2 · revisor f (GLOBAL REVIEWER) · parte d

**Onde:** T11 `local_request_guard.py` (`FORBIDDEN_HOST`, `MISSING_REQUEST_HEADER` with Portuguese messages) and T12 `application.js` (`UNEXPECTED_ERROR_MESSAGE`, `SERVER_UNREACHABLE_MESSAGE`)

**Problema:** Spec 4.4 says 'o texto em português só existe no ErrorMessageCatalog' and lists eleven codes. The guard invents two more codes (`forbidden_host`, `missing_request_header`) with their own Portuguese texts outside the catalog. The JS duplicates the `unexpected_error` text.

**Evidência:** `test_foreign_host_is_rejected_with_forbidden_host` expects `code == "forbidden_host"`. The catalog test fixes exactly 11 messages and the README table lists eleven codes.

**Correção sugerida:** Either add the two guard codes and messages to the spec 4.4 table and the catalog (and the README table), with the guard receiving the catalog by constructor or the messages as constructor data from the composition root, or record the exception in the spec. For the JS, take the fallback text from the server payload only.

### F-57 · Task 11 · L2 · revisor f (GLOBAL REVIEWER) · parte d

**Onde:** T11 `ScanController.start_scan` and the background task `_run_scan`; Review Focus mode 2

**Problema:** The check `is_scan_in_progress()` and `begin_scan` are not atomic. `begin_scan` runs inside the background task, after the 202 is sent. A second POST in that window gets 202, not 409. The duplicate task only logs `ScanAlreadyRunningError` and the running scan stays intact, so there is no data risk, but the claim 'a segunda chamada vira 409' is not strictly true. The JS guard (`is_start_request_pending`) and the one-line window make it unlikely.

**Evidência:** The Starlette `BackgroundTasks` ordering. I checked with `fastapi 0.136.3` that the POST response is sent before the task starts and that `httpx.ASGITransport` returns only after the task ends. `_run_scan` catches `DigitalizadoraError` and only logs it.

**Correção sugerida:** Document this in the T11 notes, or call `begin_scan` synchronously in the controller path before scheduling. The second option changes the ScanService contract, which would need a spec change first.

### F-58 · Task 11 · L2 · revisor f (GLOBAL REVIEWER) · parte d

**Onde:** Dependencies: T11 `from pydantic import BaseModel`, `from starlette ...` (controllers, guard) versus the header 'Dependências: exatamente as da seção 6.7'

**Problema:** `pydantic` and `starlette` are imported directly but are not listed in spec 6.7 or in `pyproject.toml`; they arrive only as transitive dependencies of `fastapi`. The header rule says any other dependency needs a user decision.

**Evidência:** My import scan of all python blocks: `pydantic` appears at lines 11799 and 12492, and `starlette` at lines 11330, 11517 and 15236.

**Correção sugerida:** Add one sentence to the plan header or to T11 that pydantic and starlette are accepted transitive dependencies of FastAPI (no new `pyproject` entry), or add them to spec 6.7.

### F-59 · Task 13 · L2 · revisor f (GLOBAL REVIEWER) · parte e

**Onde:** T13 `build_scanner_http_client`: `SCANNER_READ_TIMEOUT_SECONDS = 180.0` (comment 'NextDocument may block ... about a minute and a half') together with `write=10`, `pool=5`

**Problema:** The spec (6.5) fixes the production client as `httpx.Timeout(connect 5 s, read 30 s)`. T13 uses a 180 s read timeout, so the contract and the comment disagree. The gateway overrides the timeout on every request (5/30 s, and 5 s/`scan_timeout_seconds` for `NextDocument`), so the client value never takes effect and the comment is misleading.

**Evidência:** T5 `_default_timeout` and `_get_next_document` pass `timeout=` to `build_request`.

**Correção sugerida:** Use `read=30.0` as in spec 6.5 (or change the spec first) and drop the misleading comment about 600 dpi.

### F-60 · Task 13 · L1 · revisor f (GLOBAL REVIEWER) · parte e

**Onde:** T13 `_build_controllers` (`error_message_catalog = ErrorMessageCatalog()`) and `_build_web_configuration(configuration, http_client)`, with the ACC-11 and ACC-12 changes

**Problema:** This is extra impact of ACC-11. `WebInterfaceConfiguration` now needs the same catalog that the controllers receive. Today `_build_controllers` creates its own catalog and `_build_web_configuration` has two parameters. Passing the catalog without a third shared object breaks the 3-parameter limit or creates a second catalog instance. T13 `tests/test_composition_root.py` also calls `build_container(config, scanner_transport)` positionally, which ACC-12 changes to `ContainerOverrides`.

**Evidência:** T13 lines 14629-14647.

**Correção sugerida:** Create `ErrorMessageCatalog()` once in `build_container` (or `_build_catalog`) and pass it to both builders. Pack `_Services` and the catalog into one small dataclass if a function would exceed 3 parameters. Update the T13 tests to `build_container(configuration, ContainerOverrides(scanner_transport=...))`.

### F-61 · Task 13 · L2 · revisor f (GLOBAL REVIEWER) · parte e

**Onde:** T13 README (full text) versus spec D10 and the Gate 0 README

**Problema:** D10 requires: do not update macOS before Gate 0 and the MVP, record the build in each validation, and repeat Gate 0 after any update. The Gate 0 README says 'não atualizar' only until Gate 0 ends. The checklist records `sw_vers`. The final README has no line telling the user to repeat Gate 0 after a macOS or firmware update.

**Evidência:** `grep -i atualiz` finds only T0 lines 328 and 567 and a T3 line; the README of T13 has no such guidance.

**Correção sugerida:** Add a short 'Depois de atualizar o macOS ou o firmware da impressora' section to the T13 README, with the Gate 0 and `make probe HOST=...` steps and the `sw_vers` note.

### F-62 · Task 14 · L2 · revisor f (GLOBAL REVIEWER) · parte e

**Onde:** T14 Passo 1, test `test_rejected_second_request_does_not_start_another_job`: `job_requests = [path for path in scan_environment.scanner_app.received_paths if path.endswith(SCAN_JOBS_PATH_SUFFIX)]`

**Problema:** After ACC-5 the ruff line length is 120. This line has 121 characters, so `ruff check` (E501) fails in the T14 lint gate, `make lint` in Passo 6.

**Evidência:** My scan of every python block in the draft found exactly one line over 120 characters: line 15518 (121 characters). With the current `line-length = 100` many lines would fail, which is why ACC-5 raises it to 120.

**Correção sugerida:** Split the comprehension over two lines, or extract a helper `count_job_requests(scanner_app)`.

### F-63 · Task 14 · L1 · revisor f (GLOBAL REVIEWER) · parte e

**Onde:** T14 Passo 2 troubleshooting table, row 1: 'ver `contract_change_requests` deste plano'; Interfaces notes mentioning `monkeypatch.setattr(composition_root, ...)`

**Problema:** The row refers to a section (`contract_change_requests`) that does not exist in the plan. It also tells the executor to fix `ScanOutputService.ensure_capacity` in T8, which ACC-8 already designs. The interface notes describe monkeypatching of `composition_root`, which ACC-12 replaces with `ContainerOverrides`.

**Evidência:** `grep contract_change_requests` finds only lines 10789 and 15539; neither a section nor a file with that name exists.

**Correção sugerida:** Remove the dangling reference. Point the troubleshooting row to the ACC-8 design (`ensure_output_folder_ready` called first). Rewrite the notes of T13 and T14 after ACC-12.

### F-64 · Task 14 · L4 · revisor f (GLOBAL REVIEWER) · parte e

**Onde:** T14 'Cobertura do Review Focus' and the test list of `tests/integration/test_scan_flow.py`

**Problema:** T14 covers failure modes 2 and 3 end to end. There is no automated end-to-end test for an unreachable printer (mode 1) or for the new ACC-9 state (`storage.output_folder_available == false` with the folder missing). Both are covered only by unit tests and by the manual checklist rows A16-A18 and B9-B10.

**Evidência:** The 16 listed tests only cover accept, PDF/JPG output, thumbnail, unavailable folder, full disk and the three 409 cases.

**Correção sugerida:** Add two short integration tests. Test 1: build the app with a `scanner_transport` that raises `httpx.ConnectError`, post a scan, and assert `last_error.code == "scanner_unreachable"` and that no job request was made. Test 2: remove the output folder and assert `GET /api/state` returns `storage.output_folder_available == false` and `free_space_in_bytes == 0`.

### F-65 · Task 14 · L2 · revisor f (GLOBAL REVIEWER) · parte e

**Onde:** T14 hardware test: `SCAN_DOTS_PER_INCH = 150` and `ColorMode.GRAYSCALE` versus spec section 8 'Hardware: uma digitalização real a 300 dpi'

**Problema:** The spec's hardware test row says one real scan at 300 dpi. The plan scans at 150 dpi in grayscale, which does not exercise the default Documento preset.

**Evidência:** T14 line 15572 versus spec section 8, row 'Hardware (opcional)'.

**Correção sugerida:** Use 300 dpi (`ScanPreset.DOCUMENT.settings`) or change the spec row to 150 dpi with the reason (speed).

## O que os revisores confirmaram como correto

**Revisor a**

- bash -n clean on scripts/probe-printer.sh; works on bash 3.2.57 with BSD curl/sed/grep/sips/file against a stdlib mock printer (200/503/201/Location/DELETE)
- Probe scan-request.xml is one line, has the XML declaration glued to the root, xmlns:pwg before xmlns:scan, the right prefixes and child order (ACC-1), and is byte-identical to build_scan_settings_xml(ScanSettings(300, COLOR), fixture caps)
- Probe order of elements matches sane-airscan airscan-escl.c lines 848-889 (Version, ScanRegions with ContentRegionUnits/XOffset/YOffset/Width/Height, InputSource, ColorMode, DocumentFormat, XResolution, YResolution; escl:ThreeHundredthsOfInches unprefixed)
- Passo 5 expectations (port 9 -> curl 7 message, status=1; no arguments -> usage, status=2) reproduce exactly; Location with absolute URL is reduced to a path; EXIT trap sends the DELETE
- tomllib parses pyproject.toml; the pytest tables are valid; hook with only `items`, `from tests.conftest import ...` and the 6 hardware-marker tests pass under pytest 9.1.1 with the plan's layout
- Every test count in T1-T3 (2, 6, 8; 8, 25, 33, 15, 11, 92, 100; 13, 26, 38, 50, 55, 155) reproduced by running the extracted code; whole suite ran in 0.13 s
- extract_sequence_number matches ACC-6 for all listed inputs (other date, .part, 4 digits, 00000, lowercase only via fullmatch)
- closest_supported_resolution boundary tests (149/151, 299/301, 600/601, empty, unordered) match the spec rule
- The synthetic capabilities structure matches the sane-airscan reader (PlatenInputCaps children, SettingProfiles, ColorModes, DocumentFormats incl. DocumentFormatExt, DiscreteResolutions)
- Namespace-agnostic parsing, lowercase `<!doctype` normalization and the five Passo 19 failures behave as described once the Callable import is fixed
- No line over 100 characters in any Python block; imports are isort-ordered for ruff with `tests` as first-party; layering and naming in T2/T3 follow spec section 5

**Revisor b**

- T4 final simulator and tests: 34 passed (33 functions, one parametrized x2), slowest test under 13 ms; the cycle failed/passed counts at Passos 6 and 14 match my reasoning (7 failed/11 passed, then 9 failed/25 passed)
- T4 route handlers as bound async methods with add_api_route work (path param job_number, Request body, Response return annotation) on fastapi 0.136.3
- T4 satisfies the ACC-4 exports (build_capabilities_document, build_status_document, PLATEN_MAXIMUM_WIDTH/HEIGHT, SUPPORTED_COLOR_MODES) and the ASCII 'Pagina N' label
- T5 final gateway and tests: 50 passed; the cycle-1 code passes exactly the first 7 tests; the failed counts at Passos 10, 14, 18 and 22 are right (7, 10, 11 and 7)
- T5 sleep-driven clock logic is deterministic: busy limit gives exactly 3 sleeps, scan timeout gives exactly 4 sleeps, 404 retries give 4 requests and 3 sleeps
- T5 per-request timeout values reach the transport (request.extensions['timeout'] connect/read), follow_redirects=False on send overrides a client that follows redirects, and Headers.update sets Connection: close
- T5 MockTransport accepts async handlers and an exception raised by the handler is wrapped as httpx.TransportError; ReadTimeout is the __cause__ of ScannerUnreachableError, so the ScanTimedOutError mapping works
- T5 DELETE is sent from the finally block on success, on errors and on task cancellation, and a failing DELETE never hides the original error
- T9 bonjour discovery tests (19) and PrinterConnectionService tests (29) pass; the cycle counts at Passos 22 and 26 (7 failed/10 passed, then 12 failed/17 passed) and the final total of 57 are consistent
- T9 UUID preference, cached gateway reuse with re-verification on every acquire, replacement of a gateway that stops answering, DOWN treated as unreachable, and LocalNetworkBlockedError surviving an empty discovery all behave as described
- ACC-2 (sleep param), ACC-4 and ACC-10 are already reflected in my range; no unused imports or lines over 120 characters in my files; imports are in ruff isort order; no function exceeds 3 parameters
- Task ordering and Files lists are consistent (T4 uses T2/T3, T5 uses T2/T3/T4, T9 uses T2); commit steps list the created files

**Revisor c**

- Whole part-c code and tests extracted and run: 274 passed (pytest 9.1.1; Pillow 10.4 and 12.3; pikepdf 10.17; img2pdf 0.6.3), also with -W error; per-file counts equal the plan (22, 11, 11, 15, 20, 12, 19, 20 endpoint, 23 settings, 14, 23, 9).
- Failing-run expectations re-executed with the previous-cycle code: JPEG cycle 1 vs cycle 2 tests -> 7 passed, 15 failed; AtomicFileWriter cycle 1 vs cycle 2 tests -> 6 failures with the quoted messages; output repository cycle 3 vs cycle 4 tests -> 7 failed, 12 passed; pikepdf.open on a JPEG gives 'unable to find trailer dictionary while recovering damaged file'.
- JFIF logic: offsets (units 7, X 8, Y 10, payload minimum 12), length arithmetic, 18-byte inserted segment, insertion right after SOI before Exif, SOS stop, all 8 malformed samples raise ScanFailedError, limits 1 and 65535 work, scan data byte-identical; tested on default, 72 dpi, progressive, optimized and 4:4:4 Pillow JPEGs.
- img2pdf 0.6.3: convert returns bytes without outputstream; BytesIO input avoids the file-name attempt (source convert_to_docobject); fixed-dpi layout gives 612 x 841.68 pt for 2550x3507 at 300 dpi; tz-aware creationdate becomes 'D:20261013183012Z'; JPEG stored raw with /DCTDecode (read_raw_bytes equals input); grayscale JPEG gives /DeviceGray; empty list raises ValueError (plan guards it earlier).
- pikepdf >= 10.9: Page.get_images() exists (versionadded 10.9, Page.images is deprecated), Object.read_raw_bytes exists, docinfo and mediabox behave as the tests assume; img2pdf's `pikepdf.__version__ >= '6.2.0'` string comparison is False for 10.x but only drops deterministic_id (harmless).
- Pillow: draft('RGB', (n, n)) then thumbnail keeps aspect within 1 px, never enlarges, quality 80 gives quantization[0][0] == 6 (default quality would give 8), truncated JPEG (cut 5, 30, 100 bytes) raises OSError, grayscale JPEG gives an L thumbnail; draft is called twice (second call from thumbnail with mode None), so the test's use of recorded_requests[0] is correct.
- AtomicFileWriter on macOS: fcntl.F_FULLFSYNC == 51 and works on files and directories (APFS); os.link raises FileExistsError for an existing destination; O_EXCL temp, unlink in finally, rename fallback, directory sync failure only logged; monkeypatched tests really exercise the fallbacks (mutation: rename-only implementation fails the link-race test).
- Output repository: sequence continues after gaps, shared pdf/jpg counter, other dates and extensions ignored, hidden .part ignored, retry loop makes exactly MAXIMUM_NAME_ATTEMPTS attempts (boundary tests present), read-only folder test restores permissions and is skipped as root.
- Storage guard arithmetic: 1_073_142 (300 dpi colour) and 317_968 (200 dpi gray) match; 600 dpi is exactly 4x 300 dpi; exact, +1 and -1 byte boundaries covered; estimate_pages_remaining clamps negatives to 0.
- All commit steps list the files created by their task; every file created is listed under Files; no task uses symbols from a higher-numbered task (ScanEncoder, ports and errors come from T2/T6); ruff isort order of imports and max line length 120 are fine (lines up to 120 chars rely on ACC-5).

**Revisor d**

- T10: all 62 tests pass with the plan's code (tracker 23, scripted gateway 7, ScanService 26, state service 6); the expected counts in Steps 4, 8, 12, 16 and 17 are right.
- T10 ScanService: begin_scan outside the try works. The three concurrency tests (second call, running scan untouched, first scan completes) pass; there is no deadlock and no ordering hazard, because scan_started is set before the wait on release_scan.
- T10 asyncio.Event created in a sync fixture is fine on Python 3.12, because the loop is bound lazily at the first wait.
- T10 store runs through asyncio.to_thread, and the thread-identity test is sound. mark_failed(DigitalizadoraError.code) gives 'unexpected_error', and error.code on a subclass instance gives the subclass code, so local_network_blocked is recorded correctly.
- T11: all 125 tests pass with the real fastapi 0.136.3, starlette 0.52.1 and httpx 0.27.2 (Step 4 17, Step 8 28, Step 12 22, Step 17 7, Step 21 30, Step 25 21, Step 26 125).
- TestClient waits for BackgroundTasks before post() returns (the stub's recorded requests are visible right after the call), and logging inside the task reaches caplog.
- TestClient with base_url http://127.0.0.1:8765 sends Host '127.0.0.1:8765', and headers={'host': ...} overrides it correctly for the foreign-host and localhost tests.
- Pure ASGI LocalRequestGuard: add_middleware(cls, allowed_hosts=...) works in Starlette 0.52, the guard is the outermost user middleware, and lifespan and websocket scopes are handled (the lifespan scope has no headers key, and the code skips it). JSONResponse can be awaited directly with (scope, receive, send).
- RequestValidationError handler registered with add_exception_handler gives 422 {code,message} for an empty body; StaticFiles mount, FileResponse index, disabled docs/redoc/openapi and lifespan shutdown callbacks (run once on exit, never earlier) behave as the tests claim.
- Catalog messages are byte-identical to the 11 rows of spec 4.4 (checked by script); JSON shapes of /api/settings, /api/state (apart from ACC-9), /api/printer, thumbnail (image/jpeg, no-store, 404) and /api/health match spec 6.5.
- Ruff isort ordering, line lengths (no code line over 100) and the <=3 parameters rule hold across part-d; no test defines a DigitalizadoraError subclass, so the 11-class collection test is stable.
- Files lists and commit steps of T10 and T11 cover every created file; ACC-10 (PrinterController calls check_connection after use_manual_address) and ACC-13 (module paths) are already satisfied.

**Revisor e**

- node --check passes on application.js; format_byte_count gives '0 B | 999 B | 1,0 KB | 1,2 MB | 5,0 GB'; extra boundaries (999949 -> '999,9 KB', 999950 -> '1,0 MB', 1e12 -> '1,0 TB') are consistent
- All 23 getElementById ids exist in index.html; extracted tests/web checks all hold against the plan's files (counts 27 failed, then 14 passed/13 failed, then 27 passed are correct)
- Keyboard logic is sound for the main paths: keydown+preventDefault+event.repeat, keyup preventDefault for Firefox, the button disabled synchronously before the await (double click and held Space produce a single POST), X-Requested-With sent for every non-GET
- Makefile recipes are TAB-indented; `make -n setup run simulator run-simulated test test-hardware lint probe HOST=...` prints exactly the 11 stated lines
- zsh -n passes on the launcher; with a stub server, SIGINT or SIGHUP to the process group and SIGTERM or SIGHUP to the script all stop the server and the script exits; `open` is called once after readiness
- Test counts check out: configuration 24, composition root 11, main 7, integration 16, hardware 4; imports in part-e are isort-ordered
- Constructor wiring in composition_root matches every spec 6.x signature (3 or fewer parameters, shared settings repository, shared PrinterConnectionService)
- TestClient used as `with TestClient(app)` shares one anyio portal loop for lifespan and requests, so a scanner AsyncClient bound to an ASGITransport works across requests, and lifespan shutdown closes it; BackgroundTasks finish before the TestClient POST returns
- httpx.ASGITransport only returns the POST after its background task ends; a concurrent GET /state on the same loop works, which makes the running_scan design valid
- asyncio.Event created in a sync fixture is safe on Python 3.12 (binds on first wait)
- ensure_port_is_available on macOS: bind fails with EADDRINUSE against a listener with or without SO_REUSEADDR (so the in-use tests pass)
- Full simulated page generation, thumbnail and 3 F_FULLFSYNC calls take about 20 ms, so the integration tests fit the 100 ms budget
- README lists all 11 error codes (the grep check passes); env variable table matches configuration.py

**Revisor f (GLOBAL REVIEWER)**

- G2: every `from digitalizadora.*` and `from tests.*` import resolves to a module created by the same or a lower-numbered task (script over all python blocks); no file is created in two tasks (only the Files+Test duplicate listing in T14); every symbol imported from the plan is defined somewhere in it
- G2: every task's `git add` lists exactly the files under its Files (T0 has no commit by design; T1 adds md.md, docs, scripts)
- G2: `__init__.py` count in T1 is 19 and matches the created packages; `web/static` and `tests/fixtures/escl` are data directories, which is correct
- G3: Makefile targets (setup, run, simulator, run-simulated, test, test-hardware, lint, probe) and env vars (DIGITALIZADORA_PORT/OUTPUT_FOLDER/SCANNER_ADDRESS/HARDWARE_TESTS) are used consistently in README, checklist and T12/T14; `make -n` 'onze linhas' count is right
- G3: JSON keys of /api/state, /api/settings and /api/printer match between StateController, JS and tests; the element ids used by the JS exist in the HTML and the test checks this; Expected counts checked by hand: T1 8, T2 ciclo 2 25, T8 4/14/23/32, T11 17/22/7/30/21/28/125 and T12 27/14/13 are right
- G4: failure mode 2 is pinned in T10 (tracker and service), T11 (409) and T14 (three 409 tests with the gated NextDocument); mode 3 in T7, T8 and T14 (output_folder_unavailable before the first scanner request, insufficient_storage before the first scanner request); mode 4 in T5 (PDF, empty body, no media type) and T6 (MediaBox, truncated JPEG); mode 5 in T7 (.part leftover, link race, gaps, 100000)
- G5/G7: Task 0 probe script: `bash -n` passes; run against a fake eSCL server it follows the Location path while ignoring the foreign host, polls 503, saves the JPEG and sends DELETE; its ScanSettings XML is byte-identical to the T3 builder output (ACC-1); the decision table and the 0.1-0.8 steps match spec 9
- G7: servidor só em 127.0.0.1 (host cannot be overridden, tested); Host check including port; X-Requested-With on POST/PUT/PATCH/DELETE; no CORS; no abbreviation or placeholder issues found by the static checker; no src module imports from tests; layering table has no violations; no direct `datetime.now`/`sleep` outside SystemClock and the timing defaults
- /Volumes is root:wheel 755 here, so `mkdir(parents=True)` on an unmounted external-disk path raises PermissionError and becomes output_folder_unavailable (the external-disk-unplugged case works as designed)
- Spec 4.4 messages in `ERROR_MESSAGES` are verbatim; 6.5 error shape; 6.6 simulator exports; ACC-1..ACC-13 reviewed, none judged wrong

## Símbolos de bibliotecas conferidos

Total: 60. Resultado: wrong: unknown encoding raises LookupError and a UTF-16 document bypasses the byte-level `<!ENTITY` regex; ParseError mapping itself is ok = 1, wrong for `http://[::1/eSCL` (ValueError) and for a relative path without a slash; ok for absolute, `//host/path`, query, fragment, `[fe80::1]:8080` = 1, ok = 28, unverifiable = 7, ok on 10.4; behaviour on Pillow >=12 (pyproject) unverifiable here = 1, ok for order and namespaces; shows the ResolutionRange, DocumentFormatExt and broken-IPv6 Location cases the plan does not handle = 1, wrong (the httpcore to OSError link is __context__, not __cause__; the plan's claim and traversal are incorrect) = 1, ok (default interfaces=All makes RuntimeError possible when offline) = 1, ok (documents the RuntimeError/OSError paths that the plan does not handle) = 1, wrong = 2, ok (confirms plain-text 500, {'detail':...} 404 and 405, i.e. not the {code,message} shape) = 1, ok (RuntimeError and ValueError, neither an OSError) = 1, ok (stabilization confirmed; flagging of a bound TypeVar not run) = 1, unverifiable (semantic differences from the real pytest are limited to fixture and caplog internals) = 1, ok: aclose() calls the transport's aclose(); the constructor arguments are valid = 1, ok: per-request timeout wins, so the client-level read=180 is unused by the gateway = 1, ok: POST returns only after the background scan ends; concurrent GET works in the same loop = 1, ok: single loop for the with-block; lifespan shutdown ran (closed True); POST returns 202 with the scan already finished = 1, ok: matches the plan's claim (SystemExit(1) on port in use) = 1, ok: the plan's call is valid; default log_config makes uvicorn loggers non-propagating = 1, ok: root file handler keeps working; records from a non-propagating 'uvicorn' logger do not reach it = 1, ok: EADDRINUSE for same-address listeners; a wildcard listener does not block the probe (harmless) = 1, ok (`Page.images` is deprecated; `get_images` exists) = 1, ok (POST returned 202 after the task logged 'bg-done'), so the T14 `running_scan` fixture design works = 1, ok (middleware blocks a foreign Host with 403, 422 handler returns the custom body, /docs is 404, shutdown code ran at context exit) = 1, ok (output differs from the T0 Passo 5 expected text only in omitted summary lines) = 1.
