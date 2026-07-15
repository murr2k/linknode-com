# EAGLE-200 radio transplant: UART sniffing and protocol-derivation project plan

**Goal.** Before the EAGLE-200's host board finally dies, capture and decode the serial protocol
between its host MCU and its Zigbee module, so that a replacement host can drive the *same*
meter-authenticated Zigbee radio and keep linknode.com alive without a BC-Hydro re-provisioning.

**Status of the premise (settled).** See [`eagle-200-hardware-notes.md`](eagle-200-hardware-notes.md)
for the evidence. In short: the meter radio is a discrete, reusable **NXP JN5168 SoC module**
(Meshreen MS5168-Mxx, FCC `2AC2E-68M04`); the Smart Energy identity (certificate, private key,
EUI64, live CBKE session) lives **inside that module**; and the host only reads cooked data across
a serial link. The failing part is the host, not the radio. That makes a host transplant viable and
reduces the whole problem to **one question this project answers: what does the host say to the
module over that link, and what does the module say back?**

_Living plan. Started 2026-07-14._

---

## 1. Why now, and why non-destructive first

- **Capture while the unit is alive.** The host is degrading (filesystem/IPC faults) but still boots
  and still brings the module up (meter link reads `Connected` 100%). The boot / network-rejoin /
  CBKE handshake only crosses the wire when the host initialises the module. Once host storage fully
  dies we may only ever see steady-state traffic, or nothing. **The init sequence is far easier to
  get before the host is gone.**
- **The tap is passive and reversible.** We only *listen*: analyzer inputs on the module TX, the host
  TX (module RX), and a ground. Nothing is driven. Open the case, tack on three fine wires, capture,
  remove them, reassemble. The EAGLE keeps working. There is no downside to doing it opportunistically,
  and it is worth doing **purely as insurance even if we never transplant**.
- **We already have the plaintext.** We poll the Eagle local API and get decoded meter values
  (`InstantaneousDemand`, `CurrentSummationDelivered`) with timestamps. This turns blind reverse
  engineering into a **known-plaintext alignment problem**: capture the UART and poll the API at the
  same time, line the timestamps up, and the known values appear in the byte stream where the field
  encoding can be read off directly.

## 2. Scope

**In scope**
- Physically locate and passively tap the host to module serial link inside the EAGLE-200.
- Determine the electrical interface (UART vs SPI), baud/clocking, and framing.
- Capture representative traffic: cold-boot handshake, network (re)join, and steady-state reads.
- Correlate captured frames against local-API ground truth to decode the read path.
- Produce a written protocol spec sufficient to build a replacement host's read path.
- Prototype and validate that read path on a bench host (no meter needed for decode).

**Out of scope (explicitly not doing)**
- Extracting or cloning the SE certificate / private key. Not needed (we keep the module) and not
  feasible. See hardware notes.
- Spoofing or re-pairing a new radio with the meter. Rejected earlier.
- Reflashing or modifying the JN5168 firmware. We drive it as-is.
- Any change to the live production path during capture. The Pi bypass stays primary throughout.

## 3. Strategy: phased, with a hard split between "insurance" and "build"

Phases 1 to 5 are the **insurance package**: do them soon, while the unit lives. They are cheap,
non-destructive, and produce a durable artifact (the protocol spec) that outlives the hardware.
Phases 6 to 8 are the **build**: defer until the EAGLE actually ages out (or we choose to).

| Phase | Name | Trigger | Destructive? |
|---|---|---|---|
| 1 | Access and identify the link | Now | No (open case only) |
| 2 | Build the passive capture rig | Now | No |
| 3 | Interface and baud discovery | Now | No |
| 4 | Known-plaintext capture campaign | Now | No |
| 5 | Decode and write the protocol spec | After phase 4 | No |
| 6 | Prototype replacement host (read path) | When ready to build | No |
| 7 | Bench validation against the real module | Before cutover | No (still reversible) |
| 8 | Transplant and cutover | EAGLE host has died / is dying | Yes |

---

## 4. Equipment / bill of materials

| Item | Spec / note | Rough cost |
|---|---|---|
| Logic analyzer | **Saleae Logic 16** (16 digital channels, selectable logic threshold covering 3.3 V, sample-rate headroom far beyond 1 Mbaud) | on hand |
| Capture software | **Saleae Logic 2**, driven through its **15-tool MCP interface** (see 4.1); built-in UART and SPI analyzers | on hand |
| Fine-tip probes / micro test hooks | To grab module castellations or nearby test points | $10 to $30 |
| 30 AWG wire + soldering iron | Tack wires to pads if hooks will not grab | on hand |
| Multimeter | Continuity / 3.3 V rail check before connecting | on hand |
| Oscilloscope (optional) | To eyeball logic swing and idle-high line before committing the analyzer | optional |
| Anti-static mat / strap | Handling an open Zigbee board | on hand |
| Capture host + Pi | Workstation running Logic 2 + the MCP; the Pi polls the local API for the plaintext table | on hand |

The Logic 16 and its software are on hand; only hooks/wire may need buying.

### 4.1 Toolchain and automation: Saleae Logic 16 + MCP

The Logic 16 is driven by **Saleae Logic 2**, which exposes an automation surface reachable here as a
**15-tool MCP interface**. That turns capture from manual clicking into a **scriptable, repeatable
loop that Claude can drive directly** when the MCP is connected: enumerate the device, set the active
channels / sample rate / logic threshold, start and stop timed captures, attach a UART (or SPI)
analyzer, and export the decoded frames and raw transitions for analysis. The correlation step
(align exported frames to the Pi's timestamped local-API log) then runs as code, so a capture ->
export -> decode -> refine cycle can iterate quickly and reproducibly.

Two practical consequences for this plan:

- **16 channels means no iterative guessing.** Tap *every* candidate line at once, both UARTs
  (`TXD0/RXD0`, `TXD1/RXD1`), the flow-control pair (`RTS0/CTS0`), and the SPI candidates
  (`SCLK/MOSI/MISO/CS`), in a single capture. One boot recording then reveals which interface and
  which pins actually carry the meter traffic, collapsing phase 3 into one shot instead of a probe-
  and-retry loop.
- **Where the tools must be live.** The MCP is only useful in the session physically attached to the
  Logic 16 (the workstation by the EAGLE). This session does **not** have those tools connected, so
  the steps below are written so that whoever runs the capture (a future session with the Saleae MCP
  loaded, or a human in Logic 2) can execute them the same way. When the MCP is live, Claude can
  operate the capture end to end.

---

## 5. Phase detail

### Phase 1 - Access and identify the link

1. Power down, open the EAGLE-200 enclosure (record every screw/clip; this stays reassemble-able).
2. Identify the Zigbee module: the daughter-module/shielded can bearing FCC `2AC2E-68M04`, with the
   u.FL connector (M04 variant) or PCB antenna (M05). Photograph the board (both sides) before touching.
3. From the **MS5168-Mxx datasheet pinout**, find the module's serial pins: `TXD0`/`RXD0` and their
   flow-control mates `RTS0`/`CTS0`, plus `TXD1`/`RXD1` if present, and a `GND` and the `3V3` rail.
   Note: the JN516x serial bootloader lives on **UART0**, so data traffic may be on UART0 or UART1;
   confirm empirically in phase 3.
4. Map those module pins to reachable copper: the castellated pad, a series resistor, a via, or a test
   point on the host side of the link. Prefer the easiest solid contact for a listen-only tap.
5. Confirm the logic rail with a meter (expect ~3.3 V, idle-high on an idle UART TX line).

**Gate A output:** confirmed physical tap points for module-TX, host-TX, and GND.

### Phase 2 - Build the passive capture rig

With 16 channels available, wire **all** candidate lines at once (listen only, never drive) so a
single boot capture identifies the real interface:

| CH | Signal | Purpose |
|---|---|---|
| CH0 | module `TXD0` | UART0 module -> host |
| CH1 | host `TXD0` (module `RXD0`) | UART0 host -> module |
| CH2 | `RTS0` | UART0 flow control (explains gated bursts) |
| CH3 | `CTS0` | UART0 flow control |
| CH4 | module `TXD1` | UART1 module -> host (if present) |
| CH5 | host `TXD1` (module `RXD1`) | UART1 host -> module |
| CH6 | `SCLK` | SPI clock candidate |
| CH7 | `MOSI` | SPI host -> module candidate |
| CH8 | `MISO` | SPI module -> host candidate |
| CH9 | `CS` / `SSEL` | SPI chip-select candidate |
| CH10 | `RSTN` | module reset (marks bring-up boundary) |
| CH11 | optional strobe | manual event marker during capture |
| GND | board ground | common reference (never a signal) |

1. Tack the wires to the mapped pads/test points from phase 1. Keep stubs short; 1 Mbaud tolerates
   it, but tidy is better. Any candidate line that turns out not to exist on this board is simply an
   idle channel, no harm.
2. In Logic 2 (via MCP), set the logic threshold to the 3.3 V range and pick a sample rate giving
   comfortable oversampling (target >= ~16 samples per bit at the expected baud).
3. Sanity check: power on, confirm idle-high UART lines and bursts of activity. Do **not** yet worry
   about decoding.

### Phase 3 - Interface and baud discovery (single capture)

Because every candidate line is already tapped (phase 2), one boot capture answers this:

1. **Which interface.** See which channels carry traffic. Async self-clocked bursts on CH0/CH1 (or
   CH4/CH5) with no companion clock = UART. Activity gated by a clock on CH6 = SPI; if so, decode the
   SPI group instead. UART is the expected and far more likely case; the SPI channels are insurance.
2. **Which UART.** If both UART0 and UART1 show traffic, keep the pair whose payload tracks meter
   reads (phase 4); the other is likely a debug/ISP console.
3. **Baud / clock.** Measure the narrowest pulse; its width is one bit time. Candidate UART rates:
   - **1,000,000 baud, 8N1** - common default for the NXP JN51xx serial-link host interface.
   - **115200 / 38400 8N1** - generic defaults; 38400 is the JN51xx bootloader rate.
   Set the analyzer to the measured rate and confirm clean byte framing (no framing errors). For SPI,
   read the clock polarity/phase and word size off the capture.

**Gate B output:** interface type, the live channel pair, and line settings locked; the analyzer
produces clean bytes in both directions.

### Phase 4 - Known-plaintext capture campaign

Drive the Logic 16 through the MCP to run timed captures and export decoded frames, while the Pi
timestamps local-API polls, so every captured second has a ground-truth row
`(t, InstantaneousDemand, CurrentSummationDelivered, ...)` to align against. Keep the two clocks
comparable (same NTP-synced host, or record an offset) so the alignment is tight.

Captures to collect:
1. **Cold boot / init.** Start the capture, then power the EAGLE on. Grab the full module bring-up:
   reset, firmware/version handshake, network parameters, rejoin, and the CBKE/key exchange chatter.
   This is the perishable one, prioritise it.
2. **Steady state.** Several minutes of normal operation. The Eagle reads instantaneous demand every
   ~8 to 10 s natively, so the periodic request/response pair should be obvious and repeating.
3. **Event-correlated.** While capturing, watch the local API for a demand value change; the matching
   frame is the one whose payload changes in step. Toggle the CH3 strobe (or note the time) at that
   instant to bookmark it.
4. **Provisioning traffic if it ever occurs** (e.g. a rejoin). Treat as **sensitive**: link-layer
   key or install-code material could cross the wire here. See section 7.

Save every capture with a written log: date, firmware state of the host, what you did, and the
concurrent local-API dump.

### Phase 5 - Decode and write the protocol spec

1. **Find the framing.** Identify start/sync byte(s), a length field, a message-type/command byte,
   payload, and a trailing checksum/CRC. If Rainforest used the stock NXP serial link, the frame has a
   documented shape (start byte, type, length, payload, CRC-style check); if custom, derive it from
   repetition and the known-plaintext anchors.
2. **Anchor on known values.** Locate the `InstantaneousDemand` integer in a steady-state response by
   matching the local-API value; walk outward to recover scale/divisor, endianness, and the enclosing
   length and checksum. Repeat for `CurrentSummationDelivered`.
3. **Classify message types.** Separate host-initiated requests from module-initiated reports; note
   which request elicits a reading, and any periodic keep-alive.
4. **Deliverable:** `docs/eagle-200-serial-protocol.md` - interface + line settings, frame format,
   message-type table, field encodings for the read path, and the exact request needed to obtain a
   reading. This artifact is the point of the whole insurance exercise.

**Decision gate C:** can we, on paper, (a) recognise a reading and (b) name the request that produces
one? If yes, the transplant read path is fully specified and the insurance goal is met.

### Phase 6 - Prototype replacement host (read path)

- Choose a host: a Pi or a small Linux/MCU board with a 3.3 V UART.
- Implement the request/parse loop from the phase-5 spec; reuse the existing synthetic-Rainforest-XML
  uploader from `scripts/eagle_bypass.py` for the shipping side, so only the *acquisition* front end
  is new.
- Develop against captures first (replay), then against the live module.

### Phase 7 - Bench validation against the real module

- Connect the prototype host to the module's UART (still inside the powered EAGLE, still reversible)
  in **parallel-listen** first, then, only if confident, as the driver on a bench where we can restore
  the original host.
- Success = prototype reads `InstantaneousDemand` and summation from the module and they match the
  local API within tolerance, sustained across rejoin and over hours.

### Phase 8 - Transplant and cutover (deferred until the EAGLE ages out)

- Mechanically separate the module from the dead host; wire it to the new host (UART + 3V3 + GND +
  reset). Mind antenna: keep the M04 u.FL/embedded antenna path intact.
- Bring up, confirm the CBKE session re-establishes with the meter (it should, the identity is on the
  module), and confirm end-to-end data to Fly.
- Keep the Pi local-API bypass as the fallback until the transplant proves stable.

---

## 6. Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Link is SPI, not UART | Low | Phase 3 detects it; re-channel to SPI and capture the same way |
| Data is on UART1 while UART0 is a debug/ISP console | Medium | All 16 candidate lines tapped at once; keep the pair whose payload tracks meter reads |
| Baud is nonstandard | Low | Measured from the narrowest pulse, not guessed |
| Serial link is encrypted | Very low | RF is encrypted, not the local serial; if it is, fall back to host-storage repair (below) |
| Host too dead to init the module | Rising over time | Do phases 1 to 4 **now**; steady-state alone may still suffice for read-only |
| Flow control gates/splits bursts | Medium | Capture RTS/CTS on CH2 to interpret gaps |
| Accidental short / driving a line | Low | Listen-only rig, verified with a meter before power-on; never enable analyzer outputs |
| We damage the module during teardown | Low but costly | Non-destructive phases first; only phase 8 separates it, and only once the host is already dead |

**Lower-effort alternative kept on the table:** if the serial route stalls, repairing/replacing the
host's storage (if it is a discrete, reflashable part) and keeping Rainforest's firmware intact
sidesteps the protocol work entirely. Worth a look during phase 1 (identify the storage chip).

---

## 7. Data handling and safety

- **Captures may contain secrets.** Provisioning/rejoin traffic could carry link-layer key or
  install-code material; the Eagle local API also leaks the Wi-Fi PSK in plaintext. Treat raw captures
  and local-API dumps as **sensitive**: keep them off the repo, and **redact** before pasting into any
  doc, issue, or artifact. The Install Code is a credential.
- **No secrets in repo files** (standing project rule). The protocol spec records *format*, not keys.
- **Electrical safety:** listen-only, common ground, 3.3 V verified before connecting. No line is ever
  driven during capture.
- **Production untouched:** the Pi bypass remains the primary uploader throughout phases 1 to 7; none
  of this touches the live linknode.com path.

## 8. Success criteria

1. **Insurance met (phases 1 to 5):** a written, validated protocol spec that identifies a meter
   reading in the stream and the request that produces it.
2. **Build proven (phases 6 to 7):** a bench host that reads live values from the module matching the
   local API within tolerance, sustained.
3. **Transplant done (phase 8):** the module, on a new host, holds its meter session and ships data to
   Fly end-to-end, with the Pi bypass retired to fallback.

## 9. Rough effort

- Phases 1 to 4: a focused weekend (most of it is careful teardown, tapping, and one good boot capture).
- Phase 5: a few evenings, faster because of the known-plaintext anchors.
- Phases 6 to 7: one to two weeks of part-time firmware work, mostly reusing the existing uploader.
- Phase 8: a day, whenever the hardware forces it.

## 10. Immediate next actions

1. Confirm the **Saleae Logic 2 + 15-tool MCP** is reachable from the workstation next to the EAGLE,
   and that Claude can enumerate the Logic 16 through it (dry run on a scrap signal).
2. Get micro test hooks / 30 AWG wire (the only gear not on hand).
3. Pull the **MS5168-Mxx datasheet pinout** (public) and pre-mark the module's `TXD0/RXD0/RTS0/CTS0`,
   `TXD1/RXD1`, the SPI pins, `RSTN`, `GND`, and `3V3` before opening the case.
4. Add a timestamped local-API logger mode (reuse `scripts/eagle_net.py`/`eagle_bypass.py`) to produce
   the ground-truth table during capture.
5. Schedule the teardown-and-capture session while the host still boots, in a session with the Saleae
   MCP loaded so Claude can run the capture.

## 11. References

- [`eagle-200-hardware-notes.md`](eagle-200-hardware-notes.md) - the feasibility evidence this plan builds on.
- FCC `2AC2E-68M04` (Meshreen JN5168 module, incl. public Test Report exhibit): https://fccid.io/2AC2E-68M04
- NXP JN5168 (SoC; on-chip MAC+stack; UART/SPI): https://www.nxp.com/part/JN5168
- Meshreen MS5168-Mxx (pinout, UART host interface): https://www.meshreen.com/ms5168-m04-2/
- Seeed MeshBee cookbook (JN5168 module; AT/API/MCU host modes over UART): https://files.seeedstudio.com/wiki/Mesh_Bee/res/MeshBee_Cook_Book.pdf
