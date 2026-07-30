# MemSnapDump MIT Relicensing Declaration

## Scope

This record covers all MemSnapDump code through and including upstream commit
`87ea207372e0985790e1a28dab499dccf3c3b9a4` (`v0.1.0`) in
<https://github.com/codeasier/MemSnapDump>.

## Rights-holder confirmation

On 2026-07-31, Liu Yekang, who publishes MemSnapDump as `codeasier` using
`liuyekang@huawei.com`, explicitly confirmed all of the following in this
execution:

1. Liu Yekang is the sole author and copyright owner of all MemSnapDump code in
   the scope above.
2. The scoped code contains no unaccounted copied code and no code contributed
   by a third party.
3. Liu Yekang grants the scoped MemSnapDump code to this pt-snap-cli integration
   under the MIT License.

This declaration was explicitly confirmed by the rights holder in this
execution. The agent recorded that confirmation; the agent did not author the
declaration, does not claim to be the rights holder, and does not supply or
invent a signature.

The applicable MIT terms are preserved in
`src/pt_snap_cli/snapshot/LICENSE`. This record does not reproduce the
standard license text or represent an additional signature.

## Corroborating repository evidence

The pinned audit checkout was inspected on 2026-07-31. Its Git evidence is:

```text
$ git remote -v
origin  https://github.com/codeasier/MemSnapDump.git (fetch)
origin  https://github.com/codeasier/MemSnapDump.git (push)

$ git rev-parse HEAD
87ea207372e0985790e1a28dab499dccf3c3b9a4

$ git tag --points-at HEAD
v0.1.0

$ git rev-list --count --all
83

$ git shortlog -sne --all
83  codeasier <liuyekang@huawei.com>

$ git log --all --format='%aN <%aE>' | LC_ALL=C sort | uniq -c
83 codeasier <liuyekang@huawei.com>
```

The shortlog and full author audit each report the same single author identity
for all 83 commits. Git history corroborates the declaration but does not
replace the rights holder's explicit confirmation above.

## Reproduction boundary

The completed audit used the pinned checkout at:

```text
/var/folders/44/mmqfw4_j1mq02hggc798tfy80000gn/T/opencode/memsnapdump-audit-20260731
```

Commands in this record are intended to run from that checkout. The checkout
had 84 tracked files. A deterministic tracked-tree manifest hash was produced
with:

```sh
git ls-files -z | LC_ALL=C sort -z | xargs -0 shasum -a 256 | shasum -a 256
```

Result:

```text
626e2d5afc6dd0ef908dcccb0ab61c6804938418d65a50fe436f5e6dee797f65  -
```
