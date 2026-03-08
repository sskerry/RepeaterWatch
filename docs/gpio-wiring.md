# GPIO Wiring Reference
## RepeaterWatch + Raspberry Pi 4 + Ikoka Stick (Seeed Studio XIAO nRF52840)

**Last updated:** 2026-03-07
**Status:** Partially confirmed — see notes on each connection

---

## Voltage Compatibility

Both devices operate at **3.3V logic**:
- Raspberry Pi 4 GPIO: 3.3V
- Seeed Studio XIAO nRF52840: 3.3V

No level shifting (voltage conversion) is required for direct GPIO signal connections.
However, the USB relay circuit (see below) involves 5V USB power and needs additional components.

---

## GPIO Pin Map

All GPIO numbers below use **BCM numbering** — this is the chip numbering (e.g., "GPIO 4"),
not the physical pin number on the Pi header. See the Pi header diagram at the bottom.

### Required for Reset / Firmware Flashing

| Function | BCM GPIO | Pi Physical Pin | Connects To | Direct? | Notes |
|----------|----------|-----------------|-------------|---------|-------|
| Radio reset / DFU | GPIO 4 | Pin 7 | XIAO RESET pin | Likely yes | See note 1 |
| USB relay control | GPIO 17 | Pin 11 | Relay/switch circuit | No — needs extra parts | See note 2 |

### Optional Sensors (not needed initially)

| Function | BCM GPIO | Pi Physical Pin | Connects To | Direct? | Notes |
|----------|----------|-----------------|-------------|---------|-------|
| AS3935 lightning IRQ | GPIO 18 | Pin 12 | AS3935 INT pin | Yes | Interrupt input |
| BQ24074 charge status | GPIO 19 | Pin 35 | BQ24074 /CHG pin | Yes | Input, active low |
| BQ24074 power good | GPIO 13 | Pin 33 | BQ24074 /PG pin | Yes | Input, active low |
| BQ24074 charge enable | GPIO 6 | Pin 31 | BQ24074 CE pin | Yes | Output |

Also required for AS3935 and BQ24074: **I2C** (SDA = Pin 3, SCL = Pin 5) — not GPIO but worth noting.

---

## Note 1 — Radio Reset Line (GPIO 4 → XIAO RESET)

**What the code does:**
- Drives GPIO 4 LOW for 0.5 seconds to trigger a hard reset
- For DFU/bootloader entry: double-pulse LOW (0.1s) → HIGH (0.2s) → LOW (0.1s) → HIGH
- This mimics physically pressing the reset button on the XIAO

**Hardware:**
- The XIAO nRF52840 RESET pin is active-low (pulled HIGH internally by a resistor inside the chip)
- Driving it LOW from the Pi GPIO will trigger a reset
- Both sides are 3.3V — direct connection is electrically safe

**Recommended wiring:**
```
Pi GPIO 4 (Pin 7) ──[ 100Ω ]── XIAO RESET pad
                                      │
                              (internal pull-up inside XIAO)
```
A 100Ω series resistor is not strictly required but protects both devices if there's
ever a wiring fault. Can be omitted if you want to keep it simple.

**NEEDS CONFIRMATION:**
- [ ] Is the XIAO RESET pin exposed/accessible on the Ikoka stick?
- [ ] Is there a labeled pad, test point, or connector pin for it?
- [ ] Contact Ikoka or inspect the hardware to confirm before wiring

---

## Note 2 — USB Relay (GPIO 17 → USB power switch)

**What the code does:**
- Drives GPIO 17 HIGH ("dh") to enable the USB connection (DFU device appears)
- Drives GPIO 17 LOW ("dl") to disable the USB connection (normal operation)
- Used during firmware flashing: the XIAO enters bootloader mode, then the USB relay
  connects it to the Pi so it appears as a DFU programming device

**Why this is needed:**
After the XIAO enters bootloader mode via the reset pulse, it needs to re-enumerate
on USB as a different device (the DFU bootloader). Cycling the USB connection forces
the Pi to see it as a new device. Without this, the Pi may not detect the new DFU device.

**Hardware — this is NOT a direct pin connection:**
GPIO 17 is only a control signal (3.3V, very low current). It cannot switch USB power (5V)
directly. You need a circuit in between. Typical options:

**Option A — Relay module (simplest to build):**
```
Pi GPIO 17 (Pin 11) ──► Relay module IN
Pi 5V (Pin 2 or 4) ──► Relay module VCC
Pi GND (Pin 6) ──────► Relay module GND
                        Relay module COM/NO ──── USB VBUS (5V) to Ikoka
```
Most relay modules have a built-in transistor driver and work directly from Pi GPIO.
Choose a 5V relay module rated for the current draw of the XIAO (very low, <100mA).

**Option B — MOSFET switch (cleaner, no mechanical relay):**
A P-channel MOSFET (e.g., IRLML6402) with a small NPN transistor to invert the
signal from GPIO 17. More compact but more components.

**NEEDS CONFIRMATION:**
- [ ] Does the Ikoka stick have a separate USB connection that can be switched, or is
      its USB permanently connected to the Pi?
- [ ] Does the Ikoka stick's DFU process actually require USB relay switching, or does
      the XIAO re-enumerate automatically after bootloader entry?
- [ ] This feature may not be needed at all depending on Ikoka's USB wiring —
      test reset/DFU without the relay first

---

## Raspberry Pi 4 — 40-Pin Header Reference

Physical pin layout (looking at the Pi with the header at top-right):

```
         3V3  (1) (2)  5V
   SDA / GPIO2  (3) (4)  5V
   SCL / GPIO3  (5) (6)  GND
★      GPIO4  (7) (8)  GPIO14 / TXD
           GND  (9) (10) GPIO15 / RXD
★     GPIO17 (11) (12) GPIO18 ★
      GPIO27 (13) (14) GND
      GPIO22 (15) (16) GPIO23
          3V3 (17) (18) GPIO24
      GPIO10 (19) (20) GND
       GPIO9 (21) (22) GPIO25
      GPIO11 (23) (24) GPIO8
          GND (25) (26) GPIO7
       GPIO0 (27) (28) GPIO1
★      GPIO5 (29) (30) GND
★      GPIO6 (31) (32) GPIO12
★     GPIO13 (33) (34) GND
★     GPIO19 (35) (36) GPIO16
      GPIO26 (37) (38) GPIO20
          GND (39) (40) GPIO21
```

★ = pins used by this project (current or optional)

---

## Seeed Studio XIAO nRF52840 — Key Pins

```
           USB-C
    ┌────────────────┐
    │                │
RST ●                ● 3V3
GND ●                ● GND
 3V ●                ● A0/D0
 D1 ●                ● A1/D1
 D2 ●                ● A2/D2
 D3 ●                ● A3/D3
 D4 ●  (SDA)   (SCL) ● D5
 D6 ●  (TX)    (RX)  ● D7
 D9 ●  (MISO)        ● D8 (SCK)
D10 ●  (MOSI)        ●
    └────────────────┘
```

**RESET pad** is labeled RST — this is what GPIO 4 needs to connect to.
**Confirm this pad is accessible on the Ikoka stick before wiring.**

---

## Summary — What to Build First

1. **Start with reset only (GPIO 4 → RST)**
   - Simple, low-risk, direct connection with optional series resistor
   - Allows remote reset and DFU entry testing
   - Confirm RESET pad is accessible on Ikoka stick first

2. **Test DFU entry without the USB relay**
   - The XIAO may re-enumerate automatically without needing USB cycling
   - Only add the relay circuit if DFU detection fails without it

3. **Add USB relay only if needed**
   - More complex, adds components, not worth building until confirmed necessary

4. **Add sensors later**
   - AS3935 (lightning), BQ24074 (charger) — only if that hardware is purchased
   - No wiring needed until then; sensor polling is disabled in `.env`

---

## Open Questions

- [ ] Is the Ikoka stick's RESET pin exposed? (check with Ikoka documentation or physically inspect)
- [ ] What connector/interface does the Ikoka stick use to connect to the Pi? (USB only? GPIO header?)
- [ ] Does the XIAO re-enumerate as DFU automatically, or does USB relay switching help?
- [ ] Are there any existing GPIO connections between the Ikoka stick and Pi in the current Ikoka design?
