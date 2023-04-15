#!/usr/bin/python
import argparse
import json
import subprocess
import os
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

controller = None

def set_combo_value(widget, color):
    i = 0
    for n in widget.get_model():
        if n[0] == color:
            break
        i = i + 1
    widget.set_active(i)


def clean_text(text=None):
    if text == None:
        return ""
    return text


class ControllerConfig:
    configPath = None
    config = None
    window = None

    def __init__(self, path):
        self.configPath = path
        # readJson File
        with open(self.configPath, "r") as fp:
            self.config = json.load(fp)

    def open(self):
        self.window = PreferenceWindow()

    def close(self):
        Gtk.main_quit()

    def save_config(self):
        # save config to file
        with open(self.configPath, "w") as outfile:
            json.dump(self.config, outfile)

        # issue command to refresh fw-ctrl
        bashCommand = f"fw-ctrl refresh"
        subprocess.run(bashCommand, stdout=subprocess.PIPE, shell=True)

    def new_window(self):
        self.window = PreferenceWindow()


class PreferenceWindow:
    battery_status = None
    battery_max_charge = None
    battery_current_charge = None

    led_active = None
    led_color_default = None
    led_color_charging = None
    led_level_level1 = None
    led_color_level1 = None
    led_blink_level1 = None
    led_level_level2 = None
    led_color_level2 = None
    led_blink_level2 = None

    fan_active = None
    fan_profile = None
    fan_profile_discharging = None

    bcklght_active = None
    bcklght_step = None
    bcklght_max = None
    bcklght_brigthness_path = None
    bcklght_brigthness_max = None
    bcklght_brigthness_sensor = None

    main_window = None

    def __init__(self):
        # if window != None:
        #     window.show_all()
        #     pass

        builder = Gtk.Builder()
        builder.add_from_file("/usr/local/share/fw-ctrl/controlcenter.glade")
        # get every Field
        self.battery_status = builder.get_object("battery_status")
        self.battery_max_charge = builder.get_object("battery_max_charge")
        self.battery_current_charge = builder.get_object(
            "battery_current_charge")
        self.led_active = builder.get_object("led_active")
        self.led_color_default = builder.get_object("led_color_default")
        self.led_color_charging = builder.get_object("led_color_charging")
        self.led_level_level1 = builder.get_object("led_level_level1")
        self.led_color_level1 = builder.get_object("led_color_level1")
        self.led_blink_level1 = builder.get_object("led_blink_level1")
        self.led_level_level2 = builder.get_object("led_level_level2")
        self.led_color_level2 = builder.get_object("led_color_level2")
        self.led_blink_level2 = builder.get_object("led_blink_level2")
        self.fan_active = builder.get_object("fan_active")
        self.fan_profile = builder.get_object("fan_profile")
        self.fan_profile_discharging = builder.get_object(
            "fan_profile_discharging")
        self.bcklght_active = builder.get_object("bcklght_active")
        self.bcklght_step = builder.get_object("bcklght_step")
        self.bcklght_max = builder.get_object("bcklght_max")
        self.bcklght_brigthness_path = builder.get_object(
            "bcklght_brigthness_path")
        self.bcklght_brigthness_max = builder.get_object(
            "bcklght_brigthness_max")
        self.bcklght_brigthness_sensor = builder.get_object(
            "bcklght_brigthness_sensor")
        # fill every field
        self.battery_status.set_text(
            controller.config["manager"]["batteryChargingStatusPath"])
        self.battery_max_charge.set_text(
            controller.config["manager"]["batteryFullChargePath"])
        self.battery_current_charge.set_text(
            controller.config["manager"]["batteryCurrentChargePath"])

        self.led_active.set_active(controller.config["led"]["active"])
        set_combo_value(self.led_color_default,
                        controller.config["led"]["defaultColor"])
        set_combo_value(self.led_color_charging,
                        controller.config["led"]["chargingColor"])
        self.led_level_level1.set_value(
            int(controller.config["led"]["powerLevel1"]["level"]))
        set_combo_value(self.led_color_level1,
                        controller.config["led"]["powerLevel1"]["color"])
        self.led_blink_level1.set_active(
            controller.config["led"]["powerLevel1"]["blink"])
        self.led_level_level2.set_value(
            int(controller.config["led"]["powerLevel2"]["level"]))
        set_combo_value(self.led_color_level2,
                        controller.config["led"]["powerLevel2"]["color"])
        self.led_blink_level2.set_active(
            controller.config["led"]["powerLevel2"]["blink"])

        self.fan_active.set_active(controller.config["fan"]["active"])
        self.fan_profile_discharging.append_text("")
        for strat in controller.config["fan"]["strategies"]:
            self.fan_profile.append_text(strat)
            self.fan_profile_discharging.append_text(strat)
        set_combo_value(self.fan_profile,
                        controller.config["fan"]["defaultStrategy"])
        set_combo_value(self.fan_profile_discharging,
                        controller.config["fan"]["strategyOnDischarging"])
        self.bcklght_active.set_active(
            controller.config["backlight"]["active"])
        # config["backlight"]["sensitivity"]
        self.bcklght_max.set_value(
            int(controller.config["backlight"]["maxPercent"]))
        self.bcklght_step.set_value(
            int(controller.config["backlight"]["stepnumber"]))
        self.bcklght_brigthness_sensor.set_text(
            controller.config["backlight"]["sensor"])
        self.bcklght_brigthness_path.set_text(
            controller.config["backlight"]["backlight"])
        self.bcklght_brigthness_max.set_text(
            controller.config["backlight"]["backlightMax"])
        builder.connect_signals(self)
        self.main_window = builder.get_object("window_main")
        self.main_window.connect("delete-event", self.on_close)
        self.main_window.set_icon_from_file("/usr/local/share/fw-ctrl/fw-ctrl-ui.svg")
        self.main_window.show_all()
        Gtk.main()

    def on_close(widget, a, b):
        controller.close()

    def hide(self):
        self.main_window.hide()

    def on_save_button_is_clicked(self, button):
        # read every field in config
        controller.config["manager"]["batteryChargingStatusPath"] = clean_text(
            self.battery_status.get_text())
        controller.config["manager"]["batteryFullChargePath"] = clean_text(
            self.battery_max_charge.get_text())
        controller.config["manager"]["batteryCurrentChargePath"] = clean_text(
            self.battery_current_charge.get_text())

        controller.config["led"]["active"] = self.led_active.get_active()
        controller.config["led"]["defaultColor"] = clean_text(
            self.led_color_default.get_active_text())
        controller.config["led"]["chargingColor"] = clean_text(
            self.led_color_charging.get_active_text())
        controller.config["led"]["powerLevel1"]["level"] = self.led_level_level1.get_value_as_int()
        controller.config["led"]["powerLevel1"]["color"] = clean_text(
            self.led_color_level1.get_active_text())
        controller.config["led"]["powerLevel1"]["blink"] = self.led_blink_level1.get_active(
        )
        controller.config["led"]["powerLevel2"]["level"] = self.led_level_level2.get_value_as_int()
        controller.config["led"]["powerLevel2"]["color"] = clean_text(
            self.led_color_level2.get_active_text())
        controller.config["led"]["powerLevel2"]["blink"] = self.led_blink_level2.get_active(
        )

        controller.config["fan"]["active"] = self.fan_active.get_active()
        controller.config["fan"]["defaultStrategy"] = clean_text(
            self.fan_profile.get_active_text())
        controller.config["fan"]["strategyOnDischarging"] = clean_text(
            self.fan_profile_discharging.get_active_text())

        controller.config["backlight"]["active"] = self.bcklght_active.get_active()
        controller.config["backlight"]["maxPercent"] = self.bcklght_max.get_value_as_int(
        )
        controller.config["backlight"]["stepnumber"] = self.bcklght_step.get_value_as_int(
        )
        controller.config["backlight"]["sensor"] = clean_text(
            self.bcklght_brigthness_sensor.get_text())
        controller.config["backlight"]["backlight"] = clean_text(
            self.bcklght_brigthness_path.get_text())
        controller.config["backlight"]["backlightMax"] = clean_text(
            self.bcklght_brigthness_max.get_text())

        controller.save_config()
        controller.close()


if __name__ == '__main__':
    controller = ControllerConfig(
        os.path.expanduser("~/.config/fw-ctrl/config.json"))

    parser = argparse.ArgumentParser(
        description="Control Framework's laptop power led, fan and backlight",
    )
    args = parser.parse_args()
    controller.open()
