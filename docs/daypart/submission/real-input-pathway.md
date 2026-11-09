# Real-input pathway

Real input is **hard off**. The full pathway, with the 12 governance gates, is maintained in one
place so it cannot drift: **[docs/daypart/real-input-pathway.md](../real-input-pathway.md)**.

In short:

- Turning real input on is not a setting. It needs a code change to `REAL_INPUT_BUILD_ALLOWED`
  (`False` in this build), a revised product vision and requirements, a new design, and every
  governance gate closed with a named owner and evidence.
- Closing every gate on its own still does not enable it.
- Every route to it is refused: the UI's **Real input** control and `POST /api/mode` get 403 with
  the list of open gates, and setting `DAYPART_REAL_INPUT=1` in the environment is logged and refused.
- All 12 gates are open and unassigned in this build, by design.
