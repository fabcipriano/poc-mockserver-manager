## Purpose

Lets a developer turn a selection of already-captured real traffic into LLM-drafted MockServer expectations — including plausible edge cases the captured traffic didn't show — that are reviewed and approved before being loaded, so QA can test against a mock that behaves like the real (currently unavailable) system without hand-writing every expectation.

## Requirements

### Requirement: Developer selects captured requests as the generation seed
The web UI SHALL let a developer select one or more entries from the currently selected MockServer target's captured request history (Recent Requests) to use as the seed corpus for generation, without requiring the legacy/real system to be reachable at generation time.

#### Scenario: Developer selects entries from Recent Requests
- **WHEN** a developer viewing Recent Requests for a target marks a subset of captured entries and proceeds to the AI Mock Generator
- **THEN** those entries' request and response data are carried forward as the seed corpus for that generation run

#### Scenario: No entries selected
- **WHEN** a developer attempts to start generation with zero entries selected
- **THEN** the UI blocks the attempt and explains that at least one captured entry is required

### Requirement: Generation drafts expectations via an LLM, on demand
Given a non-empty seed corpus, the system SHALL synchronously call a configured LLM to draft candidate MockServer expectations shaped like the seed corpus's real requests and responses, only when the developer explicitly requests generation - never automatically and never while a QA test suite is executing.

#### Scenario: Developer requests generation
- **WHEN** a developer clicks "Generate mocks with AI" for a selected seed corpus
- **THEN** the system calls the configured LLM with that seed corpus and returns a set of candidate expectations for review

#### Scenario: Generation covers edge cases beyond the literal recordings
- **WHEN** the seed corpus contains only successful (2xx) captured responses for a route
- **THEN** the candidate expectations may include plausible non-2xx variants (such as a validation error or not-found response) for that same route, shaped consistently with the response conventions observed in the seed corpus

#### Scenario: LLM generation is unavailable
- **WHEN** a developer requests generation but no LLM API key is configured for this deployment
- **THEN** the system tells the developer this feature is unavailable and takes no other action

### Requirement: Candidate expectations are reviewed before anything loads
The system SHALL present every LLM-drafted candidate expectation to the developer for review - editable and individually removable - and SHALL NOT load any candidate into MockServer until the developer explicitly approves it.

#### Scenario: Developer reviews candidates before loading
- **WHEN** generation completes
- **THEN** the developer sees each candidate expectation's method, path, status, and body before any of them are loaded into MockServer

#### Scenario: Developer discards a candidate
- **WHEN** a developer removes a candidate from the review list before approving
- **THEN** that candidate is never loaded into MockServer

#### Scenario: Developer edits a candidate before approving
- **WHEN** a developer changes a candidate's status code, body, or matchers during review
- **THEN** the edited version, not the original LLM output, is what gets loaded if approved

### Requirement: Malformed or invalid candidates are surfaced, not silently loaded
The system SHALL validate each LLM-drafted candidate against the same required-field rules applied to a manually created mock, and SHALL exclude any candidate that fails validation or that the LLM returned as malformed output from the loadable set, while still showing the developer that it was rejected and why.

#### Scenario: LLM returns an incomplete candidate
- **WHEN** a candidate is missing a required field (such as method, path, or status code)
- **THEN** the system shows that candidate to the developer as rejected with the reason, and it cannot be approved for loading

#### Scenario: LLM response is not valid JSON
- **WHEN** the LLM's response cannot be parsed into candidate expectations at all
- **THEN** the system reports the generation attempt as failed and no candidates are shown as loadable

### Requirement: Approved expectations load into the selected MockServer target through the existing mock creation path
On explicit developer approval, the system SHALL load each approved candidate into the currently selected MockServer target the same way a manually created mock is loaded, so it behaves identically to (and is indistinguishable in the Active Mocks list from) a hand-created mock.

#### Scenario: Developer approves and loads candidates
- **WHEN** a developer approves one or more reviewed candidates and confirms loading
- **THEN** those expectations become active on the selected MockServer target and appear in the existing Active Mocks list

#### Scenario: Approved expectations are ordinary mocks afterward
- **WHEN** a developer later views, edits, or deletes an expectation that was loaded through AI generation
- **THEN** it behaves exactly like any other developer-created mock, with no special AI-origin state tracked or required
