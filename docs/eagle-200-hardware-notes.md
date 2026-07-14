# EAGLE-200 hardware transplant feasibility — research notes

**Question:** when the Eagle-200 finally ages out, can we keep the meter-authenticated
Zigbee radio and give it a new host (dodging the host-side storage wear that is killing
it), instead of buying and BC-Hydro-provisioning a replacement? This depends entirely on
how the device is partitioned internally.

_Living notes. Started 2026-07-14._

## Confirmed

- **The Eagle-200 (model RFA-Z114) has TWO separate Zigbee radios, each with its own FCC
  ID.** That means the radios are distinct, individually-certified subsystems, not one SoC
  fused with the host. The two networks are the **Utility HAN** (to BC Hydro's meter) and
  the **Control network** (home Zigbee subdevices).
- **FCC IDs:**
  - `2AC2E-68M04` = **Meshreen Technology** "JN5168 High Power ZigBee Module" (u.FL / embedded
    antenna). Grantee `2AC2E` = Meshreen, Taiwan. Built on the **NXP JN5168**.
  - `YCXRFA-W900` = **Rainforest Automation** "Smart Control Module RFA-W900". Grantee `YCX`
    = Rainforest.
- **NXP JN5168** is a 2.4 GHz 802.15.4 / ZigBee **SoC**: 32-bit RISC CPU, on-chip flash + RAM,
  runs the ZigBee stack *and* application on-chip; host interfaces via **UART/SPI**. The
  JN516x family shipped an NXP ZigBee **Smart Energy (CBKE)** stack, so it is capable of being
  the SE HAN radio. Key point: it is an SoC, not a dumb network co-processor.
- **Our own corroboration:** Rainforest labels the two radios `d8d5b9000000ef68` (HAN) and
  `...ef69` (control). The current failure is **host-side** (filesystem/IPC: `wifi_status`
  returns 503 with `sem '/wifi_mgr_incoming' failed to open ... No such file`), while the
  **meter link (HAN) reads `Connected` 100%**. The valuable radio path is healthy; the dying
  part is the host. That is exactly the split the transplant idea needs.

## Likely, not yet confirmed

- **Mapping (which radio is which):** best guess is **HAN = JN5168 module (`2AC2E-68M04`)**
  and **Control = Rainforest RFA-W900 (`YCXRFA-W900`)**, because "Smart Control Module" names
  the control network and the JN5168 is a common SE HAN choice. **Could be reversed** — needs
  internal-photo confirmation.

## Why the mapping matters

- **If HAN = JN5168 SoC running SE on-chip:** the SE certificate, private key, EUI64, and the
  live CBKE session with the meter all live **inside the module**. A replacement host would
  just need to **read the module's UART**. Transplant becomes feasible (small project),
  provided we can speak Rainforest's host↔module serial framing.
- **If HAN = RFA-W900 (chip unknown):** need its chip and whether it is SoC or NCP. Unknown.

## Open questions / how to resolve

1. **Which physical module is the HAN radio?** → FCC internal photos for `YCXRFA-W900` and
   `2AC2E-68M04`, or open a unit and trace the meter-facing antenna to its module.
2. **Is the HAN module autonomous (SoC runs SE) or host-driven (NCP runs CBKE from the host)?**
   → JN5168 supports both; determine from the firmware role / whether the module carries its
   own app flash. This is the weekend-hack vs multi-month-slog fork.
3. **Host↔module interface:** almost certainly a proprietary UART framing. Reverse-engineer by
   tapping the lines between host and module.
4. **Host storage type (the failing part):** eMMC / SD / raw NAND? If discrete and reflashable,
   *repairing the host storage and keeping Rainforest's firmware* may beat a radio transplant
   outright, since their FW already drives the radio + SE session.

## Blockers hit during research (2026-07-14)

- `fccid.io` → HTTP 403 (bot block); `fcc.report` → 521/522; `usermanual.wiki` → 522;
  `grokipedia.com` → 403. Every automated FCC/teardown fetch is gated. Could not pull
  internal photos or a block diagram this way.
- **Path forward:** a real browser is not bot-blocked. Either open
  `fccid.io/2AC2E-68M04` and `fccid.io/YCXRFA-W900` (Internal Photos + Block Diagram) by hand,
  or drive it via the Chrome automation tools and read the board photos: identify which module
  sits on the meter-facing antenna (= HAN), read the chip markings, and read the host storage
  chip (eMMC/SD/NAND). That resolves questions 1, 2, and 4 above in one sitting.

## Practical verdict so far

- The partition the idea needs **almost certainly exists**, and one radio is **confirmed a
  reusable commercial SoC module** (JN5168). Whether a host transplant is a small project or a
  reverse-engineering slog comes down to (a) which radio is the HAN one and (b) SoC-vs-NCP for
  it — both answerable from internal photos or a teardown.
- **Lower-effort alternative still on the table:** repair/replace the host's storage (if it is a
  discrete, reflashable part) and keep Rainforest's software intact. That sidesteps the entire
  host-firmware problem and doesn't touch the radio.

## Sources

- FCC ID `2AC2E-68M04` (Meshreen JN5168 module): https://fccid.io/2AC2E-68M04
- FCC ID `YCXRFA-W900` (Rainforest Smart Control Module): https://fccid.io/YCXRFA-W900
- NXP JN5168 SoC (family datasheet/product page): https://www.nxp.com
- Silicon Labs NCP vs SoC overview (host↔NCP via EZSP, for contrast):
  https://docs.silabs.com/zigbee/latest/zigbee-coprocessors-overview/
- EAGLE-200 product page (Rainforest): https://www.rainforestautomation.com/rfa-z114-eagle-200-2/
