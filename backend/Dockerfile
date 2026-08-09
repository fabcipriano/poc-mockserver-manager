# Runs the real, unmodified restful-booker application (https://github.com/mwinteringham/restful-booker)
# as the Backend stand-in, built from its own upstream source pinned to a specific commit for
# reproducibility. Pinned 2026-08-08 at the tip of upstream `main`.
# To bump: pick a new commit SHA from https://github.com/mwinteringham/restful-booker/commits/main
# and update RESTFUL_BOOKER_COMMIT below.
FROM node:22

ARG RESTFUL_BOOKER_COMMIT=00461155995c8636866bf51dc444f63033da44fb

WORKDIR /restful-booker

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && git clone https://github.com/mwinteringham/restful-booker.git . \
    && git checkout -q "${RESTFUL_BOOKER_COMMIT}" \
    && npm install \
    && apt-get purge -y --auto-remove git

EXPOSE 3001

CMD ["npm", "start"]
