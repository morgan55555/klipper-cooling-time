# klipper-cooling-time

Klipper can't estimate cooling time for heaters

This plugin adds to Klipper this functionality.

## Setup

```
 git clone https://github.com/morgan55555/klipper-cooling-time.git
 ln -s ~/klipper-cooling-time/cooling_time.py ~/klipper/klippy/extras/cooling_time.py
```

## Klipper configuration

```ini
[cooling_time]
room_temp: 28
```

## Usage

```
[gcode_macro CALIBRATE_ESTIMATION]
gcode:
    # Calibration. cool_temp must be equal or greater, than room_temp
    COOLING_ESTIMATION_CALIBRATE HEATER=extruder HOT_TEMP=200 COOL_TEMP=45

[gcode_macro TEST]
gcode:
    # Return time estimation for extruder cooling to 45 deg
    {printer.gcode.action_respond_info(printer.cooling_time.calc("extruder",45)|string)}
```
