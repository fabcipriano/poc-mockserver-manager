## Context

See `proposal.md` - Why/What Changes for motivation. Two capabilities are in scope: `poc-environment` (the emulated `ALB -> Gateway -> Backend` stack) and `mockserver-integration` (inserting MockServer as `ALB -> MockServer -> Gateway -> Backend`).

Two decisions were fixed by the user before design started, not re-litigated here:
- **Engine**: MockServer (mock-server.org, official `mockserver/mockserver` Docker image) - the "MockServer" name in the request is this project, and it natively supports both stubbing and forwarding to a real upstream.
- **Insertion point**: MockServer sits between the ALB stand-in and the Gateway (`ALB -> MockServer -> Gateway -> Backend`), so the Gateway is never touched to enable or disable mocking.

This design targets a local Kubernetes cluster (kind or minikube) since no real AWS/production access is implied by "POC."

## Goals / Non-Goals

**Goals:**
- Prove the `ALB -> MockServer -> Gateway -> Backend` topology works end-to-end in Kubernetes, with pass-through as the default and per-route mocking as an opt-in.
- Keep the "install MockServer" step to one command and confined to the ALB-to-Gateway edge - zero Gateway/Backend manifest or code changes.
- Keep authoring a mock expectation approachable for a dev who has never used MockServer.

**Non-Goals:**
- Reproducing real AWS ALB semantics (target groups, listener rules, WAF, TLS certs). The ALB is stood in by an Ingress + ingress controller purely to get an L7 entrypoint that can be repointed - see Risks.
- Making the Spring Boot 1.5 stand-in functionally equivalent to the real backend. It exists only to prove requests reach a real service through the chain.
- Designing the production rollout (how the real AWS ALB gets repointed at MockServer). That is a follow-up once the POC validates the pattern - see Open Questions.
- High availability, auth/mTLS between hops, or performance tuning of MockServer.

## Decisions

### 1. ALB stand-in = Ingress + ingress-nginx, not a bare LoadBalancer Service
An AWS ALB in front of a Kubernetes service is most commonly realized as an Ingress resource (the AWS Load Balancer Controller turns Ingress rules into ALB listener/target-group rules). Reproducing that with an Ingress + `ingress-nginx` controller on kind/minikube keeps the "repoint the entrypoint at MockServer" step analogous to what a real rollout would look like (edit the Ingress `backend.service.name`), instead of hand-rolling a proxy. Alternative considered: a plain `NodePort`/`LoadBalancer` Service pointing straight at the Gateway - rejected because it has no notion of "backend swap," which is the exact mechanic being proven.

### 2. Installing MockServer = repoint the Ingress backend, not modify the Gateway
"Install" is defined as: (a) deploy the MockServer Deployment/Service/ConfigMap, (b) patch the existing Ingress so its backend `service.name` changes from `gateway` to `mockserver`. Both steps are scripted/kustomize-overlay driven so they happen as one command. This keeps the Gateway's own manifests and app code completely untouched, matching the `mockserver-integration` spec's "transparent to the Gateway" requirement. Uninstall reverses step (b) then removes MockServer's resources.

### 3. Default pass-through via a seeded catch-all forwarding expectation + priority convention
MockServer has no built-in "forward everything unmatched" toggle by itself - forwarding is just another expectation action. The design seeds MockServer at startup (via its JSON initializer, `initializationJsonPath`, mounted from a ConfigMap) with a single catch-all expectation: matches any method/path, priority `0`, action `httpForward` to the Gateway Service's in-cluster DNS name. Developer-added expectations are created at a higher default priority (e.g. `10`) so MockServer's "highest priority wins" matching rule always prefers a specific mock over the catch-all forward, without devs needing to think about ordering beyond "use the default priority." Alternative considered: MockServer's proxy/record-replay mode - rejected as a worse fit because it optimizes for capturing real traffic, not authoring ad-hoc responses.

### 4. Two supported ways to author a mock expectation
- **Fast iteration**: call MockServer's REST expectation API directly (`PUT /mockserver/expectation` with a small JSON body: method, path, response status/headers/body). A short example/helper script is provided so a dev doesn't need to hand-write the full MockServer JSON schema from scratch.
- **Shareable/repeatable**: drop a JSON expectation file into a `mocks/` directory that is mounted into MockServer via the same ConfigMap-backed initializer used for the catch-all rule, so a mock can be committed to the repo and reloaded on pod restart.
Both paths produce the same expectation shape, so a dev can start with the REST API and later "promote" a working expectation into a committed JSON file.

### 5. Manifest layout
A single `mockserver-poc` namespace holds four component directories (`alb` = Ingress + controller reference, `gateway`, `backend`, `mockserver`), applied via `kubectl apply -k` (Kustomize) overlays: a `base` overlay for the environment alone, and a `with-mockserver` overlay that adds MockServer's resources and patches the Ingress backend. This gives a one-command install/uninstall for each state (`kubectl apply -k overlays/base` vs `overlays/with-mockserver`) without introducing Helm as a hard dependency for the POC; the MockServer piece is kept in its own directory so it can be lifted into a Helm chart later if it graduates past POC.

## Risks / Trade-offs

- **[Risk]** Ingress + ingress-nginx does not reproduce real ALB behavior (header rewriting, WAF, TLS termination details) → **Mitigation**: explicitly out of scope (see Non-Goals); document the gap so nobody mistakes POC results for a full production readiness signal.
- **[Risk]** A dev forgets to use the higher default priority and their mock is silently shadowed by the catch-all forward (or vice versa) → **Mitigation**: helper script always sets the documented default priority; README calls out the priority convention explicitly with a worked example.
- **[Risk, discovered during the POC]** MockServer's `PUT /mockserver/clear` matches by request-matcher overlap, not exact identity - clearing "by method + path" also matches and deletes the seeded catch-all (its `path: /.*` regex overlaps every request), silently breaking pass-through for every other route until MockServer restarts and reloads the initializer → **Mitigation**: `scripts/add-mock.sh` prints the new expectation's `id`, and `scripts/delete-mock.sh` clears by that `id` only, never by method/path.
- **[Risk]** MockServer becomes an added latency hop / single point of failure on the request path → **Mitigation**: acceptable for a POC; call out as a follow-up (replicas, resource limits, health checks) before any real-environment rollout.
- **[Risk]** Spring Boot 1.5.x is EOL and its base Docker image may need an older JDK → **Mitigation**: pin a known-good JDK 8 base image (`eclipse-temurin:8-jre-alpine`, since `openjdk:8-jre-alpine` was pulled from Docker Hub) for the stand-in; it only needs to boot and answer one endpoint, not be production-hardened.
- **[Risk]** Real environment's ALB may not be Kubernetes-managed (could be provisioned outside the cluster, e.g., via Terraform) → **Mitigation**: the POC only proves the Kubernetes-side pattern; repointing a real, externally managed ALB is called out as an open question / follow-up, not solved here.

## Migration Plan

This is a POC with no production deployment; "migration" here means the demo/validation sequence:
1. Apply the `base` overlay (ALB stand-in, Gateway, Backend) and confirm a sample request flows end-to-end with no MockServer present.
2. Apply the `with-mockserver` overlay and confirm the same sample request still flows end-to-end unchanged (pass-through proven).
3. Add a mock expectation via the REST API for the same route and confirm MockServer now answers directly instead of forwarding.
4. Remove the expectation and confirm pass-through resumes.
5. **Rollback**: re-apply the `base` overlay (or delete the `with-mockserver` resources and revert the Ingress backend patch) to fully restore the direct `ALB -> Gateway` path.

## Open Questions

- How the real, non-POC ALB is provisioned (Kubernetes-managed Ingress vs. externally managed via Terraform/console) determines how a real rollout would repoint traffic at MockServer - deferred until this POC is validated and a real rollout is planned.
- Whether teams will want one shared MockServer per cluster/environment or one per developer/branch is a scaling question for later, not needed to validate the POC.
