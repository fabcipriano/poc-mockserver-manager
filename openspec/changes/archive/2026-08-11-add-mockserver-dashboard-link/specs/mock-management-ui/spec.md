## MODIFIED Requirements

### Requirement: Web UI is organized around a left-hand navigation sidebar
The web interface SHALL present a persistent left-hand navigation sidebar with five destinations - Create Mock, List Mocks, Recent Requests, Help, and MockServer Dashboard - such that selecting Create Mock, List Mocks, Recent Requests, or Help shows only that destination's content in the main content area, and selecting MockServer Dashboard opens MockServer's own Dashboard UI in a new browser tab without changing what is shown in the main content area.

#### Scenario: Developer switches between pages
- **WHEN** a developer selects a different one of Create Mock, List Mocks, Recent Requests, or Help in the sidebar
- **THEN** the main content area shows only that destination's page, and the content of the previously shown page is no longer visible

#### Scenario: A page is reachable by a direct link
- **WHEN** a developer loads or reloads the web interface with a specific destination referenced in the URL
- **THEN** that destination's page is shown, without requiring the developer to navigate there manually

#### Scenario: Developer opens the MockServer Dashboard
- **WHEN** a developer selects MockServer Dashboard in the sidebar
- **THEN** MockServer's own Dashboard UI opens in a new browser tab, and the web interface's main content area continues showing whatever page was already displayed there

### Requirement: Web UI provides a Help page documenting request matchers
The web interface's Help page SHALL explain, for a developer unfamiliar with the tool, what each supported request matcher (path parameters, query string parameters, headers, cookies, request body) does and how to use it, SHALL state that the seeded catch-all forwarding expectation can never be edited or deleted through the web interface, and SHALL explain what the sidebar's MockServer Dashboard link is for and that it leads to a separate, unauthenticated vendor tool rather than a page the web interface owns.

#### Scenario: Developer learns how a matcher works from the Help page
- **WHEN** a developer navigates to the Help page
- **THEN** they find an explanation of what path parameters, query string parameters, headers, cookies, and the request body matcher each do

#### Scenario: Developer learns what the MockServer Dashboard link is for
- **WHEN** a developer navigates to the Help page
- **THEN** they find an explanation that the MockServer Dashboard link opens MockServer's own Dashboard UI in a new tab, that it shows why a request didn't match any mock (which Recent Requests doesn't show), and that it is a separate vendor tool with no authentication in this POC, not a page the web interface owns or keeps working
