#!/usr/bin/env bash
# Paquet pour le Chrome Web Store : dist/alice-extension-<version>.zip
#
# Le manifest de développement reconnaît aussi http://localhost:3000 (site en
# local) ; la version publiée ne le garde pas : un reviewer y verrait un accès
# inutile, et l'extension n'a rien à faire sur le localhost de l'utilisateur.
set -euo pipefail
cd "$(dirname "$0")"

version=$(python3 -c "import json; print(json.load(open('manifest.json'))['version'])")
out="dist/alice-extension-${version}.zip"
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT

cp background.js bridge.js content.js fields.js popup.html popup.js "$stage/"
mkdir -p "$stage/icons" && cp icons/16.png icons/48.png icons/128.png "$stage/icons/"

python3 - "$stage/manifest.json" <<'PY'
import json, sys
m = json.load(open("manifest.json"))
for cs in m.get("content_scripts", []):
    for key in ("matches", "exclude_matches"):
        if key in cs:
            cs[key] = [u for u in cs[key] if "localhost" not in u]
json.dump(m, open(sys.argv[1], "w"), ensure_ascii=False, indent=2)
PY

# L'API locale n'a rien à faire dans la version publiée non plus.
if grep -n "localhost" "$stage"/*.js >/dev/null; then
  echo "Attention : « localhost » apparaît encore dans le code :"; grep -n "localhost" "$stage"/*.js
fi

mkdir -p dist
rm -f "$out"
(cd "$stage" && zip -qr -X "$OLDPWD/$out" .)
echo "Paquet prêt : extension/$out"
