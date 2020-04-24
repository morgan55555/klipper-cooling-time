# -*- coding: utf-8 -*-
# Klipper bed/extruder cooling time estimating
#
# Copyright (C) 2020  Alex Morgan <alxmrg55@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#
# Install:
#
# sudo systemctl stop klipper
# cd ~
#
# git clone https://github.com/morgan55555/klipper-cooling-time.git
# ln -s ~/klipper-cooling-time/cooling_time.py ~/klipper/klippy/extras/cooling_time.py
#
from math import log
import heater

class Cooling_Estimator:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.room_temp = config.getfloat('room_temp')
        self.config = config
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_command(
            'COOLING_ESTIMATION_CALIBRATE', self.cmd_COOLING_ESTIMATION_CALIBRATE,
            desc=self.cmd_COOLING_ESTIMATION_CALIBRATE_help)
    cmd_COOLING_ESTIMATION_CALIBRATE_help = "Calibration for cooling time estimation."
    def cmd_COOLING_ESTIMATION_CALIBRATE(self, params):
        heater_name = self.gcode.get_str('HEATER', params)
        max_temp = self.gcode.get_float('HOT_TEMP', params)
        min_temp = self.gcode.get_float('COOL_TEMP', params)
        if max_temp <= min_temp:
            self.gcode.respond_error('HOT_TEMP must be equal or greater than COOL_TEMP!')
            return
        if min_temp < self.room_temp:
            self.gcode.respond_error('COOL_TEMP must be equal or greater than room_temp in settings!')
            return
        heater = self._get_heater(heater_name)
        self.printer.lookup_object('toolhead').get_last_move_time()
        heater.set_temp(max_temp)
        self.gcode.wait_for_temperature(heater)
        calibrate = ControlCoolingEstimator(heater, max_temp, min_temp, self.room_temp)
        old_control = heater.set_control(calibrate)
        try:
            heater.set_temp(min_temp)
        except self.printer.command_error as e:
            heater.set_control(old_control)
            raise
        self.gcode.wait_for_temperature(heater)
        heater.set_control(old_control)
        heater.set_temp(0)
        cooling_coef = calibrate.calc_final_coef()
        self.gcode.respond_info(
            "New cooling coef is %.6f\n"
            "The SAVE_CONFIG command will update the printer config file\n"
            "with these parameters and restart the printer." % cooling_coef)
        # Store results for SAVE_CONFIG
        configfile = self.printer.lookup_object('configfile')
        configfile.set("cooling_time", heater_name, "%.6f" % cooling_coef)
    def get_status(self, eventtime):
        return {'calc': self._calc}
    def _calc(self, heater_name, target_temp):
        coef = self.config.getfloat(heater_name, None)
        if coef == None:
            raise ValueError("No cooling coef found for heater %s" % heater_name)
        heater = self._get_heater(heater_name)
        temp = self._get_heater_temp(heater)
        if target_temp >= temp:
            return 0
        delta = temp - self.room_temp
        diff = target_temp - self.room_temp
        return -log( diff / delta ) / coef
    def _get_heater(self, heater_name):
        heater = None
        pheater = self.printer.lookup_object('heater')
        try:
            heater = pheater.lookup_heater(heater_name)
        except self.printer.config_error as e:
            raise self.gcode.error(str(e))
        return heater
    def _get_heater_temp(self, heater):
        if heater == None:
            return None
        eventtime = self.reactor.monotonic()
        if heater.check_busy(eventtime):
            return None
        return heater.get_temp(eventtime)[0]



class ControlCoolingEstimator:
    def __init__(self, heater, max_temp, min_temp, room_temp):
        self.heater = heater
        self.heater_max_power = heater.get_max_power()
        self.max_temp = max_temp
        self.min_temp = min_temp
        self.room_temp = room_temp
        # Heating control
        self.init = False
        self.done = False
        # Sample recording
        self.temp_samples = []
    # Heater control
    def set_pwm(self, read_time, value):
        self.heater.set_pwm(read_time, value)
    def temperature_update(self, read_time, temp, target_temp):
        if not self.done:
            self.temp_samples.append((read_time, temp))
            if temp <= target_temp:
                self.done = True
        elif not self.init:
            self.set_pwm(read_time, 0.)
            self.init = True
    def check_busy(self, eventtime, smoothed_temp, target_temp):
        if not self.done:
            return True
        return False
    # Analysis
    def calc_final_coef(self):
        delta = self.max_temp - self.room_temp
        summ = 0
        amount = 0
        for time, temp in self.temp_samples:
            diff = temp - self.room_temp
            summ += -log( diff / delta ) / time
            amount += 1
        return summ / amount

def load_config(config):
    return Cooling_Estimator(config)
