# GPIO Wiring Reference
## RepeaterWatch + Raspberry Pi 4 + Ikoka Stick (Seeed Studio XIAO nRF52840)

**Last updated:** 2026-03-11
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

### Serial UART Connection (required for serial/RS232 firmware only)

If your Ikoka stick is running the **serial/RS232 firmware** (from the `feature/console-serial1`
branch), the MeshCore console communicates over hardware UART pins instead of USB CDC. You must
wire the Pi's UART to the XIAO's serial pins:

| Function | BCM GPIO | Pi Physical Pin | Connects To | Direct? | Notes |
|----------|----------|-----------------|-------------|---------|-------|
| UART TX | GPIO 14 | Pin 8 | XIAO RX (D7) | Yes | Pi transmit → XIAO receive |
| UART RX | GPIO 15 | Pin 10 | XIAO TX (D6) | Yes | XIAO transmit → Pi receive |
| Ground | — | Pin 6 or 9 | XIAO GND | Yes | Common ground (required) |

Both sides are 3.3V — no level shifter needed. **TX and RX must be crossed** (Pi TX goes to
XIAO RX, and vice versa).

> **Note:** If your stick uses the standard USB firmware, these UART pins are not needed —
> all communication happens over the USB cable via `/dev/ttyACM0`.

### Optional Sensors (not needed initially)

| Function | BCM GPIO | Pi Physical Pin | Connects To | Direct? | Notes |
|----------|----------|-----------------|-------------|---------|-------|
| AS3935 lightning IRQ | GPIO 18 | Pin 12 | AS3935 INT pin | Yes | Interrupt input |
| BQ24074 charge status | GPIO 19 | Pin 35 | BQ24074 /CHG pin | Yes | Input, active low — See note 5 |
| BQ24074 power good | GPIO 13 | Pin 33 | BQ24074 /PG pin | Yes | Input, active low — See note 5 |
| BQ24074 charge enable | GPIO 6 | Pin 31 | BQ24074 CE pin | Yes | Output — See note 5 |

Note: **BQ24074 is GPIO only — no I2C required.** AS3935 requires I2C (SDA = Pin 3, SCL = Pin 5) in addition to its IRQ GPIO pin.

### I2C Sensors (no GPIO pin needed)

These sensors use the I2C bus, which is a standard two-wire interface built into the Pi.
The bus is always **SDA = Pi Pin 3 (GPIO2)** and **SCL = Pi Pin 5 (GPIO3)** — no `.env` pin setting is needed.

| Sensor | I2C Address | Pi Pins Used | Function | Poll Rate |
|--------|-------------|--------------|----------|-----------|
| BME280 | 0x77 | SDA (Pin 3) + SCL (Pin 5) | Temperature, humidity, pressure | Every 60s |
| INA3221 | 0x40 | SDA (Pin 3) + SCL (Pin 5) | Current/voltage monitor (3 channels) | Every 10s |

Both sensors share the same two wires. Multiple I2C devices can coexist on the bus as long as their addresses differ (these two do).

All sensor polling can be disabled by setting `MESHCORE_SENSOR_POLL=0` in your `.env` file (default is enabled).

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

**STATUS: Confirmed**
- [x] RESET pin is accessible on the Ikoka stick — no hardware modification needed

---

## Note 2 — USB Relay (GPIO 17 → USB VBUS switch)

> **IMPORTANT: The USB relay requires the RS232/UART firmware** (`feature/console-serial1`
> branch). With standard USB firmware, the nRF52840 will not enumerate without VBUS, so
> cutting VBUS kills the serial connection entirely. With RS232 firmware, serial goes over
> UART pins instead, so VBUS can be safely switched without losing communication.

**What the code does:**
- Drives GPIO 17 HIGH ("dh") to enable the USB relay (connects VBUS)
- Drives GPIO 17 LOW ("dl") to disable the USB relay (VBUS cut)
- The relay is NOT used for normal reboot/reset — that uses GPIO 4 only
- During a firmware flash the relay stays ON for the entire DFU transfer, then turns OFF

**Why this is needed:**

The Ikoka stick is powered externally (battery via BQ24074 charge controller), not from
the Pi's USB 5V (VBUS). During normal operation, VBUS from the Pi is disconnected so the
external charger manages the battery without interference. The USB data lines (D+, D−, GND)
remain connected. Serial communication goes over the Pi's UART pins (see Note 6), so the
radio stays reachable regardless of VBUS state.

When flashing firmware, the sequence is:
1. GPIO 4 double-pulse triggers DFU/bootloader mode on the nRF52840
2. GPIO 17 turns the relay ON → VBUS is connected → the chip detects host power and
   re-enumerates as a DFU programming device
3. `adafruit-nrfutil` flashes the firmware over the DFU USB connection
4. GPIO 17 turns the relay OFF → VBUS disconnected → Ikoka returns to battery power

**Physical wiring (from build photos):**

The relay is wired using its **NO (normally open) and COM terminals** to interrupt the
**red wire (VBUS / 5V)** on the USB cable between the Pi and the Ikoka stick. The data
lines (D+, D−) and GND pass through uninterrupted.

```
Pi USB port ──── D+, D−, GND ────────────────────────────► Ikoka USB
                 VBUS (red) ──► Relay COM/NO ──────────────► Ikoka USB VBUS

Pi GPIO 17 (Pin 11) ──► Relay module IN
Pi 5V (Pin 2 or 4)  ──► Relay module VCC
Pi GND (Pin 6)      ──► Relay module GND
```

Normal operation: relay off → NO open → VBUS cut → Ikoka on battery power
Flashing:         relay on  → NO closed → VBUS connected → DFU enumeration

**STATUS: Partially confirmed on meshcore-site3 (2026-04-04)**
- [x] Confirm DFU enumeration requires VBUS to be present — **confirmed**, nRF52840 will not enumerate without VBUS
- [x] Confirm USB relay requires RS232/UART firmware — **confirmed**, standard USB firmware loses serial when VBUS is cut
- [ ] Confirm relay interrupts VBUS only (not full USB cable)
- [ ] Confirm Ikoka is externally powered (battery) and does not rely on USB VBUS

---

## Note 3 — BME280 (Temperature / Humidity / Pressure)

**What it does:**
Measures ambient temperature (°C), relative humidity (%), and barometric pressure (hPa).
Useful for monitoring environmental conditions at a remote site.

**Interface:** I2C at address `0x77`

**Wiring:**
```
Pi 3.3V (Pin 1 or 17) ──► BME280 VCC
Pi GND  (Pin 6 or 9)  ──► BME280 GND
Pi SDA  (Pin 3)        ──► BME280 SDA
Pi SCL  (Pin 5)        ──► BME280 SCL
```

**Software:**
- Library required: `adafruit-circuitpython-bme280`
- If the library is not installed, the sensor is silently skipped — no errors, just no data
- Data is read every 60 seconds and stored to the database

**Note on address conflict:** BME280 also comes in a variant with address `0x76`. The code
is hardcoded to `0x77` — make sure your module is configured (or jumpered) to `0x77`.
Some cheap boards default to `0x76`, so check before buying.

**STATUS: Optional — not yet purchased**

---

## Note 4 — INA3221 (3-Channel Current / Voltage Monitor)

**What it does:**
Measures bus voltage and current on three separate channels simultaneously. The original
author uses it to monitor a solar power system:
- **Channel 0 (ch0):** Battery voltage and current
- **Channel 1 (ch1):** Load voltage and current (what the system is drawing)
- **Channel 2 (ch2):** Solar panel voltage and current

The code calculates power (watts) from voltage × current for each channel.

**Interface:** I2C at address `0x40`

**Wiring:**
```
Pi 3.3V (Pin 1 or 17) ──► INA3221 VCC (logic power)
Pi GND  (Pin 6 or 9)  ──► INA3221 GND
Pi SDA  (Pin 3)        ──► INA3221 SDA
Pi SCL  (Pin 5)        ──► INA3221 SCL
```

Each channel also has IN+ and IN- terminals where the current-sense resistor goes inline
with whatever circuit you are monitoring. Detailed hookup depends on your power setup.

**Software:**
- Library required: `adafruit-circuitpython-ina3221`
- Like the BME280, silently skipped if library is not installed
- Data is read every 10 seconds (more frequent due to real-time power monitoring use case)
- On I2C error, the driver resets and reinitializes automatically on the next read

**STATUS: Optional — not yet purchased**

---

## Note 5 — BQ24074 Solar Charge Controller (GPIO 6, 13, 19)

**What it is:**
The BQ24074 is a Texas Instruments solar/Li-Ion battery charge controller IC. It manages
charging a battery from a solar panel (or other DC source). The Pi doesn't control the
charging itself — it just monitors status and can enable/disable charging remotely.

**This is GPIO only — no I2C.** All three connections are direct pin-to-pin with the Pi.

**The three pins and what they mean:**

| Pin | BCM GPIO | Pi Physical | Direction | Logic | Meaning |
|-----|----------|-------------|-----------|-------|---------|
| /CHG | GPIO 19 | Pin 35 | Input | Active LOW | LOW = battery is actively charging |
| /PGOOD | GPIO 13 | Pin 33 | Input | Active LOW | LOW = valid input power present (solar/DC connected) |
| CE | GPIO 6 | Pin 31 | Output | Active HIGH | HIGH = charging disabled; LOW = charging enabled (default) |

"Active low" means the signal is backwards from what you might expect — the pin is pulled
HIGH normally, and goes LOW to indicate the event is happening.

**What the code does:**
- Reads `/CHG` and `/PGOOD` to report charging state and input power status on the dashboard
- Can write to `CE` to remotely enable or disable charging via the RepeaterWatch API
- Starts with CE LOW (charging enabled) on boot

**Wiring:**
```
Pi GPIO 19 (Pin 35) ──► BQ24074 /CHG  (charge status output from chip)
Pi GPIO 13 (Pin 33) ──► BQ24074 /PGOOD (power-good output from chip)
Pi GPIO 6  (Pin 31) ──► BQ24074 CE    (charge enable input to chip)
Pi GND     (Pin 6)  ──► BQ24074 GND   (common ground)
```
All connections are direct (no resistors needed) — the BQ24074 has internal pull-ups on
/CHG and /PGOOD, and the Pi enables software pull-ups on those input pins.

**STATUS: Optional — only relevant if using a BQ24074-based solar charger**

---

## Raspberry Pi 4 — 40-Pin Header Reference

Physical pin layout (looking at the Pi with the header at top-right):

```
         3V3  (1) (2)  5V
   SDA / GPIO2  (3) (4)  5V
   SCL / GPIO3  (5) (6)  GND
★      GPIO4  (7) (8)  GPIO14 / TXD  ★ (serial mode)
           GND  (9) (10) GPIO15 / RXD  ★ (serial mode)
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
★ (serial mode) = only used when running serial/RS232 firmware

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

## Note 6 — UART Serial Connection (GPIO 14, 15 — serial/RS232 firmware only)

**When this is needed:**
If your Ikoka stick is flashed with the **serial/RS232 firmware** (the `feature/console-serial1`
branch of MeshCore), the MeshCore CLI commands are sent over the hardware UART pins instead of
USB CDC serial. Standard USB firmware does NOT need this wiring.

**What changes from USB mode:**
- SerialMux connects to `/dev/ttyAMA0` (the Pi's hardware UART) instead of `/dev/serial/by-id/...`
- The kernel serial console must be disabled (removed from `cmdline.txt`) so Linux doesn't
  claim the UART for boot messages
- The USB cable may still be connected for power and/or DFU firmware flashing, but the
  MeshCore serial console goes over UART

**Wiring:**
```
Pi GPIO 14 / TX (Pin 8)  ──────► XIAO RX (D7)
Pi GPIO 15 / RX (Pin 10) ◄────── XIAO TX (D6)
Pi GND         (Pin 6/9) ──────── XIAO GND
```

**Important:** TX and RX are crossed — the Pi's transmit pin connects to the XIAO's receive
pin, and vice versa. Both sides are 3.3V, so no level shifter or resistors are needed.

**Kernel configuration required:**
1. `enable_uart=1` must be in `/boot/firmware/config.txt` (or `/boot/config.txt` on older OS)
2. `console=serial0,115200` must be **removed** from `/boot/firmware/cmdline.txt`
3. A reboot is required after these changes

The `install.sh` script handles this automatically when you choose "Serial (UART)" mode.

**STATUS: Confirmed working on meshcore-site3 (Nebra conversion, Ikoka Stick / XIAO nRF52840)**
Not yet tested with other nRF-based radios, but should work with any that support the RS232 firmware.

---

## Summary — What to Build First

1. **Start with reset only (GPIO 4 → RST)**
   - Simple, low-risk, direct connection with optional series resistor
   - Allows remote reset and DFU entry testing
   - Confirm RESET pad is accessible on Ikoka stick first

2. **Test DFU entry without the USB relay**
   - The XIAO may re-enumerate automatically without needing USB cycling
   - Only add the relay circuit if DFU detection fails without it

3. **Add USB relay only if using RS232/UART firmware**
   - The USB relay **requires the RS232 firmware** — with standard USB firmware, cutting VBUS
     kills the serial connection (the nRF52840 won't enumerate without VBUS)
   - With RS232 firmware, serial goes over UART so VBUS can be safely switched
   - More complex wiring, adds components — only needed if managing external battery charging

4. **Add sensors later**
   - AS3935 (lightning), BQ24074 (charger) — only if that hardware is purchased; need GPIO pins (see table above)
   - BME280 (temp/humidity/pressure) and INA3221 (current/voltage) — I2C only, no GPIO pins; just connect SDA and SCL
   - Sensor polling can be disabled globally with `MESHCORE_SENSOR_POLL=0` in `.env` until hardware is attached

---

## Open Questions

- [ ] USB relay — confirm relay interrupts VBUS only, confirm Ikoka is externally powered (see Note 2)
- [ ] Are there any existing GPIO connections between the Ikoka stick and Pi in the Ikoka design?
