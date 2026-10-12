#!/usr/bin/env bash
# Draft reproducible restore. Every downloaded source is official and pinned.
set -euo pipefail
E=$(realpath -m "${1:?new absolute output directory}")
test ! -e "$E"
mkdir -p "$E"
python3 -m venv "$E/venv"
git init "$E/source"
git -C "$E/source" fetch --depth 1 https://gitcode.com/Ascend/msinsight.git 101f65b877a267ffd5f66ea3834706057ba243e5
git -C "$E/source" checkout --detach FETCH_HEAD
test "$(git -C "$E/source" rev-parse HEAD)" = 101f65b877a267ffd5f66ea3834706057ba243e5
export E

cd "$E/source/server/third_party"
for spec in 'libuv libuv/libuv v1.44.2 0c1fa696aa502eb749c2c4735005f41ba00a27b8' 'uSockets uNetworking/uSockets v0.8.6 8cd4cb66eb061b2594ca114b9ea1ead64613ad4b' 'uWebSockets uNetworking/uWebSockets v20.48.0 bc2815d95b6ff4cad0973226d0058eadaaec99ad'; do
 read -r name repo tag sha <<< "$spec"
 git clone --depth 1 --branch "$tag" "https://github.com/$repo.git" "$name" > "$E/$name-fetch.log" 2>&1
 test "$(git -C "$name" rev-parse HEAD)" = "$sha"
done
git init rapidjson; git -C rapidjson fetch --depth 1 https://github.com/Tencent/rapidjson.git 24b5e7a8b27f42fa16b96fc70aade9106cf7102f > "$E/rapidjson-fetch.log" 2>&1; git -C rapidjson checkout --detach FETCH_HEAD
curl -fL --max-time 120 https://www.sqlite.org/2024/sqlite-autoconf-3460100.tar.gz -o "$E/sqlite.tar.gz"
echo '67d3fe6d268e6eaddcae3727fce58fcc8e9c53869bdd07a0c61e38ddf2965071  '"$E/sqlite.tar.gz" | sha256sum -c -
python - <<'PY'
import tarfile,pathlib,os
r=pathlib.Path(os.environ['E'])
with tarfile.open(r/'sqlite.tar.gz') as t:
 for n in ['sqlite3.h','sqlite3ext.h','sqlite3.c','shell.c']:
  m=t.getmember('sqlite-autoconf-3460100/'+n); assert m.isfile()
  out=r/'source/server/third_party/sqlite'/('include' if n.endswith('.h') else 'src')/n
  out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(t.extractfile(m).read())
PY
"$E/venv/bin/pip" install --index-url https://pypi.org/simple cmake==3.31.6 ninja==1.11.1.4 websockets==15.0.1 > "$E/tools-install.log" 2>&1
npm install --cache "$E/npm-cache" --prefix "$E/build-tools" --ignore-scripts --registry=https://registry.npmjs.org --strict-ssl=true pnpm@11.25.0 > "$E/pnpm-install.log" 2>&1

cd "$E/source/modules"
CI=true npm_config_strict_ssl=true "$E/build-tools/node_modules/.bin/pnpm" install --frozen-lockfile --ignore-scripts --registry=https://registry.npmjs.org --store-dir="$E/pnpm-store" --public-hoist-pattern=rc-select --public-hoist-pattern=rc-tree --public-hoist-pattern=rc-tabs --public-hoist-pattern=rc-table --public-hoist-pattern=@ant-design/icons --public-hoist-pattern=mobx-react-lite --public-hoist-pattern=classnames --public-hoist-pattern=csstype '--public-hoist-pattern=@types*' '--public-hoist-pattern=*eslint*' --public-hoist-pattern=react --public-hoist-pattern=react-dom --public-hoist-pattern=mobx-react --public-hoist-pattern=react-i18next

export PATH="$E/venv/bin:$PATH"
cmake -S "$E/source/server" -B "$E/cmake-build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5
cmake --build "$E/cmake-build" --target profiler_server -j 3
# Intentional incremental recheck: verify the completed target is up to date.
cmake --build "$E/cmake-build" --target profiler_server -j 3 > "$E/cmake-recheck.log" 2>&1
grep -F "ninja: no work to do." "$E/cmake-recheck.log"

cd "$E/source/modules/leaks"
NODE_OPTIONS='--openssl-legacy-provider --max-old-space-size=2048' NODE_ENV=production GENERATE_SOURCEMAP=false CI=false node ../node_modules/@craco/craco/dist/bin/craco.js build > "$E/leaks-build.log" 2>&1
cd "$E/source/modules/framework"
NODE_OPTIONS='--openssl-legacy-provider --max-old-space-size=2048' NODE_ENV=production GENERATE_SOURCEMAP=false CI=false node ../node_modules/@craco/craco/dist/bin/craco.js build > "$E/framework-build.log" 2>&1

git -C "$E/source" diff --exit-code
