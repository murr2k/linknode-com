# EAGLE-200 hardware transplant feasibility — research notes

**Question:** when the Eagle-200 finally ages out, can we keep the meter-authenticated
Zigbee radio and give it a new host (dodging the host-side storage wear that is killing
it), instead of buying and BC-Hydro-provisioning a replacement? This depends entirely on
how the device is partitioned internally.

_Living notes. Started 2026-07-14._

## Confirmed

- **The Eagle-200 (model RFA-Z114) carries two FCC-certified radio modules, but they are NOT
  two Zigbee radios.** The FCC filings resolve them as **one Zigbee SoC module + one Wi-Fi
  module** (correction — see the W900 finding below):
  - `2AC2E-68M04` = **Meshreen Technology** "JN5168 High Power ZigBee Module" (u.FL / embedded
    antenna). Grantee `2AC2E` = Meshreen, Taiwan. Built on the **NXP JN5168**. This is the
    **Zigbee** radio — the meter-facing HAN path. FCC filing (uploaded 2026-07-14) confirms:
    **2405-2475 MHz** single-channel (no MIMO → 802.15.4, i.e. Zigbee, not Wi-Fi), **0.118 W**
    (~21 dBm, hence "High Power"), **Single Modular Approval**, model series **MS5168-Mxx**,
    original grant 2014-10-07. A discrete, off-the-shelf commercial module — exactly the kind of
    part that is physically separable and independently documented.
  - `YCXRFA-W900` = **Rainforest Automation** "Smart Control Module RFA-W900" (grantee `YCX`).
    Its FCC grant RF profile is **802.11n Wi-Fi, not Zigbee**: 2412-2462 MHz, **2TX MIMO,
    20 & 40 MHz channel bandwidths**, ~0.329 W combined conducted. Zigbee/802.15.4 has no MIMO
    and uses 2 MHz channels, so this module is unambiguously the **2.4 GHz Wi-Fi uplink**, i.e.
    how the gateway joins the home network — despite the "Smart Control Module" marketing name.
    (See "The W900 filing" below for how this was established.)
- **NXP JN5168** is a 2.4 GHz 802.15.4 / ZigBee **SoC**: 32-bit RISC CPU, on-chip flash + RAM,
  runs the ZigBee stack *and* application on-chip; host interfaces via **UART/SPI**. The
  JN516x family shipped an NXP ZigBee **Smart Energy (CBKE)** stack, so it is capable of being
  the SE HAN radio. Key point: it is an SoC, not a dumb network co-processor.
- **Our own corroboration:** Rainforest labels two Zigbee networks `d8d5b9000000ef68` (HAN) and
  `...ef69` (control). The current failure is **host-side** (filesystem/IPC: `wifi_status`
  returns 503 with `sem '/wifi_mgr_incoming' failed to open ... No such file`), while the
  **meter link (HAN) reads `Connected` 100%**. The valuable radio path is healthy; the dying
  part is the host. That is exactly the split the transplant idea needs.

## The W900 filing (FCC ID YCXRFA-W900) — what the upload showed (2026-07-15)

Decoded from the FCC MHT the user saved. This is the most direct data we have, and it
**corrects the earlier "two Zigbee radios" assumption**:

- **Equipment class "Digital Transmission System", Notes "Smart Control Module", Single
  Modular approval.** A discrete, individually-certified module — good for the transplant
  premise generally, but this one is the Wi-Fi module, not the meter radio.
- **RF profile = Wi-Fi.** "2TX MIMO configurations", "supports 20 MHz and 40 MHz bandwidths",
  2412-2462 MHz. Those are 802.11n features that Zigbee cannot have. So W900 ≠ meter radio.
- **This grant is a re-identification, not an original design.** "Change in identification of
  presently authorized equipment. Original FCC ID: **N89-WD114**", original grant 2016-02-17,
  re-ID'd to YCXRFA-W900 on 2016-03-25. Rainforest rebadged an existing OEM Wi-Fi module under
  their own FCC ID. The chipset is whatever `N89-WD114` is (not named in this filing).
- **No internal photos here.** Exhibits are External Photographs, Label/Label Location, agent
  authorization, and change-of-ID cover letters only (confidentiality: No). So this filing does
  **not** reveal internal chip markings or a block diagram — chase `N89-WD114` for that.

**Net effect on the thesis:** it *simplifies* it. The meter-authenticated Smart Energy identity
almost certainly lives in the **one Zigbee SoC (JN5168)**, not split across two Zigbee radios.
The W900 (Wi-Fi) is part of the flaky host/uplink side we would be *replacing*, not the radio we
need to preserve.

## Likely, not yet confirmed

- **The JN5168 module is the meter HAN radio.** With W900 reclassified as Wi-Fi, the JN5168 is
  the only certified Zigbee module in the box, so it is almost certainly the SE HAN radio (and
  may also run the "control" Zigbee network as a second PAN on the same SoC). Still worth an
  internal-photo / teardown confirmation, and worth checking whether a *second* Zigbee part is
  soldered to the mainboard under the host's own composite FCC grant (which would not show up as
  its own modular ID).

## Why this matters

- **HAN = JN5168 SoC running SE on-chip (the expected case):** the SE certificate, private key,
  EUI64, and the live CBKE session with the meter all live **inside the module**. A replacement
  host would just need to **read the module's UART**. Transplant becomes feasible (small
  project), provided we can speak Rainforest's host↔module serial framing.
- **The reclassification of W900 as Wi-Fi removes the fork we worried about.** There is no
  competing "maybe the HAN radio is the W900 with an unknown chip" branch anymore — W900 is the
  Wi-Fi uplink. The remaining risk is not *which* radio but *how* the JN5168 is driven (SoC vs
  NCP) and whether a second Zigbee part hides on the mainboard.

## FCC blocker found: the decisive docs are confidential (2026-07-14)

The one open technical question — **does Rainforest run the Smart Energy / CBKE stack ON the
JN5168 (SoC mode) or drive it as a bare co-processor from the host (NCP mode)?** — is exactly
what the module's **Block Diagram, Schematics, and Operational Description** would answer. On the
FCC filing all three are **"Metadata only"** (filed under **long-term confidentiality**; the grant
page shows Long-Term Confidentiality = Yes). So the FCC route **cannot** resolve SoC-vs-NCP: those
exhibits are sealed. Public exhibits are only External/Internal Photos, Label, Test Report, and
the **User Manual (MS5168-Mxx series, public)**.

Caveat on the uploads themselves: the five saved pages are the fccid.io HTML wrappers. The actual
exhibit PDFs (internal photos, the user-manual pinout) render as page images and did **not** come
through as readable content in the saves — I have the metadata and page counts, not the pixels.
To actually read them I'd need the PDFs saved directly (the `/m/<hash>.pdf` links), not the
fccid.io page as MHT.

## What the Test Report (public, 47pp) adds — read 2026-07-14

Extracted the report's page images (it is a scan; pulled the raster pages and read them). It does
**not** reproduce the sealed internal block diagram, but its EUT/setup sections are informative:

- **EUT specifics (confirm Zigbee):** models **MS5168-M04** (u.FL external antenna, 2.43 dBi) and
  **MS5168-M05** (PCB antenna, 1.60 dBi); **O-QPSK**, 2405-2475 MHz, **15 channels**, **20.72 dBm**,
  99% OBW 2.28 MHz, **DC 3.3 V**. Unambiguously the 802.15.4 / Zigbee radio.
- **The module is host-attached and field-programmable.** Test methodology 3.2 ("EUT Exercise
  Software"): *"Turn on Zigbee function link to Notebook and run test program"*, *"EUT run test
  program"*, and *"Software used to control the EUT for staying in continuous transmitting mode was
  programmed."* The setup block diagram (3.3) is **AC Adapter → Notebook → Fixture → EUT**: the
  module sits in a fixture and is driven over a wired link by a host PC.
- **What this settles:** the module runs **loadable application firmware on-chip** and is designed
  to be **driven by an external host over a serial link** — precisely the "module + host" split the
  transplant depends on, and the same shape as the EAGLE's Linux host driving it.
- **What it does NOT settle:** whether the on-chip firmware is a *full SE/CBKE stack* (SoC mode) or
  a *thin MAC co-processor* (NCP mode). That is the sealed Block Diagram / Schematics / Operational
  Description, none of which the test report copies. So SoC-vs-NCP remains open after the FCC docs.

## SoC-vs-NCP: RESOLVED (SoC mode), from public NXP/module docs — 2026-07-14

Web research into the public JN5168 / MS5168 documentation settles the crux the sealed FCC docs
wouldn't. The stack (and therefore the Smart Energy identity) runs **on the module**, not on the
host. Evidence:

- **The JN5168 is a full SoC that runs MAC + ZigBee PRO stack + application on-chip.** 256 KB
  Flash, 32 KB RAM, **4 KB EEPROM plus OTP**, "access to the on-chip peripherals, MAC and network
  stack software is provided through specific APIs." Critically, its **OTP memory securely holds a
  64-bit MAC/IEEE address and a 128-bit AES key on-chip** — i.e. the network security material
  lives in the silicon, not on a host. (NXP JN5168 product pages / JN516x data sheet.)
- **The MS5168 module family explicitly targets ZigBee Smart Energy** and "use[s] NXP JN5168 ...
  to provide a comprehensive solution with large memory, high CPU and radio performance and all RF
  components included," with the host talking to it over **UART**. So SE is a first-class supported
  role for this exact module, run on the module. (Meshreen MS5168-Mxx datasheet/user manual.)
- **The canonical usage pattern keeps the stack on the module in every mode.** The Seeed MeshBee
  (a JN5168 module) cookbook documents three modes, and the ZigBee PRO stack runs on the module in
  all of them: *Master/AT* ("factory firmware warps the complicated Zigbee stack operation into a
  few easy to use serial commands"), *Slave/API* ("a host application can send API frames ... to
  interact with"), and *MCU* (run your own app on the JN5168 standalone). In no mode does the host
  run the ZigBee stack — the host only ever speaks high-level AT/API over UART.
- **NCP mode would mean Rainforest re-implemented the entire ZigBee PRO + Smart Energy + CBKE stack
  on their Linux host.** NXP ships that stack on-chip for free and provides no Linux SE host stack
  for JN516x; a small vendor writing their own is implausible.
- **Our own telemetry corroborates it:** the host is failing (filesystem/IPC: `wifi_status` 503,
  missing semaphore) while the **meter/HAN link stays `Connected` 100%**. A CBKE session run in host
  software would not survive the host melting down; a session held on the module does. The SE link
  outliving host failure is exactly the SoC-mode signature.

**Conclusion:** the meter's authenticated identity — SE certificate, private key, EUI64, and the
live CBKE session — lives **inside the JN5168 module**, and the EAGLE's Linux host only pulls
cooked data across a UART. A replacement host therefore needs to **speak that serial link**, not
reproduce any Zigbee/SE security. This is the favorable "small project" outcome. The only remaining
unknown is the **application-level framing** Rainforest uses over the UART (standard NXP serial-link
protocol vs a custom one) — a pure reverse-engineering task on public, accessible pins, with no
cryptographic barrier. Short of a bench probe for 100% certainty, the feasibility question is
answered: **yes, a radio-preserving host transplant is viable.**

## Open questions / how to resolve (updated)

1. ~~**SoC vs NCP for the JN5168**~~ — **RESOLVED: SoC mode** (section above). Only a bench probe of
   our own unit's UART would add final 100% certainty; not required for the go/no-go call.
2. **Is there a second Zigbee part on the mainboard** (for the "control" network) not covered by
   its own modular FCC ID, or does the single JN5168 run both PANs? → teardown / internal photos.
3. **Host↔module interface:** the **electrical layer is public** (JN5168 + Meshreen module pinout
   are documented — UART/SPI). What is unknown is Rainforest's **application-level framing** over
   that UART. De-risked physically; only the protocol is proprietary.
4. **Host storage type (the failing part):** eMMC / SD / raw NAND? If discrete and reflashable,
   *repairing the host storage and keeping Rainforest's firmware* may beat a radio transplant
   outright, since their FW already drives the radio + SE session.
5. **What chip is `N89-WD114`** (the OEM Wi-Fi module W900 rebadges)? Only matters if we end up
   needing to re-host Wi-Fi too, which the transplant would likely replace anyway.

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

- **The idea is viable.** The partition the transplant needs exists; the meter radio is a confirmed
  reusable commercial **SoC module** (JN5168, Meshreen MS5168-Mxx); the W900 upload removed the
  "which radio is the HAN one" uncertainty (W900 is Wi-Fi); and the SoC-vs-NCP crux is now
  **resolved as SoC mode** from public NXP/module docs (see the RESOLVED section above). The
  meter's SE identity lives **inside the module**; the host only reads cooked data over UART.
- **The physical interface is already de-risked:** JN5168 + MS5168 pinouts are public (UART/SPI).
  The only remaining unknown is Rainforest's application-level framing over that UART, and that is a
  plain reverse-engineering task with **no cryptographic barrier** — the crypto stays on the module
  we keep. A bench probe of our own unit would confirm the framing and give final certainty.
- **Lower-effort alternative still on the table:** repair/replace the host's storage (if it is a
  discrete, reflashable part) and keep Rainforest's software intact. That sidesteps the entire
  host-firmware problem and doesn't touch the radio.
- **Next step is a project, not a question.** The one remaining unknown (Rainforest's UART framing)
  is derived by sniffing the live host-to-module link. See the full plan in
  [`eagle-200-transplant-plan.md`](eagle-200-transplant-plan.md).

## Sources

- FCC ID `2AC2E-68M04` (Meshreen JN5168 module): https://fccid.io/2AC2E-68M04
  - EUT/setup detail read from the module's **public Test Report** exhibit (report no. 1409FR15):
    O-QPSK 2405-2475 MHz, 20.72 dBm, models MS5168-M04/M05; setup `AC Adapter → Notebook → Fixture
    → EUT`; firmware programmable / host-driven.
- FCC ID `YCXRFA-W900` (Rainforest "Smart Control Module", actually the **Wi-Fi** module, re-ID of
  N89-WD114): https://fccid.io/YCXRFA-W900
- NXP JN5168 product page (256 KB Flash / 32 KB RAM / 4 KB EEPROM+OTP; on-chip MAC+stack via APIs;
  OTP holds 64-bit MAC + 128-bit AES key): https://www.nxp.com/part/JN5168
- NXP JN516x ZigBee Smart Energy (SE stack incl. CBKE runs on the JN516x):
  https://www.nxp.com/pages/jn516x-zigbee-smart-energy:ZIGBEE-SMART-ENERGY
- Meshreen MS5168-Mxx (module family targets ZigBee Smart Energy; JN5168 + all RF; UART host):
  https://www.meshreen.com/ms5168-m04-2/
- Seeed MeshBee cookbook (JN5168 module; stack-on-module in all three modes — AT / API / MCU;
  host talks high-level AT/API over UART): https://files.seeedstudio.com/wiki/Mesh_Bee/res/MeshBee_Cook_Book.pdf
- Silicon Labs NCP vs SoC overview (host↔NCP via EZSP, for contrast):
  https://docs.silabs.com/zigbee/latest/zigbee-coprocessors-overview/
- EAGLE-200 product page (Rainforest): https://www.rainforestautomation.com/rfa-z114-eagle-200-2/
