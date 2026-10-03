"""Fill the Cloud Run spec's placeholders from the environment.

    ENGINE_IMAGE=... ALLOWED_ORIGINS=... PROJECT_ID=... \\
        python3 render_service.py < cloudrun.service.yaml > service.yaml

Only the three named placeholders are replaced. Any other ${...} left in the
output, or a missing value, is an error: a half-rendered spec must never
reach `gcloud run services replace`.
"""

import os
import re
import sys

NAMES = ("ENGINE_IMAGE", "ALLOWED_ORIGINS", "PROJECT_ID")


def render(template: str, env) -> str:
    missing = [n for n in NAMES if not env.get(n)]
    if missing:
        raise SystemExit("missing values for: " + ", ".join(missing))
    out = template
    for name in NAMES:
        out = out.replace("${%s}" % name, env[name])
    # Comments may mention placeholders; the spec itself must not keep any.
    body = "\n".join(line for line in out.splitlines()
                     if not line.lstrip().startswith("#"))
    left = re.findall(r"\$\{[A-Za-z_]+\}", body)
    if left:
        raise SystemExit("unfilled placeholders: " + ", ".join(sorted(set(left))))
    return out


if __name__ == "__main__":
    sys.stdout.write(render(sys.stdin.read(), os.environ))
