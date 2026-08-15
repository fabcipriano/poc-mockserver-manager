## ADDED Requirements

### Requirement: Web UI bounds the live tail's DOM footprint to a fixed row cap
The web interface's Recent Requests page SHALL keep at most a fixed maximum number of rows in the live-tailed list at any time. When a request arrives via the live tail while the list already holds that maximum, the oldest displayed row SHALL be removed before the new row is added, so the page's memory and DOM footprint do not grow without bound for as long as the tail keeps running, regardless of how many requests arrive.

#### Scenario: Live tail stays at the row cap under sustained arrivals
- **WHEN** the Recent Requests page's live-tailed list already holds the maximum number of rows and a new matching request arrives via the live tail
- **THEN** the oldest row in the live-tailed list is removed and the new request is added at the top, leaving the total row count at the maximum rather than growing past it

#### Scenario: Row cap holds regardless of arrival rate or how long the tail has been running
- **WHEN** requests continue arriving via the live tail well past the point where the row cap was first reached, whether over a short burst or an extended period with the page left open
- **THEN** the displayed row count remains at the maximum throughout, and the page does not accumulate additional rows beyond it

#### Scenario: Resuming a paused tail respects the row cap
- **WHEN** a developer resumes a previously paused live tail and more queued requests were received while paused than fit under the row cap
- **THEN** only the most recent requests up to the row cap remain displayed once the backlog is applied, with older ones evicted the same as during normal live-tail operation

#### Scenario: Pagination's own loads are not constrained by the row cap
- **WHEN** a developer loads additional older requests using the Recent Requests page's "load more" control, including while the displayed list is already at the row cap
- **THEN** the requested page of older requests is loaded and displayed in full; the row cap only resumes evicting the oldest displayed row in response to subsequent live-tail arrivals, and may then remove rows that pagination added, the same as any other row
