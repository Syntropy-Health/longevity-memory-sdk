# HACP index — h2s_meta (local L0)

```mermaid
flowchart LR
  PVR[PVR rev 2<br/>HAC-30] --> AD[A&D rev 1<br/>HAC-33, board-approved HAC-36] --> P1[P1 data core<br/>HAC-38 · done] --> P2[P2 passport · next step · lab<br/>HAC-38 · landed 38bda41] --> P3[P3 UI + a11y CI<br/>HAC-38 · landed ee99e82] --> P4[P4 submission pack<br/>HAC-38 · phase gate, with CTO]
```

| Decision | By | Where |
|---|---|---|
| Blueprint, D-A9, D-A2, D-A3 and D-A1 approved as written | Board | HAC-36 |
| Build plan locked (G1–G12, addendum G13) | Agent | HAC-38 document `plan` |
| AM-1: board sign-off label; ranges only where a source states them | CTO (board answer) | HAC-38 |
| P2 build decisions G22–G25 | Agent | `workstreams/daypart/plan/ADDENDUM-fhdic.md` |
| P3 build decisions G26–G29 (HAC-48 rev 2 intake, screen ids, dashboard name, Correct on a flagged value) | Agent | `workstreams/daypart/plan/ADDENDUM-fhdic.md` |
| P4 decision G30 (pack cites a committed organiser snapshot; O1–O4 for unpublished organiser rules; organiser challenge titles) | Agent | `workstreams/daypart/plan/ADDENDUM-fhdic.md` |

| Section | State |
|---|---|
| build | P1–P3 landed on `daypart/build`; P4 (submission pack) at phase gate, with the CTO to land; then the L2 delivery review |
| decision | none open |
