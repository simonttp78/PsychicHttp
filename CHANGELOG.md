## Unreleased

### Native ESP-IDF Support (no Arduino framework required)

PsychicHttp can now be used in pure ESP-IDF projects without the Arduino component.

**Library source:**
- `PsychicCore.h`: `urlEncode`/`urlDecode` refactored to `_impl` functions returning `std::string`; thin `#ifdef ARDUINO` wrappers preserve the `String` API for Arduino users. `PsychicUploadCallback` typedef is now conditional — Arduino keeps `const String& filename` (no user-code changes required); native IDF uses `const char* filename`. `HTTPHeader` fields are `std::string` internally; `addHeader(const String&, ...)` kept under `#ifdef ARDUINO`.
- `ChunkPrinter`, `TemplatePrinter`, `PsychicStreamResponse`: gated `#ifdef ARDUINO` (depend on Arduino `Print`/`Stream` which have no IDF equivalent); excluded from `PsychicHttp.h` on non-Arduino builds.
- `PsychicClient`: `localIP()` / `remoteIP()` return `esp_ip4_addr_t` on native IDF; `#ifdef ARDUINO` overloads returning `IPAddress` preserved for Arduino users.
- `PsychicMiddlewares` `LoggingMiddleware`: Arduino uses `Print&` / `Serial`; native IDF uses `ESP_LOGI` — same public interface.
- `PsychicEventSource`: `generateEventMessage` returns `std::string` in native IDF via internal `_generateEventMessage_impl`.
- `PsychicJson`: large JSON path uses `ChunkPrinter` on Arduino and `malloc` + one-shot send on native IDF.
- `PsychicRequest`: base64 encoding for digest auth selects `mbedtls_base64_encode` (IDF ≥ 5) vs `base64_encode_chars` (IDF 4) via `ESP_IDF_VERSION_MAJOR` guard.
- `PsychicResponse`: `equalsIgnoreCase()` → `strcasecmp()` for `std::string` compatibility; `#include <strings.h>` added.
- `MultipartProcessor`, `PsychicUploadHandler`: `std::min()` with explicit casts; `const char*` for internal string access.
- `sdkconfig.defaults` (`examples/esp-idf-pio/`): `CONFIG_HTTPD_WS_SUPPORT=y` required for WebSocket types; `CONFIG_MBEDTLS_ROM_MD5` disabled (ROM-only MD5 makes `mbedtls_md5_*` unavailable at link time).

**New example:** `examples/esp-idf-pio/` — fully native ESP-IDF PlatformIO example (WiFi STA+AP, HTTP handlers, basic auth middleware, WebSocket echo, SSE). Live tested on hardware. Builds with `[env:esp-idf-pio]` (`framework = espidf`).

### Bug Fixes

- `PsychicJsonResponse::send()` was calling itself recursively — the bare `send()` inside the method resolved to `this->send()` instead of the base `PsychicResponse::send()`, causing infinite recursion and a stack overflow on any JSON response. Fixed by calling `_response->send()` explicitly. This affected all JSON responses when not using the chunked path.
- `PsychicResponse::redirect()` was always returning HTTP 200 instead of 301 due to `_code` being initialised to 200 and the guard `if (!_code)` never triggering.
- `getContentDisposition()` and `_setUri()` used `if (start)` / `if (index)` to check `std::string::find()` results, which incorrectly skipped matches at position 0. Fixed to `!= std::string::npos`.
- `setSessionKey()` used `insert(pair<>)` which silently ignores updates to existing keys. Fixed to `operator[]`.

### New API

- `PsychicRequest::getParam(const char* key, const char* defaultValue)` — returns `defaultValue` instead of `NULL` when the parameter is not found, avoiding null pointer crashes in handlers that don’t call `hasParam()` first.
- `PsychicHttpServer::serveStatic(const char* uri, const char* path, const char* cache_control = nullptr)` — new overload that does not require an Arduino `fs::FS` reference; backed by POSIX via an ESP-IDF VFS partition. The existing `serveStatic(uri, fs::FS&, ...)` overload is preserved unchanged.
- `PsychicFileResponse(PsychicResponse*, const char* path, const char* contentType = nullptr, bool download = false)` — new constructor that opens the file by path directly via POSIX, no `FS` object required. Existing Arduino constructors (`fs::FS&` + path and `fs::File` + path) are preserved unchanged.

### API Changes: getter methods now return `const char*` instead of `String`

The following getter methods have changed their return type from `String` to `const char*` to enable native ESP-IDF support (no Arduino framework dependency):

| Method | Class |
|---|---|
| `uri()` | `PsychicEndpoint` |
| `getContentType()` | `PsychicResponse` / `PsychicResponseDelegate` |
| `name()`, `value()` | `PsychicWebParameter` |
| `from()`, `toUrl()`, `params()` | `PsychicRewrite` |
| `getSubprotocol()` | `PsychicHandler` |
| `getUsername()`, `getPassword()`, `getRealm()`, `getAuthFailureMessage()` | `AuthenticationMiddleware` |
| `getOrigin()`, `getMethods()`, `getHeaders()` | `CorsMiddleware` |
| `methodStr()`, `path()`, `uri()`, `query()`, `header()`, `host()`, `contentType()`, `body()`, `getCookie()`, `getFilename()` | `PsychicRequest` |

**For Arduino users, existing code will continue to compile without changes** — `String` has an implicit constructor from `const char*`:

| Before | After | Result |
|--------|-------|--------|
| `String path = request->path();` | `String path = request->path();` | ✅ unchanged |
| `String ct = request->contentType();` | `const char* ct = request->contentType();` | ✅ now also works |

**One edge case that breaks** — concatenating with `+` when the left operand is a string literal (you'd know if you hit this, it's a compile error):

```cpp
// ❌ Compile error: cannot add const char* + const char*
String url = "/prefix" + request->getFilename();

// ✅ Fix: use String() cast or +=
String url = String("/prefix") + request->getFilename();
// or (recommended)
String url = "/prefix";
url += request->getFilename();
```

### Example Updates (v2.x API)

- **All examples**: `server.begin()` must be called *after* all `server.on()` registrations. WebSocket and SSE endpoints are registered with `httpd` inside `begin()` / `start()`; calling `on()` after `begin()` silently registers the URL but the WS upgrade or SSE accept is never wired up.
- `examples/arduino/arduino.ino`: `StaticJsonDocument<N>` → `JsonDocument` (ArduinoJson v7); inline `request->authenticate()` / `requestAuthentication()` → `AuthenticationMiddleware` with `addMiddleware()`; `httpd_ws_frame` → `httpd_ws_frame_t`.
- `examples/arduino/arduino_ota/`, `examples/arduino/arduino_captive_portal/`: `server.begin()` added after all `server.on()` calls (was missing).
- `examples/websockets/src/main.cpp`, `examples/platformio/src/main.cpp`: `httpd_ws_frame` → `httpd_ws_frame_t`.
- `examples/esp-idf/main/main.cpp`: `server.begin()` ordering fixed; `websocketHandler.onMessage` → `onFrame`; `httpd_ws_frame` → `httpd_ws_frame_t`.

### Internal Changes

- Internal filesystem shim `PsychicFS.h`: `psychic::FS` / `psychic::File` provide a unified minimal interface used by all file-serving logic. The Arduino branch wraps `fs::FS&` / `fs::File`; the IDF branch is POSIX-backed (`fopen`/`fstat`/`fread`). The `FILE_IS_REAL` macro has been removed; its semantics are absorbed into `psychic::File::operator bool()`.
- `CMakeLists.txt`: `arduino-esp32` is no longer an unconditional `COMPONENT_REQUIRES` entry. It is now auto-detected via `idf_build_get_property(BUILD_COMPONENTS)` at configure time — if the `arduino` component is present in the project the dep is added automatically and the `ARDUINO` define flows through as before. Pure ESP-IDF projects (without the Arduino component) require no manual flag. `esp_http_server` and `mbedtls` added as explicit deps in both branches.
- `httpd` task stack size increased from 4608 to 5120 bytes. `std::string` method frames are slightly larger than Arduino `String` due to libstdc++ EH cleanup stubs, which pushed deep call chains (upload handler + middleware + digest auth) over the 4608 limit. Confirmed crash at 4608, stable at 4800; 5120 gives a ~512 byte margin. Total cost: +3.5 KB across 7 open sockets.

---

## 2.1.1

- Re-added deleted MAX function per #230

## 2.1.0 (since 2.0.0)

- send to all clients, not bail on the first one.
- Fix issue whereby H2 encoding ignores method and defaults to HTTP_GET. (#202)
- now using the stable version of pioarduino.
- V2 dev rollup: update PsychicFileResponse (set status and content type before chunked responses), fix getCookie, and add pong reply to ping. (#228, #207, #209, #222)
- Update async_worker.cpp to fix compatibility with Arduino ESP32 3.3.0. (#225)
- fixed a mistake from the pull merge.
- Moved setting content type and response code into sendHeaders(). (PR #220)
- Check if content size is 0 before sending a response. (#218)
- Fix crash with Event Source and update CI / IDF examples. (#221)
- fixed EventSource error with missing headers (content type, cache-control, keep-alive).
- fixed the CI to use the latest stable versions.
- ugh. CI so annoying.
- bump to v2.1.0.


# v2.0

I apologize for sitting on this release for so long.  Its been almost a year and life just sort of got away from me.  I'd like to get this release out and then start working through the backlog of issues.  v2.0 has been very stable for me, so it's more than time to release it.

* Huge amount of work was done to add MiddleWare and some more under the hood updates
* Modified the request handling to bring initial url matching and filtering into PsychicHttpServer itself.
    * Fixed a bug with filter() where endpoint is matched, but filter fails and it doesn't continue matching further endpoints on same uri (checks were in different codebases)
    * HTTP_ANY support
    * unlimited endpoints (no more need to manually set config.max_uri_handlers)
    * much more flexibility for future
* Endpoint Matching Updates
    * Endpoint matching functions can be set on server level (```server.setURIMatchFunction()```) or endpoint level (```endpoint.setURIMatchFunction()```)
    * Added convenience macros MATCH_SIMPLE, MATCH_WILDCARD, and MATCH_REGEX
    * Added regex matching of URIs, enable it with define PSY_ENABLE_REGEX
    * On regex matched requests, you can get match data with request->getRegexMatches()
* Ported URL rewrite functionality from ESPAsyncWS

## Changes required from v1.x to v2.0:

* add a ```server.begin()``` or ```server.start()``` after all your ```server.on()``` calls
* remove any calls to ```config.max_uri_handlers```
* if you are using a custom ```server.config.uri_match_fn``` to match uris, change it to ```server.setURIMatchFunction()```

# v1.2.1

* Fix bug with missing include preventing the HTTPS server from compiling.

# v1.2

* Added TemplatePrinter from https://github.com/Chris--A/PsychicHttp/tree/templatePrint
* Support using as ESP IDF component
* Optional using https server in ESP IDF
* Fixed bug with headers
* Add ESP IDF example + CI script
* Added Arduino Captive Portal example and OTAUpdate from @06GitHub
* HTTPS fix for ESP-IDF v5.0.2+ from @06GitHub
* lots of bugfixes from @mathieucarbou

Thanks to @Chris--A, @06GitHub, and @dzungpv for your contributions.

# v1.1

* Changed the internal structure to support request handlers on endpoints and generic requests that do not match an endpoint
    * websockets, uploads, etc should now create an appropriate handler and attach to an endpoint with the server.on() syntax
* Added PsychicClient to abstract away some of the internals of ESP-IDF sockets + add convenience
    * onOpen and onClose callbacks have changed as a result
* Added support for EventSource / SSE
* Added support for multipart file uploads
* changed getParam() to return a PsychicWebParameter in line with ESPAsyncWebserver
* Renamed various classes / files:
    * PsychicHttpFileResponse -> PsychicFileResponse
    * PsychicHttpServerEndpoint -> PsychicEndpoint
    * PsychicHttpServerRequest -> PsychicRequest
    * PsychicHttpServerResponse -> PsychicResponse
    * PsychicHttpWebsocket.h -> PsychicWebSocket.h
    * Websocket => WebSocket
* Quite a few bugfixes from the community. Thank you @glennsky, @gb88, @KastanEr, @kstam, and @zekageri