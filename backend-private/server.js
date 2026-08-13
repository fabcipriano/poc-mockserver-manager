const express = require('express');

const PORT = process.env.PORT || 3000;

const app = express();

function health(req, res) {
  res.json({ status: 'ok', service: 'backend-private' });
}

function accounts(req, res) {
  res.json({
    accounts: [
      { id: 'acct-1', owner: 'Private Corp A' },
      { id: 'acct-2', owner: 'Private Corp B' },
    ],
  });
}

// Registered both at the plain path (used by Kubernetes' readinessProbe, which talks to this
// pod directly and bypasses the Ingress) and under /private (the path prefix the POC's shared
// Ingress adds for this topology, forwarded through unchanged by MockServer - see
// k8s/overlays/with-mockserver/ingress-patch.yaml).
app.get('/health', health);
app.get('/private/health', health);
app.get('/accounts', accounts);
app.get('/private/accounts', accounts);

app.listen(PORT, () => {
  console.log(`backend-private stand-in listening on :${PORT}, serving a hardcoded JSON API`);
});
