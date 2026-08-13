## MODIFIED Requirements

### Requirement: Web UI reflects the selected MockServer target's live state with no independent cache
The web interface SHALL NOT maintain its own copy or cache of mock definitions; every list, create, update, and delete action SHALL act directly and synchronously against the currently selected MockServer target's live expectation store.

#### Scenario: UI reflects a change made outside the UI
- **WHEN** a mock is added, changed, or removed by some means other than the web interface (for example, `scripts/add-mock.sh` or a direct MockServer API call) on the currently selected target
- **THEN** the web interface's next list view reflects that change, because it queries that MockServer target directly rather than a local cache

### Requirement: Web UI remains responsive with multiple simultaneous viewers
The web interface SHALL keep the Recent Requests page responsive - including pages and endpoints unrelated to Recent Requests - when multiple developers have the page open at the same time, whether viewing the same target or different targets, regardless of how many requests any configured MockServer target has logged.

#### Scenario: Other pages stay responsive while Recent Requests is busy
- **WHEN** multiple developers have the Recent Requests page open simultaneously while a MockServer target holds a large volume of logged requests
- **THEN** the web interface's other endpoints (for example, health checks and the mocks list) continue to respond promptly rather than being blocked by Recent Requests activity

#### Scenario: Live tail cost does not scale with viewer count
- **WHEN** additional developers open the Recent Requests page for the same target while others already have it open
- **THEN** the live tail continues delivering new requests to all open viewers of that target without a proportional increase in the work performed against that MockServer target for each additional viewer

#### Scenario: Live tail cost does not scale with the number of configured targets beyond one poller each
- **WHEN** the system is configured with multiple MockServer targets, regardless of how many developers are viewing each one
- **THEN** each target is polled by exactly one background poller, and the number of viewers of a given target does not change how many times that target is polled

## ADDED Requirements

### Requirement: Web UI lets a developer select which MockServer target to view
The web interface SHALL present a MockServer target selector - a labeled dropdown (or equivalent list control) - that is visible regardless of which page (Create Mock, List Mocks, Recent Requests, Help) is currently shown, listing every MockServer target the system is configured with by its display label. Selecting a different target SHALL immediately re-scope the Create Mock, List Mocks, and Recent Requests pages to that target's live MockServer state.

#### Scenario: Developer switches MockServer target
- **WHEN** a developer selects a different target from the MockServer target selector
- **THEN** the List Mocks page's contents, the Recent Requests page's history and live tail, and any in-progress Create Mock form target the newly selected MockServer instance instead of the previous one

#### Scenario: Selector lists only configured targets
- **WHEN** a developer opens the MockServer target selector
- **THEN** it shows exactly the targets the system is currently configured with, by their display labels, and no others

#### Scenario: Selector remains visible across pages
- **WHEN** a developer navigates between Create Mock, List Mocks, Recent Requests, and Help
- **THEN** the MockServer target selector remains visible and shows the currently selected target throughout

### Requirement: Selected MockServer target persists across navigation and reload
The web interface SHALL remember which MockServer target a developer has selected, both when navigating between pages within the same session and when the page is reloaded, rather than resetting to a default target each time.

#### Scenario: Selection survives page navigation
- **WHEN** a developer selects a MockServer target, then navigates to a different page within the web interface
- **THEN** the same target remains selected on the new page

#### Scenario: Selection survives a page reload
- **WHEN** a developer selects a MockServer target and then reloads the web interface
- **THEN** the previously selected target is still selected, rather than the interface resetting to its default target

### Requirement: mock-ui is configurable to reach multiple MockServer targets without rebuilding
The mock-ui server SHALL determine the set of MockServer targets it can reach (each target's identifier, display label, and base URL) from environment variables read at process startup, such that adding, removing, or repointing a target requires only a configuration change and a restart, not a rebuild of the mock-ui container image.

#### Scenario: Adding a target requires no rebuild
- **WHEN** an operator adds a new MockServer target to the environment-variable configuration and restarts the mock-ui process, without changing any application code or rebuilding its container image
- **THEN** the new target appears in the MockServer target selector and can be selected and used like any other configured target

#### Scenario: A deployment with no multi-target configuration keeps working
- **WHEN** mock-ui is started with none of the multi-target configuration set
- **THEN** it falls back to a single default MockServer target, preserving the behavior of a deployment that has not adopted multi-target configuration
