## ADDED Requirements

### Requirement: Mock expectations persist across MockServer restarts
Mock expectations - both the seeded catch-all forwarding rule and any mock a developer has added - SHALL survive a restart or rescheduling of the MockServer pod, without requiring a developer to re-add anything.

#### Scenario: Dev-added mock survives a MockServer pod restart
- **WHEN** a developer has added a mock expectation and the MockServer pod is then restarted or rescheduled
- **THEN** after the pod becomes ready again, the same mock expectation is active without the developer re-adding it

#### Scenario: Catch-all is present after a restart on a brand-new volume
- **WHEN** MockServer is installed for the first time, before any developer has added a mock
- **THEN** the seeded catch-all forwarding rule is active, exactly as it is today

#### Scenario: Persisted mocks outlive an uninstall/reinstall cycle
- **WHEN** a developer runs the documented MockServer uninstall command(s) and then reinstalls MockServer
- **THEN** mock expectations that were active before the uninstall are active again after the reinstall, without being re-added
