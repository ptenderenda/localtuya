"""Platform to locally control Tuya-based climate devices."""
import asyncio
import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.climate import (
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DOMAIN,
    ClimateEntity,
)
from homeassistant.components.climate.const import (
    CURRENT_HVAC_OFF,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_DRY,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_FAN,

    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_NONE,
    ClimateEntityFeature,
    SUPPORT_FAN_MODE,
    SUPPORT_SWING_MODE,

    PRESET_NONE,
    PRESET_ECO,
    PRESET_AWAY,
    PRESET_HOME,

    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    FAN_OFF,

    SWING_ON,
    SWING_OFF,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_TEMPERATURE_UNIT,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    UnitOfTemperature,
)

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_CURRENT_TEMPERATURE_DP,
    CONF_ECO_DP,
    CONF_ECO_VALUE,
    CONF_HEURISTIC_ACTION,
    CONF_HVAC_ACTION_DP,
    CONF_HVAC_ACTION_SET,
    CONF_HVAC_MODE_DP,
    CONF_HVAC_MODE_SET,
    CONF_MAX_TEMP_DP,
    CONF_MIN_TEMP_DP,
    CONF_PRECISION,
    CONF_PRESET_DP,
    CONF_PRESET_SET,
    CONF_TARGET_PRECISION,
    CONF_TARGET_TEMPERATURE_DP,
    CONF_TEMPERATURE_STEP,
    CONF_FAN_MODE_DP,
    CONF_FAN_MODE_SET,
    CONF_FAN_SWING_MODE_DP,
    CONF_FAN_SWING_MODE_SET,
)

_LOGGER = logging.getLogger(__name__)

HVAC_MODE_SETS = {
    "manual/auto": {
        HVAC_MODE_HEAT: "manual",
        HVAC_MODE_AUTO: "auto",
    },
    "Manual/Auto": {
        HVAC_MODE_HEAT: "Manual",
        HVAC_MODE_AUTO: "Auto",
    },
    "Manual/Program": {
        HVAC_MODE_HEAT: "Manual",
        HVAC_MODE_AUTO: "Program",
    },
    "m/p": {
        HVAC_MODE_HEAT: "m",
        HVAC_MODE_AUTO: "p",
    },
    "True/False": {
        HVAC_MODE_HEAT: True,
    },
    "1/0": {
        HVAC_MODE_HEAT: "1",
        HVAC_MODE_AUTO: "0",
    },
    "0(auto)/1(heat)/2(dry)/3(cool)/4(fan only)": {
        HVAC_MODE_AUTO: "0",
        HVAC_MODE_HEAT: "1",
        HVAC_MODE_DRY: "2",
        HVAC_MODE_COOL: "3",
        HVAC_MODE_FAN_ONLY: "4",
    },
}
HVAC_ACTION_SETS = {
    "True/False": {
        CURRENT_HVAC_HEAT: True,
        CURRENT_HVAC_IDLE: False,
    },
    "open/close": {
        CURRENT_HVAC_HEAT: "open",
        CURRENT_HVAC_IDLE: "close",
    },
    "heating/no_heating": {
        CURRENT_HVAC_HEAT: "heating",
        CURRENT_HVAC_IDLE: "no_heating",
    },
    "Heat/Warming": {
        CURRENT_HVAC_HEAT: "Heat",
        CURRENT_HVAC_IDLE: "Warming",
    },
    "0(auto)/1(heat)/2(dry)/3(cool)/4(fan only)": {
        CURRENT_HVAC_HEAT: "1",
        CURRENT_HVAC_DRY: "2",
        CURRENT_HVAC_COOL: "3",
        CURRENT_HVAC_FAN: "4",
    },
}
PRESET_SETS = {
    "Manual/Holiday/Program": {
        PRESET_AWAY: "Holiday",
        PRESET_HOME: "Program",
        PRESET_NONE: "Manual",
    },
}

FAN_MODE_SETS = {
    "0(auto)/1(low)/2(medium)/3(hight)": {
        FAN_AUTO: "0",
        FAN_LOW: "1",
        FAN_MEDIUM: "2",
        FAN_HIGH: "3",
    },
}

FAN_SWING_MODE_SETS = {
    "True/False": {
        SWING_ON: True,
        SWING_OFF: False,
    },
}

# FAN_ON = "on"
# FAN_OFF = "off"
# FAN_AUTO = "auto"
# FAN_LOW = "low"
# FAN_MEDIUM = "medium"
# FAN_HIGH = "high"
# FAN_TOP = "top"
# FAN_MIDDLE = "middle"
# FAN_FOCUS = "focus"
# FAN_DIFFUSE = "diffuse"
# 
# 
# # Possible swing state
# SWING_ON = "on"
# SWING_OFF = "off"
# SWING_BOTH = "both"
# SWING_VERTICAL = "vertical"
# SWING_HORIZONTAL = "horizontal"

TEMPERATURE_CELSIUS = "celsius"
TEMPERATURE_FAHRENHEIT = "fahrenheit"
DEFAULT_TEMPERATURE_UNIT = TEMPERATURE_CELSIUS
DEFAULT_PRECISION = PRECISION_TENTHS
DEFAULT_TEMPERATURE_STEP = PRECISION_HALVES
# Empirically tested to work for AVATTO thermostat
MODE_WAIT = 0.1


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_TARGET_TEMPERATURE_DP): vol.In(dps),
        vol.Optional(CONF_CURRENT_TEMPERATURE_DP): vol.In(dps),
        vol.Optional(CONF_TEMPERATURE_STEP): vol.In(
            [PRECISION_WHOLE, PRECISION_HALVES, PRECISION_TENTHS]
        ),
        vol.Optional(CONF_MAX_TEMP_DP): vol.In(dps),
        vol.Optional(CONF_MIN_TEMP_DP): vol.In(dps),
        vol.Optional(CONF_PRECISION): vol.In(
            [PRECISION_WHOLE, PRECISION_HALVES, PRECISION_TENTHS]
        ),
        vol.Optional(CONF_HVAC_MODE_DP): vol.In(dps),
        vol.Optional(CONF_HVAC_MODE_SET): vol.In(list(HVAC_MODE_SETS.keys())),
        vol.Optional(CONF_HVAC_ACTION_DP): vol.In(dps),
        vol.Optional(CONF_HVAC_ACTION_SET): vol.In(list(HVAC_ACTION_SETS.keys())),
        vol.Optional(CONF_ECO_DP): vol.In(dps),
        vol.Optional(CONF_ECO_VALUE): str,
        vol.Optional(CONF_PRESET_DP): vol.In(dps),
        vol.Optional(CONF_PRESET_SET): vol.In(list(PRESET_SETS.keys())),
        vol.Optional(CONF_TEMPERATURE_UNIT): vol.In(
            [TEMPERATURE_CELSIUS, TEMPERATURE_FAHRENHEIT]
        ),
        vol.Optional(CONF_TARGET_PRECISION): vol.In(
            [PRECISION_WHOLE, PRECISION_HALVES, PRECISION_TENTHS]
        ),
        vol.Optional(CONF_HEURISTIC_ACTION): bool,
        vol.Optional(CONF_FAN_MODE_DP): vol.In(dps),
        vol.Optional(CONF_FAN_MODE_SET): vol.In(list(FAN_MODE_SETS.keys())),
        vol.Optional(CONF_FAN_SWING_MODE_DP): vol.In(dps),
        vol.Optional(CONF_FAN_SWING_MODE_SET): vol.In(list(FAN_SWING_MODE_SETS.keys())),
    }


class LocaltuyaClimate(LocalTuyaEntity, ClimateEntity):
    """Tuya climate device."""

    def __init__(
        self,
        device,
        config_entry,
        switchid,
        **kwargs,
    ):
        """Initialize a new LocaltuyaClimate."""
        super().__init__(device, config_entry, switchid, _LOGGER, **kwargs)
        self._state = None
        self._target_temperature = None
        self._current_temperature = None
        self._hvac_mode = None
        self._preset_mode = None
        self._hvac_action = None
        self._fan_mode = None
        self._fan_swing_mode = None
        self._precision = self._config.get(CONF_PRECISION, DEFAULT_PRECISION)
        self._target_precision = self._config.get(
            CONF_TARGET_PRECISION, self._precision
        )
        self._conf_hvac_mode_dp = self._config.get(CONF_HVAC_MODE_DP)
        self._conf_hvac_mode_set = HVAC_MODE_SETS.get(
            self._config.get(CONF_HVAC_MODE_SET), {}
        )
        self._conf_preset_dp = self._config.get(CONF_PRESET_DP)
        self._conf_preset_set = PRESET_SETS.get(self._config.get(CONF_PRESET_SET), {})
        self._conf_hvac_action_dp = self._config.get(CONF_HVAC_ACTION_DP)
        self._conf_hvac_action_set = HVAC_ACTION_SETS.get(
            self._config.get(CONF_HVAC_ACTION_SET), {}
        )
        self._conf_eco_dp = self._config.get(CONF_ECO_DP)
        self._conf_eco_value = self._config.get(CONF_ECO_VALUE, "ECO")
        self._has_presets = self.has_config(CONF_ECO_DP) or self.has_config(
            CONF_PRESET_DP
        )
        self._conf_fan_mode_dp = self._config.get(CONF_FAN_MODE_DP)
        self._conf_fan_mode_set = FAN_MODE_SETS.get(
            self._config.get(CONF_FAN_MODE_SET), {}
        )
        
        self._conf_fan_swing_mode_dp = self._config.get(CONF_FAN_SWING_MODE_DP)
        self._conf_fan_swing_mode_set = FAN_SWING_MODE_SETS.get(
            self._config.get(CONF_FAN_SWING_MODE_SET), {}
        )
        _LOGGER.debug("Initialized climate [%s]", self.name)

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = 0
        if self.has_config(CONF_TARGET_TEMPERATURE_DP):
            supported_features = supported_features | ClimateEntityFeature.TARGET_TEMPERATURE
        if self.has_config(CONF_MAX_TEMP_DP):
            supported_features = supported_features | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        if self.has_config(CONF_PRESET_DP) or self.has_config(CONF_ECO_DP):
            supported_features = supported_features | ClimateEntityFeature.PRESET_MODE
        supported_features = supported_features | SUPPORT_FAN_MODE
        supported_features = supported_features | SUPPORT_SWING_MODE

        # SUPPORT_TARGET_TEMPERATURE = 1
        # SUPPORT_TARGET_TEMPERATURE_RANGE = 2
        # SUPPORT_TARGET_HUMIDITY = 4
        # SUPPORT_FAN_MODE = 8
        # SUPPORT_PRESET_MODE = 16
        # SUPPORT_SWING_MODE = 32
        # SUPPORT_AUX_HEAT = 64
            
        return supported_features

    @property
    def precision(self):
        """Return the precision of the system."""
        return self._precision

    @property
    def target_precision(self):
        """Return the precision of the target."""
        return self._target_precision

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        if (
            self._config.get(CONF_TEMPERATURE_UNIT, DEFAULT_TEMPERATURE_UNIT)
            == TEMPERATURE_FAHRENHEIT
        ):
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        return self._hvac_mode

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        if not self.has_config(CONF_HVAC_MODE_DP):
            return None
        return list(self._conf_hvac_mode_set) + [HVAC_MODE_OFF]

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        if self._config.get(CONF_HEURISTIC_ACTION, False):
            if self._hvac_mode == HVAC_MODE_HEAT:
                if self._current_temperature < (
                    self._target_temperature - self._precision
                ):
                    self._hvac_action = CURRENT_HVAC_HEAT
                if self._current_temperature == (
                    self._target_temperature - self._precision
                ):
                    if self._hvac_action == CURRENT_HVAC_HEAT:
                        self._hvac_action = CURRENT_HVAC_HEAT
                    if self._hvac_action == CURRENT_HVAC_IDLE:
                        self._hvac_action = CURRENT_HVAC_IDLE
                if (
                    self._current_temperature + self._precision
                ) > self._target_temperature:
                    self._hvac_action = CURRENT_HVAC_IDLE
            return self._hvac_action
        return self._hvac_action

    @property
    def preset_mode(self):
        """Return current preset."""
        return self._preset_mode

    @property
    def preset_modes(self):
        """Return the list of available presets modes."""
        if not self._has_presets:
            return None
        presets = list(self._conf_preset_set)
        if self._conf_eco_dp:
            presets.append(PRESET_ECO)
        return presets

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._config.get(CONF_TEMPERATURE_STEP, DEFAULT_TEMPERATURE_STEP)

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._fan_mode

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        if not self.has_config(CONF_FAN_MODE_DP):
            return None
        return list(self._conf_fan_mode_set) + [FAN_OFF]

    @property
    def swing_mode(self):
        """Returns the swing setting. Requires SUPPORT_SWING_MODE"""   
        return self._fan_swing_mode

    @property
    def swing_modes(self):
        """Returns the list of available swing modes. Requires SUPPORT_SWING_MODE."""   
        if not self.has_config(CONF_FAN_SWING_MODE_DP):
            return None
        return list(self._conf_fan_swing_mode_set)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs and self.has_config(CONF_TARGET_TEMPERATURE_DP):
            temperature = round(kwargs[ATTR_TEMPERATURE] / self._target_precision)
            await self._device.set_dp(
                temperature, self._config[CONF_TARGET_TEMPERATURE_DP]
            )

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        await self._device.set_dp(
            self._conf_fan_mode_set[fan_mode], self._conf_fan_mode_dp
        )

    async def async_set_swing_mode(self, swing_mode):
        """Set new target swing operation."""
        await self._device.set_dp(
            self._conf_fan_swing_mode_set[swing_mode], self._conf_fan_swing_mode_dp
        )

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target operation mode."""
        if hvac_mode == HVAC_MODE_OFF:
            await self._device.set_dp(False, self._dp_id)
            return
        if not self._state and self._conf_hvac_mode_dp != self._dp_id:
            await self._device.set_dp(True, self._dp_id)
            # Some thermostats need a small wait before sending another update
            await asyncio.sleep(MODE_WAIT)
        await self._device.set_dp(
            self._conf_hvac_mode_set[hvac_mode], self._conf_hvac_mode_dp
        )

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self._device.set_dp(True, self._dp_id)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self._device.set_dp(False, self._dp_id)

    async def async_set_preset_mode(self, preset_mode):
        """Set new target preset mode."""
        if preset_mode == PRESET_ECO:
            await self._device.set_dp(self._conf_eco_value, self._conf_eco_dp)
            return
        await self._device.set_dp(
            self._conf_preset_set[preset_mode], self._conf_preset_dp
        )

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        if self.has_config(CONF_MIN_TEMP_DP):
            return self.dps_conf(CONF_MIN_TEMP_DP)
        # DEFAULT_MIN_TEMP is in C
        if self.temperature_unit == UnitOfTemperature.FAHRENHEIT:
            return DEFAULT_MIN_TEMP * 1.8 + 32
        else:
            return DEFAULT_MIN_TEMP

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if self.has_config(CONF_MAX_TEMP_DP):
            return self.dps_conf(CONF_MAX_TEMP_DP)
        # DEFAULT_MAX_TEMP is in C
        if self.temperature_unit == UnitOfTemperature.FAHRENHEIT:
            return DEFAULT_MAX_TEMP * 1.8 + 32
        else:
            return DEFAULT_MAX_TEMP

    def status_updated(self):
        """Device status was updated."""
        self._state = self.dps(self._dp_id)

        if self.has_config(CONF_TARGET_TEMPERATURE_DP):
            self._target_temperature = (
                self.dps_conf(CONF_TARGET_TEMPERATURE_DP) * self._target_precision
            )

        if self.has_config(CONF_CURRENT_TEMPERATURE_DP):
            self._current_temperature = (
                self.dps_conf(CONF_CURRENT_TEMPERATURE_DP) * self._precision
            )

        if self._has_presets:
            if (
                self.has_config(CONF_ECO_DP)
                and self.dps_conf(CONF_ECO_DP) == self._conf_eco_value
            ):
                self._preset_mode = PRESET_ECO
            else:
                for preset, value in self._conf_preset_set.items():  # todo remove
                    if self.dps_conf(CONF_PRESET_DP) == value:
                        self._preset_mode = preset
                        break
                else:
                    self._preset_mode = PRESET_NONE

        # Update the HVAC status
        if self.has_config(CONF_HVAC_MODE_DP):
            if not self._state:
                self._hvac_mode = HVAC_MODE_OFF
            else:
                for mode, value in self._conf_hvac_mode_set.items():
                    if self.dps_conf(CONF_HVAC_MODE_DP) == value:
                        self._hvac_mode = mode
                        break
                else:
                    # in case hvac mode and preset share the same dp
                    self._hvac_mode = HVAC_MODE_AUTO

        # Update the current action
        for action, value in self._conf_hvac_action_set.items():
            if self.dps_conf(CONF_HVAC_ACTION_DP) == value:
                self._hvac_action = action
                
        # update fan mode
        if self.has_config(CONF_FAN_MODE_DP):
            if not self._state:
                self._fan_mode = FAN_OFF
            else:
                for mode, value in self._conf_fan_mode_set.items():
                    if self.dps_conf(CONF_FAN_MODE_DP) == value:
                        self._fan_mode = mode
                        break
                else:
                    # in case fan mode and preset share the same dp
                    self._fan_mode = FAN_AUTO

        # update fan swing mode
        if self.has_config(CONF_FAN_SWING_MODE_DP):   
            if not self._state:
                self._fan_swing_mode = SWING_OFF
            else:
                for mode, value in self._conf_fan_swing_mode_set.items():
                    if self.dps_conf(CONF_FAN_SWING_MODE_DP) == value:
                        self._fan_swing_mode = mode
                        break
                else:
                    # in case fan mode and preset share the same dp
                    self._fan_swing_mode = SWING_OFF

async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaClimate, flow_schema)
