const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');

const PORT = process.env.PORT || 3000;
const BACKEND_URL = process.env.BACKEND_URL || 'http://backend:3001';

const app = express();

app.use(
  '/',
  createProxyMiddleware({
    target: BACKEND_URL,
    changeOrigin: true,
    logLevel: 'info',
  })
);

app.listen(PORT, () => {
  console.log(`gateway stand-in listening on :${PORT}, forwarding to ${BACKEND_URL}`);
});
