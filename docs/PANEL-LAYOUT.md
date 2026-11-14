# Cockpit row/column layout

This layout replaces sequential left-to-right packing with explicit positions. The XL uses seven composite pages; the N4 Pro uses eight pages. DCS and BMS use matching coordinates.

Coordinates in `panel-layout.json` are zero-based **column, row**, viewed on the physical device with the text upright. The N4 Pro's reversed software Y axis is converted when building the profile.

[XL avionics grid](avionics-xl.png) · [N4 HUD grid](hud-n4.png) · [N4 avionics upper view](avionics-n4-upper.png) · [N4 INS/MIDS lower view](avionics-n4-lower.png)

## Main arrangements

| Panel | Upper row, left to right | Lower rows |
| --- | --- | --- |
| Avionics power | MMC, ST STA, MFD, UFC, MAP | GPS below MFD; DL below UFC; INS lower-left, MIDS lower-right |
| HUD | SCALES, FPM, DED/PFL, DEPR RET | SPEED, ALT, BRT in the first three columns below |
| Sensor power | L HDPT, R HDPT, FCR, RDR ALT | One horizontal switch row |
| External lighting | ANTI COLL, POSITION, WING/TAIL, FUSELAGE | MASTER centered below; N4 FORM knob left and AAR knob right |
| Test | FIRE, OBOGS, LAMP | EPU GEN below OBOGS; absent controls leave gaps |
| ECM | Power/XMIT on the left; modules 1, 2, 3, 4 to the right | BIT under XMIT; module 5 below module 1; absent FRM/SPL controls stay empty |
| Electrical | MAIN PWR | ELEC RESET below MAIN PWR |
| Flight control | DIG BACKUP left, ALT FLAPS right | LE FLAPS lower-left |

## Device compromises

- XL pages group several small panels where useful. Each subpanel keeps its reviewed internal geometry; the entire page is not a scale reproduction of a cockpit console. Single-control panels are kept in separate blocks.
- The N4 Pro avionics-power panel is split into an upper/middle page and an INS/MIDS lower-page viewport. Columns stay consistent between the two views and the XL.
- N4 HUD controls are now on one page: four above three. Navigation and simulator-switch keys occupy the remaining spaces; navigation positions vary where necessary to preserve all five avionics columns.
- Physical N4 knobs form one row, so they cannot reproduce a real two-row knob panel. Audio knobs retain their relative ordering; lighting knobs preserve left/center/right placement where possible. Unused knobs remain unassigned.
- JFS START 1 and START 2 remain separate momentary commands and occupy consecutive positions above ENG CONT. They are not converted into a latching selector.
- No new simulator command definitions or keyboard shortcuts were added. Existing mapped functions are reused, including exposing the complete HUD/avionics groups on N4 pages. All previously available logical controls and all eleven encoder functions remain available.

## Reference review

The installed **DCS F-16C Early Access Guide EN** (774-page English edition) was visually reviewed at PDF/printed pages 63-65, 67, 69, 71-72, 75-78, 94 and 706. These show engine/JFS, EPU/electrical, audio, fuel, external lighting, flight-control/test, sensor/environment/oxygen, avionics, HUD and ECM panels. [Eagle Dynamics' English guide](https://www.digitalcombatsimulator.com/upload/iblock/3dc/5p9ejw7gi488n9zd15csrxxs8os2dflk/DCS_F-16C_Early_Access_Guide_EN.pdf) is an online reference; pagination can differ between editions.

The installed **TO 1F-16CMAM-1 BMS**, Change 4.38, was checked at pages 129 (external lighting) and 150 (AUDIO 1/2) for the corresponding BMS panel arrangements. Reference manuals and their screenshots are not redistributed here.

This is a grid approximation of the covered F-16CM/Block-50-style controls. It does not assert that every F-16 block, cockpit variant, or simulator configuration has an identical panel.
