# BMS explicit switch positions

Version 0.3.2 replaces the five ECM mode toggle callbacks with separate
`SimEcmMode1On` / `SimEcmMode1Off` through `SimEcmMode5On` /
`SimEcmMode5Off` commands. All 46 persistent switch and selector definitions
now use explicit ON/OFF or named-position callbacks. Momentary pushbuttons and
incremental knobs retain their appropriate actions. DCS ECM mappings are unchanged.

Each press still advances one button to the next displayed setting. The command
sets that target position rather than toggling whatever position BMS currently
has. For example, if the icon shows OFF but the cockpit is already ON, the next
press sends ON and displays ON. A successfully executed command aligns them.

Icons and dots represent the last command sent through VSD, not confirmation
from BMS. Mouse/HOTAS changes and new flights do not automatically update the
display. BMS must be in the foreground and executing the configured keyfile
commands. Rejected keyboard injection leaves the icon unchanged.

The installer exposes the ten new ECM shortcuts in Review / edit shortcuts,
checks conflicts against the selected keyfiles, and applies shortcut edits to
the runtime mapping and keyfiles together. Existing unrelated keyboard and
joystick assignments are preserved. Close BMS and VSD Craft before installing.

Validation: 19 installer tests, 19 runtime tests, 10 panel-layout tests, and a
standalone bundled-EXE/GUI self-check covering 179 editable bindings. Runtime
checks exercise every position of every persistent BMS selector and both
directions of all five ECM buttons. In-flight execution remains unverified.
