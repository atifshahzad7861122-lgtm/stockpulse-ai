// Replaces the __STOCKPULSE_API_URL__ placeholder baked into the Next.js
// client bundle at Docker build time with the runtime NEXT_PUBLIC_API_URL.
//
// Hosts like Railway cannot receive custom Docker build args, so the image
// is built with the placeholder and the container injects the real URL on
// startup (see deploy/frontend.Dockerfile). Idempotent: after the first
// injection the placeholder is gone and later runs are no-ops.
const fs = require("fs");
const path = require("path");

const PLACEHOLDER = "__STOCKPULSE_API_URL__";
const value = process.env.NEXT_PUBLIC_API_URL || "";

if (!value || value === PLACEHOLDER) {
  process.exit(0);
}

function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(p);
    } else if (p.endsWith(".js")) {
      const content = fs.readFileSync(p, "utf8");
      if (content.includes(PLACEHOLDER)) {
        // split/join instead of a regex replace: the URL may contain
        // characters (/, &) that are special in regex/sed replacements.
        fs.writeFileSync(p, content.split(PLACEHOLDER).join(value));
      }
    }
  }
}

const staticDir = "/app/.next/static";
if (fs.existsSync(staticDir)) {
  walk(staticDir);
}
