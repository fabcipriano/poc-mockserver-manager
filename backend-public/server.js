const express = require('express');

const PORT = process.env.PORT || 3000;

const app = express();

function health(req, res) {
  res.json({ status: 'ok', service: 'backend-public' });
}

function items(req, res) {
  res.json({
    items: [
      { id: 1, name: 'Public Widget' },
      { id: 2, name: 'Public Gadget' },
    ],
  });
}

// Registered both at the plain path (used by Kubernetes' readinessProbe, which talks to this
// pod directly and bypasses the Ingress) and under /public (the path prefix the POC's shared
// Ingress adds for this topology, forwarded through unchanged by MockServer - see
// k8s/overlays/with-mockserver/ingress-patch.yaml).
app.get('/health', health);
app.get('/public/health', health);
app.get('/items', items);
app.get('/public/items', items);

app.listen(PORT, () => {
  console.log(`backend-public stand-in listening on :${PORT}, serving a hardcoded JSON API`);
});
